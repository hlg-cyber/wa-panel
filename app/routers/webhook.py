from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.config import settings
import json

router = APIRouter(prefix="/webhook", tags=["Webhook"])


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Verifikasi webhook saat setup di Meta."""
    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        print("✅ WEBHOOK VERIFIED")
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """Terima semua event dari Meta (pesan masuk, status, dll)."""
    try:
        body = await request.json()
        print(f"📩 Webhook received: {json.dumps(body)[:500]}")

        if body.get("object") != "whatsapp_business_account":
            return {"status": "ignored"}

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                field = change.get("field")

                if field == "messages":
                    _handle_messages(value, db)
                elif field == "message_template_status_update":
                    _handle_template_status(value, db)

        return {"status": "ok"}
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {"status": "error", "message": str(e)}


def _handle_messages(value: dict, db: Session):
    """Handle pesan masuk & status update."""
    metadata = value.get("metadata", {})
    phone_number_id = metadata.get("phone_number_id")
    display_phone = metadata.get("display_phone_number")

    # Cari WABA berdasarkan phone_number_id
    waba = db.query(models.Waba).filter(
        models.Waba.phone_number_id == phone_number_id
    ).first()

    if not waba:
        print(f"⚠️  WABA tidak ditemukan untuk phone_number_id: {phone_number_id}")
        return

    # 1. Pesan masuk
    for msg in value.get("messages", []):
        msg_id = msg.get("id")
        from_number = msg.get("from")
        msg_type = msg.get("type", "text")
        content = ""

        if msg_type == "text":
            content = msg.get("text", {}).get("body", "")
        elif msg_type == "button":
            content = msg.get("button", {}).get("text", "")
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if "button_reply" in interactive:
                content = interactive["button_reply"].get("title", "")
            elif "list_reply" in interactive:
                content = interactive["list_reply"].get("title", "")
        else:
            content = f"[{msg_type}]"

        log = models.MessageLog(
            waba_id=waba.id,
            client_id=waba.client_id,
            recipient=from_number,
            direction="inbound",
            message_type=msg_type,
            content=content,
            payload=json.dumps(msg),
            status="received",
            meta_message_id=msg_id,
        )
        db.add(log)
        print(f"📥 Pesan masuk dari {from_number}: {content}")

    # 2. Status update (sent, delivered, read, failed)
    for status_update in value.get("statuses", []):
        msg_id = status_update.get("id")
        status_val = status_update.get("status")
        recipient = status_update.get("recipient_id")
        errors = status_update.get("errors", [])

        # Cari log dengan meta_message_id
        log = db.query(models.MessageLog).filter(
            models.MessageLog.meta_message_id == msg_id
        ).first()

        if log:
            log.status = status_val
            if errors:
                log.error_message = json.dumps(errors)
            print(f"📊 Status update: {msg_id} → {status_val}")

            # Update broadcast counters
            if log.broadcast_id:
                broadcast = db.query(models.Broadcast).filter(
                    models.Broadcast.id == log.broadcast_id
                ).first()
                if broadcast:
                    if status_val == "delivered":
                        broadcast.total_delivered += 1
                    elif status_val == "read":
                        broadcast.total_read += 1
                    elif status_val == "failed":
                        broadcast.total_failed += 1

    db.commit()


def _handle_template_status(value: dict, db: Session):
    """Handle update status template dari Meta."""
    event = value.get("event")
    template_name = value.get("message_template_name")
    reason = value.get("reason", "")

    template = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.name == template_name
    ).first()

    if template:
        if event == "APPROVED":
            template.status = models.TemplateStatus.approved
        elif event == "REJECTED":
            template.status = models.TemplateStatus.rejected
            template.rejection_reason = reason
        elif event == "PENDING":
            template.status = models.TemplateStatus.pending
        db.commit()
        print(f"📋 Template {template_name}: {event}")