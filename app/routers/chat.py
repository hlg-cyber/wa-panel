from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app import models
from app.schemas import (
    ChatSessionCreate, ChatSessionOut, ChatSessionDetail,
    ChatMessageCreate, ChatMessageOut, CompleteWabaRequest,
)
from app.deps import require_client_admin, require_super_admin
from app.services import meta_api

router = APIRouter(prefix="/chat", tags=["Chat CS"])


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
    """Klien buat sesi chat baru (misalnya: ajukan tambah WABA)."""
    # Cek apakah ada session aktif untuk nomor ini
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
        raise HTTPException(
            status_code=400,
            detail="Anda masih memiliki sesi aktif untuk nomor ini. Lanjutkan chat yang ada."
        )

    session = models.ChatSession(
        client_id=current_user.client_id,
        topic=payload.topic,
        phone_number=payload.phone_number,
        display_name=payload.display_name,
        status=models.ChatSessionStatus.waiting_admin,
    )
    db.add(session)
    db.flush()

    # System message otomatis
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

    # Mark all admin messages as read
    db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id,
        models.ChatMessage.sender_role == "admin",
        models.ChatMessage.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()})
    db.commit()

    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id
    ).order_by(models.ChatMessage.id.asc()).all()

    result = ChatSessionDetail.model_validate(session)
    result.messages = [ChatMessageOut.model_validate(m) for m in messages]
    return result


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

    # Kalau status waiting_otp dan klien kirim pesan — tetap text
    # (admin yang interpretasi manual, bukan sistem)
    msg = models.ChatMessage(
        session_id=session_id,
        sender_role="client",
        sender_id=current_user.id,
        message_type="text",
        content=payload.content,
    )
    db.add(msg)

    # Kalau status waiting_admin → ubah ke in_progress (admin lihat ada pesan klien)
    # (biarkan status waiting_admin sampai admin balas — hanya system yang deteksi)

    db.commit()
    db.refresh(msg)
    return msg


@router.get("/my-unread-count")
def my_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    """Hitung pesan admin yang belum dibaca klien."""
    count = db.query(models.ChatMessage).join(
        models.ChatSession, models.ChatMessage.session_id == models.ChatSession.id
    ).filter(
        models.ChatSession.client_id == current_user.client_id,
        models.ChatMessage.sender_role == "admin",
        models.ChatMessage.read_at.is_(None),
    ).count()
    return {"unread": count}


# ============ SUPER ADMIN ============

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

    # Mark client messages as read
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

    result = ChatSessionDetail.model_validate(session)
    result.messages = [ChatMessageOut.model_validate(m) for m in messages]
    result.client_name = client.name if client else None
    result.client_email = client_admin.email if client_admin else None
    return result


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

    # Update status ke in_progress kalau masih waiting_admin
    if session.status == models.ChatSessionStatus.waiting_admin:
        session.status = models.ChatSessionStatus.in_progress

    db.commit()
    db.refresh(msg)
    return msg


@router.post("/admin/sessions/{session_id}/action/request-otp", response_model=ChatMessageOut)
def admin_request_otp(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_super_admin),
):
    """Admin klik tombol 'Minta Kode OTP' — sistem kirim pesan template."""
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

    db.commit()
    db.refresh(msg)
    return msg


@router.post("/admin/sessions/{session_id}/complete")
async def admin_complete_waba(
    session_id: int,
    payload: CompleteWabaRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_super_admin),
):
    """
    Admin menyelesaikan WABA.
    Input: meta_waba_id, meta_phone_number_id, api_manager_id, otp_code (opsional)
    Sistem auto:
    - Buat WABA di panel
    - Subscribe webhook ke Meta
    - Update session ke completed
    - Kirim system message ke klien
    """
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")

    api_manager = db.query(models.ApiManager).filter(
        models.ApiManager.id == payload.api_manager_id,
        models.ApiManager.is_active == True,
    ).first()
    if not api_manager:
        raise HTTPException(status_code=404, detail="API Manager tidak ditemukan")

    # Cek slot
    current_count = db.query(models.Waba).filter(
        models.Waba.api_manager_id == api_manager.id
    ).count()
    if current_count >= api_manager.max_waba_slots:
        raise HTTPException(
            status_code=400,
            detail=f"API Manager {api_manager.name} sudah penuh ({current_count}/{api_manager.max_waba_slots})"
        )

    # Buat WABA di panel
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

    # Auto-subscribe WABA ke Meta
    subscribe_result = await meta_api.subscribe_waba_to_app(waba)
    subscribe_ok = subscribe_result.get("success", False)

    # Update session
    session.meta_waba_id = payload.meta_waba_id
    session.meta_phone_number_id = payload.meta_phone_number_id
    session.api_manager_id = api_manager.id
    session.waba_id = waba.id
    session.otp_code = payload.otp_code
    session.status = models.ChatSessionStatus.completed
    session.completed_at = datetime.utcnow()

    # Kirim system message penutup
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
        "message": "WABA berhasil diaktifkan" + (" dan webhook tersubscribe." if subscribe_ok else ". Warning: subscribe webhook gagal, coba manual."),
    }


@router.post("/admin/sessions/{session_id}/reject")
def admin_reject(
    session_id: int,
    payload: ChatMessageCreate,   # pakai content sebagai alasan
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_super_admin),
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
    """Hitung pesan klien yang belum dibaca admin."""
    count = db.query(models.ChatMessage).filter(
        models.ChatMessage.sender_role == "client",
        models.ChatMessage.read_at.is_(None),
    ).count()
    return {"unread": count}