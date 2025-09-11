import os
import sys

# --- Set dummy environment variables for testing ---
# This must be done BEFORE importing the FastAPI app
os.environ['COGNITO_REGION'] = "us-east-1"
os.environ['COGNITO_USERPOOL_ID'] = "us-east-1_dummy"
os.environ['PATIENT_APP_CLIENT_ID'] = "dummy_patient_client_id"
os.environ['DOCTOR_APP_CLIENT_ID'] = "dummy_doctor_client_id"
os.environ['API_JWT_SECRET_NAME'] = "dummy_secret_name"
os.environ['API_JWT_SECRET'] = "a_super_secret_key_for_testing"
# --- End environment variable setup ---


# Add the project root to the path to allow for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check():
    """
    Tests the /health endpoint to ensure the server is running.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
