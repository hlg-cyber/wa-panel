from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models
from app.schemas import WabaRequestCreate, WabaRequestOut, WabaRequestMapping, WabaRequestReject
from app.deps import require_client_admin, require_super_admin
from app.services import meta_api, waba_mapper
from datetime import datetime

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
    # Cek apakah nomor sudah pernah diajukan dan masih pending
    existing = db.query(models.WabaRequest).filter(
        models.WabaRequest.client_id == current_user.client_id,
        models.WabaRequest.phone_number == payload.phone_number,
        models.WabaRequest.status == models.WabaRequestStatus.pending,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nomor ini sudah ada di request pending")

    # Cek apakah nomor sudah terdaftar sebagai WABA aktif
    existing_waba = db.query(models.Waba).filter(
        models.Waba.display_phone_number == payload.phone_number,
        models.Waba.client_id == current_user.client_id,
    ).first()
    if existing_waba:
        raise HTTPException(status_code=400, detail="Nomor ini sudah terdaftar sebagai WABA")

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
    """Return status semua API Manager + slot."""
    return waba_mapper.get_all_api_managers_status(db)


@router.post("/admin/{request_id}/approve", response_model=WabaRequestOut)
async def approve_request(
    request_id: int,
    payload: WabaRequestMapping,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    """
    Approve request WABA.
    - Kalau payload.auto = True: auto-map ke API Manager dengan slot kosong
    - Kalau payload.api_manager_id diisi: manual map
    - waba_id & phone_number_id dari payload (opsional, diisi Super Admin setelah setup di Meta)
    """
    req = db.query(models.WabaRequest).filter(models.WabaRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    if req.status != models.WabaRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Request sudah diproses")

    # Tentukan API Manager
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

        # Cek slot
        current_count = db.query(models.Waba).filter(
            models.Waba.api_manager_id == api_manager.id
        ).count()
        if current_count >= api_manager.max_waba_slots:
            raise HTTPException(
                status_code=400,
                detail=f"API Manager {api_manager.name} sudah penuh ({current_count}/{api_manager.max_waba_slots}). Override dengan menaikkan max_waba_slots."
            )
    else:
        raise HTTPException(status_code=400, detail="Pilih 'auto' atau 'api_manager_id'")

    # Buat WABA baru
    waba = models.Waba(
        api_manager_id=api_manager.id,
        client_id=req.client_id,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        display_phone_number=req.phone_number,
        display_name=req.display_name,
        is_active=True,
    )
    db.add(waba)
    db.flush()

    # Update request
    req.status = models.WabaRequestStatus.approved
    req.api_manager_id = api_manager.id
    req.waba_id = waba.id
    req.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(req)

    # Auto-subscribe WABA ke Meta (kalau waba_id & phone_number_id sudah ada)
    if waba.waba_id and waba.phone_number_id:
        try:
            await meta_api.subscribe_waba_to_app(waba)
        except Exception as e:
            print(f"⚠️  Auto-subscribe gagal: {e}")

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