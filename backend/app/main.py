# app/main.py
#
# This is the main entry point for the FastAPI application.
# It creates the FastAPI app instance, includes the modular routers,
# and sets up middleware and exception handlers.
#
# The `handler` function is the entry point for AWS Lambda.

from fastapi import FastAPI
from mangum import Mangum

from .routers import auth, users, prescriptions

app = FastAPI(
    title="Prescription App Backend API (Refactored)",
    description="API using AWS Cognito for authentication, with modular routers."
)

# Include the routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(prescriptions.router)

@app.get("/health", tags=["Health Check"])
def health_check():
    """A simple endpoint to confirm the API is running."""
    return {"status": "ok"}

# This handler is the entry point for AWS Lambda
handler = Mangum(app, lifespan="off")
