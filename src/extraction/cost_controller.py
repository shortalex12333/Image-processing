"""
Cost controller for LLM escalation decisions.
Enforces budget caps and decides when to invoke LLM vs return partial results.
"""

from uuid import UUID

from src.config import settings, calculate_llm_cost
from src.logger import get_logger

logger = get_logger(__name__)


class CostBudgetExceeded(Exception):
    """Cost budget exceeded for this session."""
    pass


class Decision:
    """LLM invocation decision."""

    def __init__(
        self,
        action: str,
        reason: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        manual_review_required: bool = False
    ):
        self.action = action  # "return_results", "invoke_llm", "return_partial"
        self.reason = reason
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.manual_review_required = manual_review_required


class SessionCostTracker:
    """Tracks LLM costs per session."""

    def __init__(self, session_id: UUID):
        self.session_id = session_id
        self.llm_calls = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.model_usage = {}  # {model: {calls, tokens, cost}}

    def record_llm_call(self, model: str, input_tokens: int, output_tokens: int, cost: float) -> None:
        """
        Record an LLM API call.

        Args:
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
            cost: Call cost in USD
        """
        self.llm_calls += 1
        self.total_tokens += input_tokens + output_tokens
        self.total_cost += cost

        if model not in self.model_usage:
            self.model_usage[model] = {"calls": 0, "tokens": 0, "cost": 0.0}

        self.model_usage[model]["calls"] += 1
        self.model_usage[model]["tokens"] += input_tokens + output_tokens
        self.model_usage[model]["cost"] += cost

        logger.info("LLM call recorded", extra={
            "session_id": str(self.session_id),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "total_cost": self.total_cost,
            "total_calls": self.llm_calls
        })

        # Alert if approaching limits
        if self.total_cost > settings.max_cost_per_session * 0.8:
            logger.warning("Session approaching cost cap", extra={
                "session_id": str(self.session_id),
                "total_cost": self.total_cost,
                "cap": settings.max_cost_per_session,
                "percentage": (self.total_cost / settings.max_cost_per_session) * 100
            })

    def can_afford_call(self, model: str, estimated_tokens: int) -> bool:
        """
        Check if we can afford another LLM call.

        Args:
            model: Model to use
            estimated_tokens: Estimated total tokens

        Returns:
            True if within budget, False otherwise
        """
        # Estimate cost
        estimated_input = int(estimated_tokens * 0.6)  # ~60% input
        estimated_output = int(estimated_tokens * 0.4)  # ~40% output
        estimated_cost = calculate_llm_cost(model, estimated_input, estimated_output)

        # Check budget
        projected_cost = self.total_cost + estimated_cost
        projected_calls = self.llm_calls + 1

        if projected_cost > settings.max_cost_per_session:
            logger.warning("Cannot afford LLM call - cost budget exceeded", extra={
                "session_id": str(self.session_id),
                "projected_cost": projected_cost,
                "cap": settings.max_cost_per_session
            })
            return False

        if projected_calls > settings.max_llm_calls_per_session:
            logger.warning("Cannot afford LLM call - call count exceeded", extra={
                "session_id": str(self.session_id),
                "projected_calls": projected_calls,
                "cap": settings.max_llm_calls_per_session
            })
            return False

        return True


class CostController:
    """Controls LLM escalation decisions based on cost and quality."""

    def __init__(self, cost_tracker: SessionCostTracker):
        self.cost_tracker = cost_tracker

    def decide_next_action(
        self,
        coverage: float,
        table_confidence: float,
        llm_attempts: int,
        last_llm_confidence: float | None = None
    ) -> Decision:
        """
        Determine whether to escalate to LLM or return current results.

        Args:
            coverage: Percentage of text successfully parsed (0.0 to 1.0)
            table_confidence: Confidence in table detection (0.0 to 1.0)
            llm_attempts: Number of LLM attempts already made
            last_llm_confidence: Confidence from last LLM attempt (if any)

        Returns:
            Decision object with action and parameters

        Decision flow:
        1. If deterministic success (coverage >= 0.8) → return results
        2. If budget exceeded → return partial
        3. If first attempt → invoke gpt-4.1-mini
        4. If second attempt and low confidence → escalate to gpt-4.1
        5. Otherwise → return partial with manual review flag
        """
        # Stage 1: Check deterministic success
        if coverage >= settings.llm_coverage_threshold and table_confidence >= 0.7:
            logger.info("Deterministic success - no LLM needed", extra={
                "coverage": coverage,
                "table_confidence": table_confidence
            })
            return Decision(
                action="return_results",
                reason="deterministic_success"
            )

        # Stage 2: Check LLM budget
        if self.cost_tracker.llm_calls >= settings.max_llm_calls_per_session:
            logger.warning("LLM budget exceeded - returning partial", extra={
                "llm_calls": self.cost_tracker.llm_calls,
                "cap": settings.max_llm_calls_per_session
            })
            return Decision(
                action="return_partial",
                reason="llm_budget_exceeded",
                manual_review_required=True
            )

        if self.cost_tracker.total_cost >= settings.max_cost_per_session:
            logger.warning("Cost budget exceeded - returning partial", extra={
                "total_cost": self.cost_tracker.total_cost,
                "cap": settings.max_cost_per_session
            })
            return Decision(
                action="return_partial",
                reason="cost_budget_exceeded",
                manual_review_required=True
            )

        # Stage 3: Decide normalization vs escalation
        if llm_attempts == 0:
            # First attempt - use gpt-4.1-mini for normalization
            if not self.cost_tracker.can_afford_call("gpt-4.1-mini", 2000):
                return Decision(
                    action="return_partial",
                    reason="cannot_afford_normalization",
                    manual_review_required=True
                )

            logger.info("Invoking LLM normalization", extra={
                "coverage": coverage,
                "model": "gpt-4.1-mini"
            })
            return Decision(
                action="invoke_llm",
                model="gpt-4.1-mini",
                reason="low_coverage",
                max_tokens=2000,
                temperature=0.1
            )

        elif llm_attempts == 1 and last_llm_confidence and last_llm_confidence < 0.6:
            # Second attempt - escalate to gpt-4.1 if low confidence
            if not settings.enable_llm_escalation:
                logger.info("LLM escalation disabled - returning partial")
                return Decision(
                    action="return_partial",
                    reason="escalation_disabled",
                    manual_review_required=True
                )

            if not self.cost_tracker.can_afford_call("gpt-4.1", 3000):
                return Decision(
                    action="return_partial",
                    reason="cannot_afford_escalation",
                    manual_review_required=True
                )

            logger.warning("Escalating to gpt-4.1", extra={
                "last_confidence": last_llm_confidence,
                "model": "gpt-4.1"
            })
            return Decision(
                action="invoke_llm",
                model="gpt-4.1",
                reason="escalation_low_confidence",
                max_tokens=3000,
                temperature=0.2
            )

        else:
            # Give up - return what we have
            logger.info("Max attempts reached - returning partial", extra={
                "llm_attempts": llm_attempts
            })
            return Decision(
                action="return_partial",
                reason="max_attempts_reached",
                manual_review_required=True
            )
