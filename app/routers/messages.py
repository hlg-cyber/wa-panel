from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
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


# =====================
# CHAT ROOM ENDPOINTS
# =====================

@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    """
    Ambil daftar percakapan unik (group by recipient phone number).
    Menampilkan nomor, pesan terakhir, waktu, dan jumlah pesan belum dibaca.
    """
    cid = current_user.client_id

    # Subquery: ambil id pesan terakhir per recipient
    subq = db.query(
        models.MessageLog.recipient,
        func.max(models.MessageLog.id).label("last_id")
    ).filter(
        models.MessageLog.client_id == cid
    ).group_by(models.MessageLog.recipient).subquery()

    # Join untuk dapat detail pesan terakhir
    results = db.query(models.MessageLog).join(
        subq, models.MessageLog.id == subq.c.last_id
    ).order_by(models.MessageLog.id.desc()).all()

    conversations = []
    for log in results:
        # Hitung total pesan
        total = db.query(func.count(models.MessageLog.id)).filter(
            models.MessageLog.client_id == cid,
            models.MessageLog.recipient == log.recipient,
        ).scalar() or 0

        conversations.append({
            "phone": log.recipient,
            "last_message": log.content,
            "last_direction": log.direction,
            "last_status": log.status,
            "last_time": log.created_at.isoformat() if log.created_at else None,
            "total_messages": total,
        })

    return conversations


@router.get("/conversation/{phone}")
def get_conversation(
    phone: str,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    """Ambil semua pesan dengan nomor tertentu, urut dari yang lama ke baru."""
    cid = current_user.client_id
    messages = db.query(models.MessageLog).filter(
        models.MessageLog.client_id == cid,
        models.MessageLog.recipient == phone,
    ).order_by(models.MessageLog.id.asc()).limit(limit).all()

    return [{
        "id": m.id,
        "waba_id": m.waba_id,
        "recipient": m.recipient,
        "direction": m.direction,
        "message_type": m.message_type,
        "content": m.content,
        "status": m.status,
        "error_message": m.error_message,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m in messages]