from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models
from app.schemas import ClientCreate, ClientUpdate, ClientOut
from app.deps import require_super_admin
from app.security import hash_password

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("", response_model=List[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    return db.query(models.Client).order_by(models.Client.id.desc()).all()


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    return obj


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    # Cek email sudah dipakai?
    existing = db.query(models.User).filter(models.User.email == payload.admin_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")

    # Buat Client dulu
    client = models.Client(
        name=payload.name,
        status=models.ClientStatus.active,
    )
    db.add(client)
    db.flush()  # supaya dapat client.id

    # Buat User admin untuk klien ini
    admin_user = models.User(
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        role="client_admin",
        client_id=client.id,
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(client)
    return client


@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")

    if payload.name is not None:
        obj.name = payload.name
    if payload.status is not None:
        obj.status = payload.status

    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{client_id}/suspend", response_model=ClientOut)
def suspend_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")

    obj.status = models.ClientStatus.suspended

    # Nonaktifkan semua user klien ini
    db.query(models.User).filter(models.User.client_id == client_id).update({"is_active": False})

    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{client_id}/activate", response_model=ClientOut)
def activate_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")

    obj.status = models.ClientStatus.active

    # Aktifkan kembali semua user klien ini
    db.query(models.User).filter(models.User.client_id == client_id).update({"is_active": True})

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    obj = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")

    # Hapus semua user klien ini dulu
    db.query(models.User).filter(models.User.client_id == client_id).delete()

    db.delete(obj)
    db.commit()
    return None