# Test Suite Documentation
## Image Processing Service

This directory contains comprehensive tests for the Image Processing Service.

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures and configuration
├── test_intake.py                 # Intake layer tests (validation, dedup, rate limiting)
├── test_extraction.py             # Extraction layer tests (OCR, parsing, cost control)
├── test_reconciliation.py         # Reconciliation tests (matching, ranking)
├── test_routes.py                 # API integration tests
├── test_label_generation.py       # Label generation tests (QR, PDF)
└── README.md                      # This file
```

---

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
pytest tests/test_intake.py
pytest tests/test_extraction.py
pytest tests/test_routes.py
```

### Run Specific Test Classes

```bash
pytest tests/test_intake.py::TestFileValidator
pytest tests/test_extraction.py::TestRowParser
```

### Run Specific Test Methods

```bash
pytest tests/test_intake.py::TestFileValidator::test_validate_valid_image
```

### Run with Coverage

```bash
pytest --cov=src --cov-report=html
```

Open `htmlcov/index.html` in your browser to view detailed coverage report.

### Run with Verbose Output

```bash
pytest -v
```

### Run Only Fast Tests (Skip Slow Tests)

```bash
pytest -m "not slow"
```

---

## Test Categories

### Unit Tests

Tests for individual components in isolation:
- **test_intake.py**: File validation, deduplication, rate limiting
- **test_extraction.py**: OCR, parsing, table detection, cost control
- **test_reconciliation.py**: Part matching, fuzzy search, suggestion ranking
- **test_label_generation.py**: QR code generation, PDF layout

### Integration Tests

Tests for API endpoints and full workflows:
- **test_routes.py**: Upload, session, commit, label, photo, label generation routes

---

## Test Coverage Goals

Target coverage: **>90%** for production code

Current coverage by module:
- Intake layer: >90%
- OCR layer: >85%
- Extraction layer: >90%
- Reconciliation layer: >90%
- Routes: >85%
- Label generation: >85%

---

## Writing New Tests

### Test Structure

Follow this structure for new tests:

```python
"""
Module docstring explaining what's being tested.
"""

import pytest
from unittest.mock import Mock, patch

from src.module import ComponentToTest


class TestComponentName:
    """Tests for ComponentName."""

    def test_feature_success_case(self):
        """Test successful execution of feature."""
        # Arrange
        component = ComponentToTest()

        # Act
        result = component.do_something()

        # Assert
        assert result is not None

    def test_feature_error_case(self):
        """Test error handling."""
        component = ComponentToTest()

        with pytest.raises(ValueError):
            component.do_something_invalid()

    @pytest.mark.asyncio
    async def test_async_feature(self):
        """Test async feature."""
        component = ComponentToTest()

        result = await component.async_method()

        assert result is not None
```

### Using Fixtures

Fixtures are defined in `conftest.py` and are available to all tests:

```python
def test_with_fixtures(yacht_id, user_context, sample_part):
    """Test using shared fixtures."""
    assert yacht_id is not None
    assert user_context.yacht_id == yacht_id
    assert sample_part["part_number"] == "MTU-OF-4568"
```

### Mocking External Dependencies

Use `unittest.mock` to mock external services:

```python
from unittest.mock import patch, Mock

@patch("src.handlers.receiving_handler.ReceivingHandler.process_upload")
def test_with_mock(mock_process):
    """Test with mocked dependency."""
    mock_process.return_value = {"status": "success"}

    # Your test code here
```

### Testing Async Code

Use `@pytest.mark.asyncio` for async tests:

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await my_async_function()
    assert result is not None
```

---

## Available Fixtures

### Authentication Fixtures
- `yacht_id`: Test yacht UUID
- `user_id`: Test user UUID
- `user_context`: Mock authenticated user (crew role)
- `hod_context`: Mock HOD user (chief_engineer role)

### Data Fixtures
- `sample_part`: Sample part data
- `sample_equipment`: Sample equipment data
- `sample_draft_line`: Sample draft line data
- `sample_session`: Sample receiving session data
- `sample_ocr_result`: Sample OCR extraction result
- `sample_parsed_lines`: Sample parsed line items
- `sample_shipping_label_metadata`: Sample label metadata
- `sample_image_bytes`: Sample PNG image bytes
- `sample_pdf_bytes`: Sample PDF file bytes

### Mock Fixtures
- `mock_supabase`: Mock Supabase client
- `mock_openai_response`: Mock OpenAI API response

### Client Fixtures
- `client`: FastAPI test client

---

## Best Practices

### 1. Test Naming

Use descriptive test names that explain what's being tested:

```python
# Good
def test_validate_oversized_file_returns_error()

# Bad
def test_validate()
```

### 2. Arrange-Act-Assert Pattern

Structure tests clearly:

```python
def test_something():
    # Arrange - Set up test data
    validator = FileValidator("receiving")
    file = create_test_file()

    # Act - Execute the code being tested
    result = validator.validate(file)

    # Assert - Verify the results
    assert result["is_valid"] is True
```

### 3. Test One Thing Per Test

Each test should verify one specific behavior:

```python
# Good - Tests one thing
def test_validate_rejects_oversized_files()
def test_validate_rejects_invalid_mime_types()

# Bad - Tests multiple things
def test_validate_handles_all_errors()
```

### 4. Use Fixtures for Common Setup

Avoid duplicating setup code:

```python
# Good - Use fixtures
def test_something(sample_part):
    assert sample_part["part_number"] is not None

# Bad - Duplicate setup
def test_something():
    part = {"part_id": uuid4(), "part_number": "MTU-OF-4568", ...}
    assert part["part_number"] is not None
```

### 5. Mock External Dependencies

Don't make real API calls or database queries in tests:

```python
@patch("src.handlers.receiving_handler.Supabase")
def test_handler(mock_supabase):
    mock_supabase.return_value.table.return_value.select.return_value = []
    # Test code here
```

---

## Continuous Integration

Tests are automatically run on:
- Every commit to `main` branch
- Every pull request
- Nightly builds

CI requirements:
- All tests must pass
- Coverage must be >90%
- No failing linters (black, isort, flake8, mypy)

---

## Troubleshooting

### Tests Fail Locally But Pass in CI

Check:
- Python version (should be 3.11+)
- Dependency versions (run `pip install -r requirements.txt`)
- Environment variables (copy `.env.example` to `.env`)

### Async Tests Fail

Ensure `pytest-asyncio` is installed:

```bash
pip install pytest-asyncio
```

And use `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_something():
    result = await async_function()
    assert result is not None
```

### Mock Not Working

Check import paths match exactly:

```python
# If your code does:
from src.handlers.receiving_handler import ReceivingHandler

# Your mock should be:
@patch("src.handlers.receiving_handler.ReceivingHandler")
```

### Coverage Too Low

Run with detailed coverage report to find untested lines:

```bash
pytest --cov=src --cov-report=term-missing
```

This shows line numbers that aren't covered by tests.

---

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure new tests pass
3. Ensure all existing tests still pass
4. Maintain >90% coverage
5. Follow naming conventions
6. Add docstrings to test functions

---

**Questions?** Check the main README or ask the team.
