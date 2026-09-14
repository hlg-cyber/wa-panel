from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db, SessionLocal
from app import models
from app.schemas import BroadcastCreate, BroadcastOut
from app.deps import require_client_admin
from app.services import meta_api
import asyncio
import json

router = APIRouter(prefix="/broadcasts", tags=["Broadcasts"])


@router.get("", response_model=List[BroadcastOut])
def list_broadcasts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    return db.query(models.Broadcast).filter(
        models.Broadcast.client_id == current_user.client_id
    ).order_by(models.Broadcast.id.desc()).all()


@router.post("", response_model=BroadcastOut)
async def create_broadcast(
    payload: BroadcastCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    waba = db.query(models.Waba).filter(
        models.Waba.id == payload.waba_id,
        models.Waba.client_id == current_user.client_id,
    ).first()
    if not waba:
        raise HTTPException(status_code=404, detail="WABA tidak ditemukan")

    # Kumpulkan recipients
    recipients = []
    if payload.recipients:
        recipients.extend([r.strip() for r in payload.recipients if r.strip()])

    if payload.use_contacts:
        contacts = db.query(models.Contact).filter(
            models.Contact.client_id == current_user.client_id
        ).all()
        recipients.extend([c.phone_number for c in contacts])

    # Dedupe
    recipients = list(set(recipients))

    if not recipients:
        raise HTTPException(status_code=400, detail="Tidak ada recipient")

    broadcast = models.Broadcast(
        client_id=current_user.client_id,
        waba_id=payload.waba_id,
        name=payload.name,
        message_type=payload.message_type,
        message_body=payload.message_body,
        template_name=payload.template_name,
        status=models.BroadcastStatus.sending,
        total_recipients=len(recipients),
    )
    db.add(broadcast)
    db.commit()
    db.refresh(broadcast)

    # Kirim di background
    background_tasks.add_task(
        _send_broadcast_bg,
        broadcast.id,
        recipients,
    )

    return broadcast


async def _send_broadcast_bg(broadcast_id: int, recipients: List[str]):
    """Kirim broadcast di background."""
    db = SessionLocal()
    try:
        broadcast = db.query(models.Broadcast).filter(models.Broadcast.id == broadcast_id).first()
        if not broadcast:
            return

        waba = db.query(models.Waba).filter(models.Waba.id == broadcast.waba_id).first()
        if not waba:
            broadcast.status = models.BroadcastStatus.failed
            db.commit()
            return

        sent_count = 0
        failed_count = 0

        for phone in recipients:
            try:
                if broadcast.message_type == "text":
                    result = await meta_api.send_text_message(waba, phone, broadcast.message_body)
                elif broadcast.message_type == "template":
                    result = await meta_api.send_template_message(
                        waba, phone, broadcast.template_name or "", "id"
                    )
                else:
                    result = {"success": False, "error": "Unsupported type"}

                if result.get("success"):
                    sent_count += 1
                    log_status = "sent"
                    error_msg = None
                else:
                    failed_count += 1
                    log_status = "failed"
                    error_msg = result.get("error")

                log = models.MessageLog(
                    waba_id=waba.id,
                    client_id=broadcast.client_id,
                    broadcast_id=broadcast.id,
                    recipient=phone,
                    direction="outbound",
                    message_type=broadcast.message_type,
                    content=broadcast.message_body,
                    status=log_status,
                    error_message=error_msg,
                    meta_message_id=result.get("message_id"),
                )
                db.add(log)
                db.commit()

                # Rate limit kecil agar tidak kena spam detection
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"❌ Broadcast error to {phone}: {e}")
                failed_count += 1
                continue

        broadcast.total_sent = sent_count
        broadcast.total_failed = failed_count
        broadcast.status = models.BroadcastStatus.done
        db.commit()
        print(f"✅ Broadcast #{broadcast_id} selesai: {sent_count} sent, {failed_count} failed")

    except Exception as e:
        print(f"❌ Broadcast #{broadcast_id} error: {e}")
    finally:
        db.close()


@router.get("/{broadcast_id}", response_model=BroadcastOut)
def get_broadcast(
    broadcast_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    broadcast = db.query(models.Broadcast).filter(
        models.Broadcast.id == broadcast_id,
        models.Broadcast.client_id == current_user.client_id,
    ).first()
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast tidak ditemukan")
    return broadcast


@router.get("/{broadcast_id}/logs")
def broadcast_logs(
    broadcast_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    broadcast = db.query(models.Broadcast).filter(
        models.Broadcast.id == broadcast_id,
        models.Broadcast.client_id == current_user.client_id,
    ).first()
    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast tidak ditemukan")

    logs = db.query(models.MessageLog).filter(
        models.MessageLog.broadcast_id == broadcast_id
    ).order_by(models.MessageLog.id.desc()).all()

    return [{
        "id": l.id,
        "recipient": l.recipient,
        "status": l.status,
        "error_message": l.error_message,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    } for l in logs]