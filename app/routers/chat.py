from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
from app.database import get_db
from app import models
from app.schemas import (
    ChatSessionCreate, ChatSessionOut, ChatSessionDetail,
    ChatMessageCreate, ChatMessageOut, CompleteWabaRequest, ChecklistUpdate,
)
from app.deps import require_client_admin, require_super_admin
from app.services import meta_api

router = APIRouter(prefix="/chat", tags=["Chat CS"])


# =====================
# WORKFLOW DEFINITION
# =====================
WORKFLOW_STEPS = [
    {"key": "confirm", "label": "Konfirmasi Chat Ditangani", "desc": "Balas klien & tandai sedang diproses"},
    {"key": "link_waba", "label": "Link a WABA di Meta Business Suite", "desc": "Buat/link WABA klien di Meta Business Suite"},
    {"key": "assign_assets", "label": "Assign Assets ke System User", "desc": "Beri akses WABA + App ke System User"},
    {"key": "request_otp", "label": "Minta Kode OTP ke Klien", "desc": "Kirim permintaan OTP via chat"},
    {"key": "get_ids", "label": "Salin WABA ID & Phone Number ID", "desc": "Ambil kedua ID dari Meta / Graph API"},
    {"key": "activate", "label": "Aktifkan WABA di Panel", "desc": "Submit WABA & aktifkan"},
]


def _parse_checklist(raw: Optional[str]) -> dict:
    if not raw:
        return {step["key"]: False for step in WORKFLOW_STEPS}
    try:
        data = json.loads(raw)
        for step in WORKFLOW_STEPS:
            data.setdefault(step["key"], False)
        return data
    except Exception:
        return {step["key"]: False for step in WORKFLOW_STEPS}


def _build_session_detail(session, messages, client_name=None, client_email=None, checklist=None):
    """Build ChatSessionDetail manual (hindari model_validate yang crash karena checklist_state string)."""
    return ChatSessionDetail(
        id=session.id,
        client_id=session.client_id,
        topic=session.topic,
        phone_number=session.phone_number,
        display_name=session.display_name,
        status=session.status,
        otp_code=session.otp_code,
        otp_requested_at=session.otp_requested_at,
        meta_waba_id=session.meta_waba_id,
        meta_phone_number_id=session.meta_phone_number_id,
        waba_id=session.waba_id,
        api_manager_id=session.api_manager_id,
        rejection_reason=session.rejection_reason,
        created_at=session.created_at,
        completed_at=session.completed_at,
        messages=[ChatMessageOut.model_validate(m) for m in messages],
        client_name=client_name,
        client_email=client_email,
        checklist_state=checklist,
    )


# ============ KLIEN ============

@router.get("/my-sessions", response_model=List[ChatSessionOut])
def my_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    return db.query(models.ChatSession).filter(
        models.ChatSession.client_id == current_user.client_id
    ).order_by(models.ChatSession.id.desc()).all()


@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    existing = db.query(models.ChatSession).filter(
        models.ChatSession.client_id == current_user.client_id,
        models.ChatSession.phone_number == payload.phone_number,
        models.ChatSession.status.in_([
            models.ChatSessionStatus.waiting_admin,
            models.ChatSessionStatus.in_progress,
            models.ChatSessionStatus.waiting_otp,
        ]),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Anda masih memiliki sesi aktif untuk nomor ini.")

    session = models.ChatSession(
        client_id=current_user.client_id,
        topic=payload.topic,
        phone_number=payload.phone_number,
        display_name=payload.display_name,
        status=models.ChatSessionStatus.waiting_admin,
        checklist_state=json.dumps({step["key"]: False for step in WORKFLOW_STEPS}),
    )
    db.add(session)
    db.flush()

    sys_msg = models.ChatMessage(
        session_id=session.id,
        sender_role="system",
        message_type="system",
        content=f"Topik: Tambah WABA Baru\nNomor yang diajukan: {payload.phone_number}",
    )
    db.add(sys_msg)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def get_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    session = db.query(models.ChatSession).filter(
        models.ChatSession.id == session_id,
        models.ChatSession.client_id == current_user.client_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id,
        models.ChatMessage.sender_role == "admin",
        models.ChatMessage.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()})
    db.commit()

    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id
    ).order_by(models.ChatMessage.id.asc()).all()

    return _build_session_detail(session, messages, checklist=None)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageOut)
def send_message_client(
    session_id: int,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    session = db.query(models.ChatSession).filter(
        models.ChatSession.id == session_id,
        models.ChatSession.client_id == current_user.client_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    if session.status in (models.ChatSessionStatus.completed, models.ChatSessionStatus.rejected, models.ChatSessionStatus.closed):
        raise HTTPException(status_code=400, detail="Sesi sudah ditutup")

    msg = models.ChatMessage(
        session_id=session_id,
        sender_role="client",
        sender_id=current_user.id,
        message_type="text",
        content=payload.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/my-unread-count")
def my_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    count = db.query(models.ChatMessage).join(
        models.ChatSession, models.ChatMessage.session_id == models.ChatSession.id
    ).filter(
        models.ChatSession.client_id == current_user.client_id,
        models.ChatMessage.sender_role == "admin",
        models.ChatMessage.read_at.is_(None),
    ).count()
    return {"unread": count}


# ============ SUPER ADMIN ============

@router.get("/admin/workflow-definition")
def get_workflow_definition(
    _: models.User = Depends(require_super_admin),
):
    return WORKFLOW_STEPS


@router.get("/admin/sessions", response_model=List[ChatSessionOut])
def admin_list_sessions(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    query = db.query(models.ChatSession)
    if status_filter:
        query = query.filter(models.ChatSession.status == status_filter)
    return query.order_by(models.ChatSession.id.desc()).all()


@router.get("/admin/sessions/{session_id}", response_model=ChatSessionDetail)
def admin_get_session(
    session_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id,
        models.ChatMessage.sender_role == "client",
        models.ChatMessage.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()})
    db.commit()

    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id
    ).order_by(models.ChatMessage.id.asc()).all()

    client = db.query(models.Client).filter(models.Client.id == session.client_id).first()
    client_admin = db.query(models.User).filter(
        models.User.client_id == session.client_id,
        models.User.role == "client_admin",
    ).first()

    return _build_session_detail(
        session, messages,
        client_name=client.name if client else None,
        client_email=client_admin.email if client_admin else None,
        checklist=_parse_checklist(session.checklist_state),
    )


@router.post("/admin/sessions/{session_id}/messages", response_model=ChatMessageOut)
def admin_send_message(
    session_id: int,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_super_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    msg = models.ChatMessage(
        session_id=session_id,
        sender_role="admin",
        sender_id=current_user.id,
        message_type="text",
        content=payload.content,
    )
    db.add(msg)

    if session.status == models.ChatSessionStatus.waiting_admin:
        session.status = models.ChatSessionStatus.in_progress

    checklist = _parse_checklist(session.checklist_state)
    if not checklist.get("confirm"):
        checklist["confirm"] = True
        session.checklist_state = json.dumps(checklist)

    db.commit()
    db.refresh(msg)
    return msg


@router.post("/admin/sessions/{session_id}/checklist", response_model=ChatSessionDetail)
def update_checklist(
    session_id: int,
    payload: ChecklistUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    valid_keys = [s["key"] for s in WORKFLOW_STEPS]
    if payload.step_key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Step tidak valid: {payload.step_key}")

    checklist = _parse_checklist(session.checklist_state)
    checklist[payload.step_key] = payload.completed
    session.checklist_state = json.dumps(checklist)

    if payload.step_key == "confirm" and payload.completed:
        if session.status == models.ChatSessionStatus.waiting_admin:
            session.status = models.ChatSessionStatus.in_progress
    elif payload.step_key == "request_otp" and payload.completed:
        session.status = models.ChatSessionStatus.waiting_otp

    db.commit()
    db.refresh(session)

    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id
    ).order_by(models.ChatMessage.id.asc()).all()
    client = db.query(models.Client).filter(models.Client.id == session.client_id).first()
    client_admin = db.query(models.User).filter(
        models.User.client_id == session.client_id,
        models.User.role == "client_admin",
    ).first()

    return _build_session_detail(
        session, messages,
        client_name=client.name if client else None,
        client_email=client_admin.email if client_admin else None,
        checklist=checklist,
    )


@router.post("/admin/sessions/{session_id}/action/request-otp", response_model=ChatMessageOut)
def admin_request_otp(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_super_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    content = (
        "📱 *Silakan kirim kode OTP yang Anda terima*\n\n"
        "Kami telah mendaftarkan nomor Anda ke WhatsApp Business. "
        "Anda akan menerima kode verifikasi 6 digit melalui SMS atau panggilan suara. "
        "Silakan balas dengan kode tersebut di chat ini."
    )

    msg = models.ChatMessage(
        session_id=session_id,
        sender_role="admin",
        sender_id=current_user.id,
        message_type="action",
        action_type="request_otp",
        content=content,
    )
    db.add(msg)

    session.status = models.ChatSessionStatus.waiting_otp
    session.otp_requested_at = datetime.utcnow()

    checklist = _parse_checklist(session.checklist_state)
    checklist["request_otp"] = True
    session.checklist_state = json.dumps(checklist)

    db.commit()
    db.refresh(msg)
    return msg


@router.post("/admin/sessions/{session_id}/complete")
async def admin_complete_waba(
    session_id: int,
    payload: CompleteWabaRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    api_manager = db.query(models.ApiManager).filter(
        models.ApiManager.id == payload.api_manager_id,
        models.ApiManager.is_active == True,
    ).first()
    if not api_manager:
        raise HTTPException(status_code=404, detail="API Manager tidak ditemukan")

    current_count = db.query(models.Waba).filter(
        models.Waba.api_manager_id == api_manager.id
    ).count()
    if current_count >= api_manager.max_waba_slots:
        raise HTTPException(
            status_code=400,
            detail=f"API Manager {api_manager.name} sudah penuh ({current_count}/{api_manager.max_waba_slots})"
        )

    waba = models.Waba(
        api_manager_id=api_manager.id,
        client_id=session.client_id,
        waba_id=payload.meta_waba_id,
        phone_number_id=payload.meta_phone_number_id,
        display_phone_number=session.phone_number,
        display_name=session.display_name,
        is_active=True,
    )
    db.add(waba)
    db.flush()

    subscribe_result = await meta_api.subscribe_waba_to_app(waba)
    subscribe_ok = subscribe_result.get("success", False)

    session.meta_waba_id = payload.meta_waba_id
    session.meta_phone_number_id = payload.meta_phone_number_id
    session.api_manager_id = api_manager.id
    session.waba_id = waba.id
    session.otp_code = payload.otp_code
    session.status = models.ChatSessionStatus.completed
    session.completed_at = datetime.utcnow()

    checklist = {step["key"]: True for step in WORKFLOW_STEPS}
    session.checklist_state = json.dumps(checklist)

    complete_msg = models.ChatMessage(
        session_id=session_id,
        sender_role="system",
        message_type="system",
        action_type="waba_linked",
        content=f"✅ WABA berhasil terhubung ke akun Anda!\n\nNomor: {session.phone_number}\nWABA ID: {payload.meta_waba_id}\n\nAnda sekarang dapat menggunakan WhatsApp API.",
    )
    db.add(complete_msg)
    db.commit()
    db.refresh(session)

    return {
        "success": True,
        "waba_id": waba.id,
        "subscribe_ok": subscribe_ok,
        "subscribe_error": None if subscribe_ok else subscribe_result.get("error"),
        "message": "WABA berhasil diaktifkan" + (" dan webhook tersubscribe." if subscribe_ok else ". Warning: subscribe webhook gagal."),
    }


@router.post("/admin/sessions/{session_id}/reject")
def admin_reject(
    session_id: int,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    session.status = models.ChatSessionStatus.rejected
    session.rejection_reason = payload.content
    session.completed_at = datetime.utcnow()

    msg = models.ChatMessage(
        session_id=session_id,
        sender_role="system",
        message_type="system",
        action_type="rejected",
        content=f"❌ Permintaan ditolak.\n\nAlasan: {payload.content}",
    )
    db.add(msg)
    db.commit()
    return {"success": True}


@router.get("/admin/unread-count")
def admin_unread_count(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    count = db.query(models.ChatMessage).filter(
        models.ChatMessage.sender_role == "client",
        models.ChatMessage.read_at.is_(None),
    ).count()
    return {"unread": count}