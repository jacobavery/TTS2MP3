"""File upload and text extraction route."""

import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile

from engine.readers import read_file, epub_metadata, pdf_metadata
from server.config import MAX_UPLOAD_SIZE

router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED_EXTENSIONS = {".txt", ".rtf", ".epub", ".pdf", ".md"}


@router.post("/upload")
async def upload_file(file: UploadFile):
    from server.app import app_state

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit")

    # Write to temp file for processing
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)

        text = read_file(tmp_path, clean_pdf=True, cache_dir=app_state["cache_dir"])

        metadata = {}
        if ext == ".epub":
            try:
                metadata = epub_metadata(tmp_path)
            except Exception:
                pass
        elif ext == ".pdf":
            try:
                metadata = pdf_metadata(tmp_path)
            except Exception:
                pass

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    words = len(text.split())
    return {
        "text": text,
        "filename": file.filename,
        "words": words,
        "chars": len(text),
        "metadata": metadata,
    }
