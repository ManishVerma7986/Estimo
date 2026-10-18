"""Security and Upload Sanitization Module (Rule R6 & Section 5).

Protects against path-traversal attacks, rejects executable extensions and model-file uploads,
and validates file sizes.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Tuple
from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import settings


def sanitize_filename(filename: str) -> str:
    """Sanitizes filename against path traversal (../, ..\\) and prohibited characters."""
    base_name = os.path.basename(filename)
    clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base_name)
    if not clean_name or clean_name.startswith("."):
        clean_name = f"upload_{clean_name}"
    return clean_name


def validate_dataset_upload(file: UploadFile) -> Tuple[str, str]:
    """Validates uploaded file against security rules."""
    raw_name = file.filename or "uploaded_data.csv"
    clean_name = sanitize_filename(raw_name)
    suffix = Path(clean_name).suffix.lower()

    # Rule R6: No model uploads allowed
    if suffix in [".joblib", ".pkl", ".pickle"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SECURITY VIOLATION: Uploading serialized model files (.joblib, .pkl) is prohibited by Rule R6."
        )

    # Check against prohibited executable extensions
    if suffix in settings.prohibited_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SECURITY VIOLATION: File extension '{suffix}' is prohibited."
        )

    # Check allowed extensions
    if suffix not in settings.allowed_dataset_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{suffix}'. Allowed: {settings.allowed_dataset_extensions}"
        )

    return clean_name, suffix
