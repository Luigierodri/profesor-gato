"""
gcp_client.py — Vertex AI auth helper
Centraliza autenticación y construcción de URLs para Vertex AI.
Usa Application Default Credentials (gcloud auth application-default login).
"""

import os
import google.auth
import google.auth.transport.requests

_creds = None


def _get_creds():
    global _creds
    if _creds is None or not _creds.valid:
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        _creds = creds
    elif _creds.expired:
        _creds.refresh(google.auth.transport.requests.Request())
    return _creds


def vertex_headers() -> dict:
    """Authorization header con Bearer token fresco."""
    return {
        "Authorization": f"Bearer {_get_creds().token}",
        "Content-Type": "application/json",
    }


def vertex_url(model: str, method: str) -> str:
    """URL del endpoint de Vertex AI para un modelo y método dados."""
    project  = os.getenv("GOOGLE_CLOUD_PROJECT", "profesor-gato-prod")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    base = f"https://{location}-aiplatform.googleapis.com/v1"
    return f"{base}/projects/{project}/locations/{location}/publishers/google/models/{model}:{method}"


def vertex_operation_url(operation_name: str) -> str:
    """URL de polling para una long-running operation de Vertex AI."""
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    return f"https://{location}-aiplatform.googleapis.com/v1/{operation_name}"
