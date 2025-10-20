import json
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import prescriptions as rx


@pytest.fixture(autouse=True)
def override_auth():
    """Bypass Cognito authorizer for tests.

    The real API gets Cognito claims from API Gateway; here we inject a dummy
    user to exercise only the prescription logic.
    """
    app.dependency_overrides[rx.get_cognito_user_info] = lambda: {"sub": "test-sub"}
    yield
    app.dependency_overrides.clear()


class DummyTable:
    """Minimal stand-in for a DynamoDB Table used by the router.

    We capture the last item written so assertions can verify normalization.
    """
    def __init__(self):
        self.last_item: Dict[str, Any] | None = None

    def put_item(self, Item: Dict[str, Any]):
        self.last_item = Item


def _mock_crud_doctor(monkeypatch):
    """Make the requester a DOCTOR and the target patient a PATIENT.

    This isolates the test to creation logic and data normalization,
    avoiding any dependency on real DynamoDB contents.
    """
    # Requester (doctor)
    monkeypatch.setattr(rx, "db_get_user_by_cognito_sub", lambda sub: {"userId": "doctor-1"})
    # Doctor profile has DOCTOR role; patient profile has PATIENT role
    monkeypatch.setattr(
        rx, "db_get_full_user_profile", lambda uid: {"roles": ["DOCTOR"]} if uid == "doctor-1" else {"roles": ["PATIENT"]}
    )


def test_create_prescription_normalizes_unmapped(monkeypatch):
    """Unmapped free-text medication is accepted and normalized server-side.

    Expectations:
    - code defaults to "UNMAPPED"
    - system defaults to "UNMAPPED" (or SNOMED if later mapped)
    - display falls back to original free text (or name)
    """
    _mock_crud_doctor(monkeypatch)
    dummy = DummyTable()
    monkeypatch.setattr(rx, "prescriptions_table", dummy)

    client = TestClient(app)

    payload = {
        "patientId": "patient-1",
        "expiresAt": "2025-12-31",
        "diagnosis": "Fever",
        "medications": [
            {
                # Unmapped free text (no system/code/display)
                "name": "unknown med 500",
                "dosage": "500 mg",
                "frequency": "1-0-1",
                "duration": "5 days",
                "instructions": "after food"
            }
        ],
    }

    r = client.post("/prescriptions", json=payload)
    assert r.status_code == 201, r.text

    saved = dummy.last_item
    assert saved is not None
    meds = saved["medications"]
    assert len(meds) == 1
    m = meds[0]
    # Server defaults
    assert m["code"] == "UNMAPPED"
    assert m["system"] in ("UNMAPPED", "http://snomed.info/sct")
    assert m["display"] != ""  # display falls back to original/name


def test_create_prescription_preserves_mapped_fields(monkeypatch):
    """Mapped medication preserves SNOMED fields exactly as provided.

    Expectations:
    - code/system/display/original_input are stored unchanged
    - other fields (dosage/frequency/duration) are carried through
    """
    _mock_crud_doctor(monkeypatch)
    dummy = DummyTable()
    monkeypatch.setattr(rx, "prescriptions_table", dummy)

    client = TestClient(app)

    payload = {
        "patientId": "patient-1",
        "expiresAt": "2025-12-31",
        "diagnosis": "Fever",
        "medications": [
            {
                "system": "http://snomed.info/sct",
                "code": "1552821000189108",
                "display": "Crocin Advance (paracetamol) 500 mg oral tablet",
                "original_input": "croc",
                "name": "Crocin Advance (paracetamol) 500 mg oral tablet",
                "dosage": "500 mg",
                "frequency": "1-0-1",
                "duration": "5 days",
                "instructions": None
            }
        ],
    }

    r = client.post("/prescriptions", json=payload)
    assert r.status_code == 201, r.text

    saved = dummy.last_item
    assert saved is not None
    m = saved["medications"][0]
    assert m["code"] == "1552821000189108"
    assert m["system"] == "http://snomed.info/sct"
    assert m["display"].startswith("Crocin Advance")
    assert m["original_input"] == "croc"

