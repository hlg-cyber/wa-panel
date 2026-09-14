from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app import models
from app.schemas import (
    WabaRequestCreate, WabaRequestOut, WabaRequestMapping, WabaRequestReject,
    WabaRegisterStep1, WabaRegisterStep2, WabaRegisterStep3, WabaRegisterStep4,
)
from app.deps import require_client_admin, require_super_admin
from app.services import meta_api, waba_mapper

router = APIRouter(prefix="/waba-requests", tags=["WABA Requests"])


# ============ KLIEN ============

@router.get("", response_model=List[WabaRequestOut])
def list_my_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    return db.query(models.WabaRequest).filter(
        models.WabaRequest.client_id == current_user.client_id
    ).order_by(models.WabaRequest.id.desc()).all()


@router.post("", response_model=WabaRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: WabaRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    existing = db.query(models.WabaRequest).filter(
        models.WabaRequest.client_id == current_user.client_id,
        models.WabaRequest.phone_number == payload.phone_number,
        models.WabaRequest.status.in_([
            models.WabaRequestStatus.pending,
            models.WabaRequestStatus.approved,
            models.WabaRequestStatus.registering,
        ]),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nomor ini sudah ada di request aktif")

    req = models.WabaRequest(
        client_id=current_user.client_id,
        phone_number=payload.phone_number,
        display_name=payload.display_name,
        notes=payload.notes,
        status=models.WabaRequestStatus.pending,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.post("/{request_id}/cancel", response_model=WabaRequestOut)
def cancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    req = db.query(models.WabaRequest).filter(
        models.WabaRequest.id == request_id,
        models.WabaRequest.client_id == current_user.client_id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    if req.status != models.WabaRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Hanya request pending yang bisa dibatalkan")

    req.status = models.WabaRequestStatus.cancelled
    req.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(req)
    return req


# ============ SUPER ADMIN ============

@router.get("/admin/all", response_model=List[WabaRequestOut])
def list_all_requests(
    status_filter: str = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    query = db.query(models.WabaRequest)
    if status_filter:
        query = query.filter(models.WabaRequest.status == status_filter)
    return query.order_by(models.WabaRequest.id.desc()).all()


@router.get("/admin/api-managers-status")
def api_managers_status(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    return waba_mapper.get_all_api_managers_status(db)


@router.post("/admin/{request_id}/approve", response_model=WabaRequestOut)
async def approve_request(
    request_id: int,
    payload: WabaRequestMapping,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    req = db.query(models.WabaRequest).filter(models.WabaRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    if req.status != models.WabaRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Request sudah diproses")

    api_manager = None
    if payload.auto:
        api_manager = waba_mapper.find_best_api_manager(db)
        if not api_manager:
            raise HTTPException(
                status_code=400,
                detail="Semua API Manager penuh. Tambah API Manager baru atau mapping manual."
            )
    elif payload.api_manager_id:
        api_manager = db.query(models.ApiManager).filter(
            models.ApiManager.id == payload.api_manager_id,
            models.ApiManager.is_active == True,
        ).first()
        if not api_manager:
            raise HTTPException(status_code=404, detail="API Manager tidak ditemukan atau tidak aktif")

        current_count = db.query(models.Waba).filter(
            models.Waba.api_manager_id == api_manager.id
        ).count()
        if current_count >= api_manager.max_waba_slots:
            raise HTTPException(
                status_code=400,
                detail=f"API Manager {api_manager.name} sudah penuh ({current_count}/{api_manager.max_waba_slots})."
            )
    else:
        raise HTTPException(status_code=400, detail="Pilih 'auto' atau 'api_manager_id'")

    # Buat WABA placeholder (belum ada waba_id & phone_number_id — diisi di wizard registrasi)
    waba = models.Waba(
        api_manager_id=api_manager.id,
        client_id=req.client_id,
        display_phone_number=req.phone_number,
        display_name=req.display_name,
        is_active=True,
    )
    db.add(waba)
    db.flush()

    req.status = models.WabaRequestStatus.approved
    req.api_manager_id = api_manager.id
    req.waba_id = waba.id
    req.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(req)
    return req


@router.post("/admin/{request_id}/reject", response_model=WabaRequestOut)
def reject_request(
    request_id: int,
    payload: WabaRequestReject,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    req = db.query(models.WabaRequest).filter(models.WabaRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    if req.status != models.WabaRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Request sudah diproses")

    req.status = models.WabaRequestStatus.rejected
    req.rejection_reason = payload.reason or "Tidak ada alasan"
    req.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(req)
    return req


# ============ WIZARD REGISTRASI WABA ============

@router.post("/admin/{request_id}/register/step1")
async def register_step1(
    request_id: int,
    payload: WabaRegisterStep1,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    """
    Step 1: Daftarkan nomor ke WABA Meta.
    Input: meta_waba_id, verified_name (opsional, default = display_name klien)
    Output: meta_phone_number_id
    """
    req = db.query(models.WabaRequest).filter(models.WabaRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    if not req.api_manager_id:
        raise HTTPException(status_code=400, detail="Request belum di-approve")

    api_manager = db.query(models.ApiManager).filter(
        models.ApiManager.id == req.api_manager_id
    ).first()
    if not api_manager:
        raise HTTPException(status_code=404, detail="API Manager tidak ditemukan")

    # Parse nomor: 62812xxx → cc=62, number=812xxx
    phone = req.phone_number.replace("+", "").strip()
    cc = phone[:2]
    number = phone[2:]

    verified_name = payload.verified_name or req.display_name or f"WA-{req.id}"

    result = await meta_api.register_phone_number(
        api_manager=api_manager,
        meta_waba_id=payload.meta_waba_id,
        cc=cc,
        phone_number=number,
        verified_name=verified_name,
    )

    if not result.get("success"):
        req.registration_error = result.get("error", "Gagal daftar nomor")
        req.status = models.WabaRequestStatus.failed
        db.commit()
        raise HTTPException(status_code=400, detail=result.get("error", "Gagal daftar nomor ke Meta"))

    req.meta_waba_id = payload.meta_waba_id
    req.meta_phone_number_id = result.get("phone_number_id")
    req.status = models.WabaRequestStatus.registering
    req.registration_error = None
    db.commit()
    db.refresh(req)

    return {
        "success": True,
        "meta_phone_number_id": req.meta_phone_number_id,
        "message": "Nomor berhasil didaftarkan. Lanjut ke Step 2: kirim OTP.",
    }


@router.post("/admin/{request_id}/register/step2")
async def register_step2(
    request_id: int,
    payload: WabaRegisterStep2,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    """Step 2: Kirim OTP ke nomor klien."""
    req = db.query(models.WabaRequest).filter(models.WabaRequest.id == request_id).first()
    if not req or not req.meta_phone_number_id:
        raise HTTPException(status_code=400, detail="Step 1 belum selesai")

    api_manager = db.query(models.ApiManager).filter(
        models.ApiManager.id == req.api_manager_id
    ).first()

    result = await meta_api.request_verification_code(
        api_manager=api_manager,
        phone_number_id=req.meta_phone_number_id,
        code_method=payload.code_method,
        language=payload.language,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Gagal kirim OTP"))

    req.otp_sent_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "message": f"OTP dikirim via {payload.code_method}. Minta klien cek SMS/panggilan.",
    }


@router.post("/admin/{request_id}/register/step3")
async def register_step3(
    request_id: int,
    payload: WabaRegisterStep3,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    """Step 3: Verifikasi OTP."""
    req = db.query(models.WabaRequest).filter(models.WabaRequest.id == request_id).first()
    if not req or not req.meta_phone_number_id:
        raise HTTPException(status_code=400, detail="Step 1 belum selesai")

    api_manager = db.query(models.ApiManager).filter(
        models.ApiManager.id == req.api_manager_id
    ).first()

    result = await meta_api.verify_phone_number(
        api_manager=api_manager,
        phone_number_id=req.meta_phone_number_id,
        code=payload.code,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Kode OTP salah"))

    req.otp_verified = True
    db.commit()

    return {
        "success": True,
        "message": "OTP terverifikasi. Lanjut ke Step 4: set PIN 6 digit.",
    }


@router.post("/admin/{request_id}/register/step4")
async def register_step4(
    request_id: int,
    payload: WabaRegisterStep4,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    """Step 4: Registrasi Cloud API + set PIN + auto-subscribe webhook."""
    req = db.query(models.WabaRequest).filter(models.WabaRequest.id == request_id).first()
    if not req or not req.meta_phone_number_id:
        raise HTTPException(status_code=400, detail="Step 1 belum selesai")
    if not req.otp_verified:
        raise HTTPException(status_code=400, detail="OTP belum diverifikasi")
    if len(payload.pin) != 6 or not payload.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN harus 6 digit angka")

    api_manager = db.query(models.ApiManager).filter(
        models.ApiManager.id == req.api_manager_id
    ).first()

    # Register untuk Cloud API
    result = await meta_api.register_phone_for_cloud_api(
        api_manager=api_manager,
        phone_number_id=req.meta_phone_number_id,
        pin=payload.pin,
    )

    if not result.get("success"):
        req.registration_error = result.get("error", "Registrasi gagal")
        db.commit()
        raise HTTPException(status_code=400, detail=result.get("error", "Registrasi ke Meta gagal"))

    # Auto-subscribe WABA ke app
    sub_result = await meta_api.subscribe_waba_to_app_by_id(
        api_manager=api_manager,
        meta_waba_id=req.meta_waba_id,
    )
    sub_ok = sub_result.get("success", False)

    # Update WABA di panel (isi waba_id & phone_number_id)
    if req.waba_id:
        waba = db.query(models.Waba).filter(models.Waba.id == req.waba_id).first()
        if waba:
            waba.waba_id = req.meta_waba_id
            waba.phone_number_id = req.meta_phone_number_id
            waba.is_active = True

    req.pin_set = True
    req.registered_at = datetime.utcnow()
    req.status = models.WabaRequestStatus.registered
    req.registration_error = None
    db.commit()
    db.refresh(req)

    return {
        "success": True,
        "message": "WABA berhasil diregistrasi!" + (" Webhook tersubscribe." if sub_ok else " (Warning: subscribe webhook gagal, coba manual via /wabas/{id}/resubscribe)"),
        "subscribe_ok": sub_ok,
        "subscribe_error": None if sub_ok else sub_result.get("error"),
    }