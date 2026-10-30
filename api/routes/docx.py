"""Download a local Word file written by the docx agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from tools.docx.store import DOCX_MEDIA, export_file

router = APIRouter()


@router.get("/docx/{document_id}/file")
async def download_docx(document_id: str) -> FileResponse:
    try:
        path, filename = export_file(document_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type=DOCX_MEDIA, filename=filename)
