from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app import models
from app.schemas import WabaCreate, WabaUpdate, WabaOut
from app.deps import require_super_admin

router = APIRouter(prefix="/wabas", tags=["WABA"])


@router.get("", response_model=List[WabaOut])
def list_wabas(
    api_manager_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    query = db.query(models.Waba)
    if api_manager_id:
        query = query.filter(models.Waba.api_manager_id == api_manager_id)
    return query.order_by(models.Waba.id.desc()).all()


@router.get("/{waba_id}", response_model=WabaOut)
def get_waba(
    waba_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.Waba).filter(models.Waba.id == waba_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="WABA tidak ditemukan")
    return obj


@router.post("", response_model=WabaOut, status_code=status.HTTP_201_CREATED)
def create_waba(
    payload: WabaCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    # Cek API Manager exists
    am = db.query(models.ApiManager).filter(models.ApiManager.id == payload.api_manager_id).first()
    if not am:
        raise HTTPException(status_code=404, detail="API Manager tidak ditemukan")

    # Cek WABA ID sudah ada?
    existing = db.query(models.Waba).filter(models.Waba.waba_id == payload.waba_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="WABA ID sudah terdaftar")

    obj = models.Waba(
        api_manager_id=payload.api_manager_id,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        display_phone_number=payload.display_phone_number,
        display_name=payload.display_name,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{waba_id}", response_model=WabaOut)
def update_waba(
    waba_id: int,
    payload: WabaUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.Waba).filter(models.Waba.id == waba_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="WABA tidak ditemukan")

    if payload.display_name is not None:
        obj.display_name = payload.display_name
    if payload.quality_rating is not None:
        obj.quality_rating = payload.quality_rating
    if payload.is_active is not None:
        obj.is_active = payload.is_active

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{waba_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_waba(
    waba_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.Waba).filter(models.Waba.id == waba_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="WABA tidak ditemukan")
    db.delete(obj)
    db.commit()
    return None