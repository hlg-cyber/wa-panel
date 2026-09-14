from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models
from app.schemas import ContactCreate, ContactBulkImport, ContactOut
from app.deps import require_client_admin
import csv
import io

router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.get("", response_model=List[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    return db.query(models.Contact).filter(
        models.Contact.client_id == current_user.client_id
    ).order_by(models.Contact.id.desc()).all()


@router.post("", response_model=ContactOut)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    existing = db.query(models.Contact).filter(
        models.Contact.client_id == current_user.client_id,
        models.Contact.phone_number == payload.phone_number,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nomor sudah terdaftar")

    contact = models.Contact(
        client_id=current_user.client_id,
        name=payload.name,
        phone_number=payload.phone_number,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/bulk", response_model=dict)
def bulk_import(
    payload: ContactBulkImport,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    inserted = 0
    skipped = 0
    for c in payload.contacts:
        existing = db.query(models.Contact).filter(
            models.Contact.client_id == current_user.client_id,
            models.Contact.phone_number == c.phone_number,
        ).first()
        if existing:
            skipped += 1
            continue
        db.add(models.Contact(
            client_id=current_user.client_id,
            name=c.name,
            phone_number=c.phone_number,
        ))
        inserted += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped}


@router.post("/import-csv", response_model=dict)
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    """Import CSV dengan kolom: name, phone_number"""
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    inserted = 0
    skipped = 0

    for row in reader:
        phone = (row.get("phone_number") or row.get("phone") or "").strip()
        name = (row.get("name") or "").strip()
        if not phone:
            skipped += 1
            continue

        # Normalisasi nomor (hapus +, spasi, dash)
        phone = phone.replace("+", "").replace(" ", "").replace("-", "")

        existing = db.query(models.Contact).filter(
            models.Contact.client_id == current_user.client_id,
            models.Contact.phone_number == phone,
        ).first()
        if existing:
            skipped += 1
            continue
        db.add(models.Contact(
            client_id=current_user.client_id,
            name=name or None,
            phone_number=phone,
        ))
        inserted += 1

    db.commit()
    return {"inserted": inserted, "skipped": skipped}


@router.delete("/{contact_id}")
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    contact = db.query(models.Contact).filter(
        models.Contact.id == contact_id,
        models.Contact.client_id == current_user.client_id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Kontak tidak ditemukan")
    db.delete(contact)
    db.commit()
    return {"status": "deleted"}