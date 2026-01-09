"""
Pytest configuration and fixtures.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime
from fastapi.testclient import TestClient

from src.main import app
from src.middleware.auth import UserContext


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def yacht_id():
    """Test yacht UUID."""
    return uuid4()


@pytest.fixture
def user_id():
    """Test user UUID."""
    return uuid4()


@pytest.fixture
def user_context(yacht_id, user_id):
    """Mock authenticated user context."""
    return UserContext(
        user_id=user_id,
        yacht_id=yacht_id,
        email="test@example.com",
        roles=["crew"],
        is_hod=False
    )


@pytest.fixture
def hod_context(yacht_id, user_id):
    """Mock HOD user context."""
    return UserContext(
        user_id=user_id,
        yacht_id=yacht_id,
        email="hod@example.com",
        roles=["chief_engineer"],
        is_hod=True
    )


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    mock = Mock()
    mock.table = Mock(return_value=mock)
    mock.select = Mock(return_value=mock)
    mock.insert = Mock(return_value=mock)
    mock.update = Mock(return_value=mock)
    mock.delete = Mock(return_value=mock)
    mock.eq = Mock(return_value=mock)
    mock.in_ = Mock(return_value=mock)
    mock.single = Mock(return_value=mock)
    mock.execute = Mock(return_value=Mock(data=[]))
    return mock


@pytest.fixture
def sample_part(yacht_id):
    """Sample part data."""
    return {
        "part_id": uuid4(),
        "yacht_id": yacht_id,
        "part_number": "MTU-OF-4568",
        "name": "MTU Oil Filter",
        "manufacturer": "MTU",
        "category": "filters",
        "location": "Engine Room",
        "quantity_on_hand": 12.0,
        "minimum_quantity": 6.0,
        "unit": "ea"
    }


@pytest.fixture
def sample_equipment(yacht_id):
    """Sample equipment data."""
    return {
        "equipment_id": uuid4(),
        "yacht_id": yacht_id,
        "code": "ME-S-001",
        "name": "Main Engine Starboard",
        "manufacturer": "MTU",
        "model": "16V4000 M93L",
        "location": "Engine Room",
        "status": "operational",
        "category": "main_engine"
    }


@pytest.fixture
def sample_draft_line(yacht_id):
    """Sample draft line data."""
    part_id = uuid4()
    return {
        "draft_line_id": uuid4(),
        "session_id": uuid4(),
        "yacht_id": yacht_id,
        "line_number": 1,
        "quantity": 12.0,
        "unit": "ea",
        "description": "MTU Oil Filter",
        "part_number": "MTU-OF-4568",
        "extraction_confidence": 0.95,
        "verification_status": "unverified",
        "suggested_part": {
            "part_id": part_id,
            "part_number": "MTU-OF-4568",
            "name": "MTU Oil Filter",
            "confidence": 1.0,
            "match_reason": "exact_part_number",
            "current_stock": 12.0
        }
    }


@pytest.fixture
def sample_session(yacht_id, user_id):
    """Sample receiving session data."""
    session_id = uuid4()
    return {
        "session_id": session_id,
        "yacht_id": yacht_id,
        "created_by": user_id,
        "status": "draft",
        "upload_type": "receiving",
        "created_at": datetime.utcnow().isoformat(),
        "image_count": 1,
        "total_cost": 0.05
    }


@pytest.fixture
def sample_ocr_result():
    """Sample OCR extraction result."""
    return {
        "text": """
        PACKING SLIP

        Item    Qty  Unit  Part Number    Description
        1       12   ea    MTU-OF-4568   MTU Oil Filter
        2       8    ea    KOH-AF-9902   Kohler Air Filter
        3       15   ea    MTU-FF-4569   MTU Fuel Filter
        """,
        "confidence": 0.92,
        "method": "tesseract"
    }


@pytest.fixture
def sample_parsed_lines():
    """Sample parsed line items."""
    return [
        {
            "line_number": 1,
            "quantity": 12.0,
            "unit": "ea",
            "part_number": "MTU-OF-4568",
            "description": "MTU Oil Filter"
        },
        {
            "line_number": 2,
            "quantity": 8.0,
            "unit": "ea",
            "part_number": "KOH-AF-9902",
            "description": "Kohler Air Filter"
        },
        {
            "line_number": 3,
            "quantity": 15.0,
            "unit": "ea",
            "part_number": "MTU-FF-4569",
            "description": "MTU Fuel Filter"
        }
    ]


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock = Mock()
    mock.choices = [Mock(message=Mock(content='{"lines": [], "extraction_notes": "Test"}'))]
    mock.usage = Mock(prompt_tokens=100, completion_tokens=50)
    return mock


@pytest.fixture
def sample_shipping_label_metadata():
    """Sample shipping label metadata."""
    return {
        "carrier": "FedEx",
        "tracking_number": "1234567890",
        "recipient_name": "MY Excellence",
        "recipient_address": "123 Marina Bay, Singapore",
        "ship_date": "2026-01-08",
        "delivery_date": "2026-01-10",
        "service_type": "Express"
    }


@pytest.fixture
def sample_image_bytes():
    """Sample image file bytes."""
    # Create a minimal PNG image
    import io
    from PIL import Image

    img = Image.new('RGB', (100, 100), color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF file bytes."""
    # Minimal PDF
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000229 00000 n
0000000328 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
422
%%EOF"""


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks between tests."""
    yield
    # Cleanup happens automatically with pytest
