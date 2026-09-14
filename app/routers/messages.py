from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app import models
from app.schemas import SendMessageRequest, SendMessageResponse, MessageLogOut
from app.deps import require_client_admin, require_super_admin
from app.services import meta_api
import json

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    """Kirim pesan dari panel klien."""
    waba = db.query(models.Waba).filter(
        models.Waba.id == payload.waba_id,
        models.Waba.client_id == current_user.client_id,
    ).first()
    if not waba:
        raise HTTPException(status_code=404, detail="WABA tidak ditemukan atau bukan milik Anda")

    if not waba.is_active:
        raise HTTPException(status_code=400, detail="WABA tidak aktif")

    result = None
    content_preview = ""

    if payload.message_type == "text":
        if not payload.text:
            raise HTTPException(status_code=400, detail="Text wajib diisi")
        result = await meta_api.send_text_message(waba, payload.to, payload.text)
        content_preview = payload.text

    elif payload.message_type == "template":
        if not payload.template_name:
            raise HTTPException(status_code=400, detail="Template name wajib diisi")
        result = await meta_api.send_template_message(
            waba, payload.to, payload.template_name,
            payload.template_language or "id", payload.template_params
        )
        content_preview = f"[Template: {payload.template_name}]"

    elif payload.message_type in ("image", "document", "video"):
        if not payload.media_url:
            raise HTTPException(status_code=400, detail="Media URL wajib diisi")
        result = await meta_api.send_media_message(
            waba, payload.to, payload.message_type, payload.media_url, payload.media_caption
        )
        content_preview = f"[{payload.message_type}] {payload.media_url}"

    else:
        raise HTTPException(status_code=400, detail="Tipe pesan tidak didukung")

    # Log
    log = models.MessageLog(
        waba_id=waba.id,
        client_id=current_user.client_id,
        recipient=payload.to,
        direction="outbound",
        message_type=payload.message_type,
        content=content_preview,
        payload=json.dumps(result),
        status="sent" if result.get("success") else "failed",
        error_message=None if result.get("success") else result.get("error"),
        meta_message_id=result.get("message_id"),
    )
    db.add(log)
    db.commit()

    if not result.get("success"):
        return SendMessageResponse(success=False, error=result.get("error"))

    return SendMessageResponse(success=True, message_id=result.get("message_id"))


@router.get("/logs", response_model=List[MessageLogOut])
def list_logs(
    waba_id: Optional[int] = None,
    direction: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    query = db.query(models.MessageLog).filter(
        models.MessageLog.client_id == current_user.client_id
    )
    if waba_id:
        query = query.filter(models.MessageLog.waba_id == waba_id)
    if direction:
        query = query.filter(models.MessageLog.direction == direction)
    return query.order_by(models.MessageLog.id.desc()).limit(limit).all()