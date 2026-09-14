from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models
from app.schemas import ApiManagerCreate, ApiManagerUpdate, ApiManagerOut
from app.deps import require_super_admin
from app.security import encrypt_token
from app.services import waba_mapper

router = APIRouter(prefix="/api-managers", tags=["API Manager"])


@router.get("", response_model=List[ApiManagerOut])
def list_api_managers(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    return db.query(models.ApiManager).order_by(models.ApiManager.id.desc()).all()


@router.get("/status")
def list_api_managers_with_status(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    """List API Manager + slot info (untuk auto-mapping UI)."""
    return waba_mapper.get_all_api_managers_status(db)


@router.get("/{api_manager_id}", response_model=ApiManagerOut)
def get_api_manager(
    api_manager_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.ApiManager).filter(models.ApiManager.id == api_manager_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="API Manager tidak ditemukan")
    return obj


@router.post("", response_model=ApiManagerOut, status_code=status.HTTP_201_CREATED)
def create_api_manager(
    payload: ApiManagerCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = models.ApiManager(
        name=payload.name,
        app_id=payload.app_id,
        app_secret_encrypted=encrypt_token(payload.app_secret),
        access_token_encrypted=encrypt_token(payload.access_token),
        business_manager_id=payload.business_manager_id,
        max_waba_slots=payload.max_waba_slots,
        client_id=payload.client_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{api_manager_id}", response_model=ApiManagerOut)
def update_api_manager(
    api_manager_id: int,
    payload: ApiManagerUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.ApiManager).filter(models.ApiManager.id == api_manager_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="API Manager tidak ditemukan")

    if payload.name is not None:
        obj.name = payload.name
    if payload.business_manager_id is not None:
        obj.business_manager_id = payload.business_manager_id
    if payload.app_secret:
        obj.app_secret_encrypted = encrypt_token(payload.app_secret)
    if payload.access_token:
        obj.access_token_encrypted = encrypt_token(payload.access_token)
    if payload.max_waba_slots is not None:
        obj.max_waba_slots = payload.max_waba_slots
    if payload.is_active is not None:
        obj.is_active = payload.is_active

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{api_manager_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_manager(
    api_manager_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.ApiManager).filter(models.ApiManager.id == api_manager_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="API Manager tidak ditemukan")

    waba_count = db.query(models.Waba).filter(models.Waba.api_manager_id == api_manager_id).count()
    if waba_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Tidak bisa hapus. Masih ada {waba_count} WABA terhubung.",
        )
    db.delete(obj)
    db.commit()
    return None