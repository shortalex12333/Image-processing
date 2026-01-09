"""
Integration tests for API routes.
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
from uuid import uuid4
from io import BytesIO

from src.middleware.auth import UserContext


class TestUploadRoutes:
    """Tests for upload routes."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Image Processing Service"
        assert data["docs"] == "/docs"

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.receiving_handler.ReceivingHandler.process_upload")
    def test_upload_image(self, mock_process, mock_auth, client, user_context, sample_image_bytes):
        """Test image upload endpoint."""
        # Mock authentication
        mock_auth.return_value = user_context

        # Mock processing result
        mock_process.return_value = {
            "status": "success",
            "images": [{
                "image_id": str(uuid4()),
                "file_name": "test.png",
                "is_duplicate": False,
                "processing_status": "queued"
            }],
            "processing_eta_seconds": 30
        }

        # Create file upload
        files = {"files": ("test.png", BytesIO(sample_image_bytes), "image/png")}
        data = {"upload_type": "receiving"}

        response = client.post(
            "/api/v1/images/upload",
            files=files,
            data=data,
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert len(result["images"]) > 0

    def test_upload_without_auth(self, client, sample_image_bytes):
        """Test upload without authentication fails."""
        files = {"files": ("test.png", BytesIO(sample_image_bytes), "image/png")}
        data = {"upload_type": "receiving"}

        response = client.post("/api/v1/images/upload", files=files, data=data)

        assert response.status_code == 401


class TestSessionRoutes:
    """Tests for session routes."""

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.receiving_handler.ReceivingHandler.get_session")
    def test_get_session(self, mock_get_session, mock_auth, client, user_context, sample_session, sample_draft_line):
        """Test get session endpoint."""
        mock_auth.return_value = user_context

        session_id = sample_session["session_id"]
        mock_get_session.return_value = {
            "session": sample_session,
            "draft_lines": [sample_draft_line],
            "verification_status": {
                "can_commit": False,
                "verification_percentage": 0.0
            }
        }

        response = client.get(
            f"/api/v1/receiving/sessions/{session_id}",
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "session" in data
        assert "draft_lines" in data

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.receiving_handler.ReceivingHandler.verify_draft_line")
    def test_verify_draft_line(self, mock_verify, mock_auth, client, user_context):
        """Test verify draft line endpoint."""
        mock_auth.return_value = user_context

        session_id = uuid4()
        line_id = uuid4()
        mock_verify.return_value = {"status": "verified", "line_id": str(line_id)}

        response = client.patch(
            f"/api/v1/receiving/sessions/{session_id}/lines/{line_id}/verify",
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "verified"

    def test_get_session_without_auth(self, client):
        """Test get session without authentication fails."""
        session_id = uuid4()

        response = client.get(f"/api/v1/receiving/sessions/{session_id}")

        assert response.status_code == 401


class TestCommitRoutes:
    """Tests for commit routes."""

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.receiving_handler.ReceivingHandler.commit_session")
    def test_commit_session_as_hod(self, mock_commit, mock_auth, client, hod_context):
        """Test commit session as HOD."""
        mock_auth.return_value = hod_context

        session_id = uuid4()
        mock_commit.return_value = {
            "status": "success",
            "receiving_event": {
                "event_id": str(uuid4()),
                "event_number": "RCV-EVT-2026-001",
                "lines_committed": 10
            },
            "inventory_updates": {
                "parts_updated": 8,
                "total_quantity_added": 87.0
            }
        }

        response = client.post(
            f"/api/v1/receiving/sessions/{session_id}/commit",
            json={"commitment_notes": "All verified"},
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @patch("src.middleware.auth.get_current_user")
    def test_commit_session_as_non_hod(self, mock_auth, client, user_context):
        """Test commit session as non-HOD fails."""
        mock_auth.return_value = user_context

        session_id = uuid4()

        response = client.post(
            f"/api/v1/receiving/sessions/{session_id}/commit",
            json={"commitment_notes": "All verified"},
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 403


class TestLabelRoutes:
    """Tests for shipping label routes."""

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.label_handler.LabelHandler.process_shipping_label")
    def test_process_shipping_label(self, mock_process, mock_auth, client, user_context, sample_shipping_label_metadata):
        """Test process shipping label endpoint."""
        mock_auth.return_value = user_context

        image_id = uuid4()
        mock_process.return_value = {
            "status": "completed",
            "metadata": sample_shipping_label_metadata,
            "matched_orders": [],
            "cost": 0.0005
        }

        response = client.post(
            "/api/v1/shipping-labels/process",
            json={"image_id": str(image_id)},
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "metadata" in data
        assert data["metadata"]["carrier"] == "FedEx"


class TestPhotoRoutes:
    """Tests for photo attachment routes."""

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.photo_handler.PhotoHandler.attach_discrepancy_photo")
    def test_attach_discrepancy_photo(self, mock_attach, mock_auth, client, user_context):
        """Test attach discrepancy photo endpoint."""
        mock_auth.return_value = user_context

        image_id = uuid4()
        entity_id = uuid4()
        mock_attach.return_value = {
            "status": "attached",
            "image_id": str(image_id),
            "entity_type": "fault",
            "entity_id": str(entity_id)
        }

        response = client.post(
            "/api/v1/photos/attach/discrepancy",
            json={
                "image_id": str(image_id),
                "entity_type": "fault",
                "entity_id": str(entity_id),
                "notes": "Damaged on arrival"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "attached"

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.photo_handler.PhotoHandler.attach_part_photo")
    def test_attach_part_photo(self, mock_attach, mock_auth, client, user_context):
        """Test attach part photo endpoint."""
        mock_auth.return_value = user_context

        image_id = uuid4()
        part_id = uuid4()
        mock_attach.return_value = {
            "status": "attached",
            "image_id": str(image_id),
            "part_id": str(part_id),
            "photo_type": "catalog"
        }

        response = client.post(
            "/api/v1/photos/attach/part",
            json={
                "image_id": str(image_id),
                "part_id": str(part_id),
                "photo_type": "catalog"
            },
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "attached"


class TestLabelGenerationRoutes:
    """Tests for label generation routes."""

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.label_generation_handler.LabelGenerationHandler.generate_part_labels_pdf")
    def test_generate_part_labels_pdf(self, mock_generate, mock_auth, client, user_context):
        """Test generate part labels PDF endpoint."""
        mock_auth.return_value = user_context

        # Mock PDF bytes
        mock_generate.return_value = b"%PDF-1.4\n..."

        response = client.post(
            "/api/v1/labels/parts/pdf",
            json={"location": "Engine Room"},
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    @patch("src.middleware.auth.get_current_user")
    @patch("src.handlers.label_generation_handler.LabelGenerationHandler.generate_part_qr_only")
    def test_generate_part_qr(self, mock_generate, mock_auth, client, user_context):
        """Test generate part QR code endpoint."""
        mock_auth.return_value = user_context

        part_id = uuid4()
        # Mock PNG bytes
        mock_generate.return_value = b"\x89PNG\r\n..."

        response = client.get(
            f"/api/v1/labels/parts/{part_id}/qr?part_number=MTU-OF-4568",
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
