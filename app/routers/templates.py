from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models
from app.schemas import TemplateCreate, TemplateUpdate, TemplateOut
from app.deps import require_client_admin
from app.services import meta_api
import json

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=List[TemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    return db.query(models.MessageTemplate).filter(
        models.MessageTemplate.client_id == current_user.client_id
    ).order_by(models.MessageTemplate.id.desc()).all()


@router.post("", response_model=TemplateOut)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    waba = db.query(models.Waba).filter(
        models.Waba.id == payload.waba_id,
        models.Waba.client_id == current_user.client_id,
    ).first()
    if not waba:
        raise HTTPException(status_code=404, detail="WABA tidak ditemukan")

    template = models.MessageTemplate(
        client_id=current_user.client_id,
        waba_id=payload.waba_id,
        name=payload.name,
        category=payload.category,
        language=payload.language,
        header_type=payload.header_type,
        header_text=payload.header_text,
        body_text=payload.body_text,
        footer_text=payload.footer_text,
        buttons_json=json.dumps(payload.buttons) if payload.buttons else None,
        status=models.TemplateStatus.draft,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    template = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.id == template_id,
        models.MessageTemplate.client_id == current_user.client_id,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan")
    if template.status == models.TemplateStatus.approved:
        raise HTTPException(status_code=400, detail="Template yang sudah approved tidak bisa diubah")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "buttons" and value is not None:
            setattr(template, "buttons_json", json.dumps(value))
        elif hasattr(template, field):
            setattr(template, field, value)

    db.commit()
    db.refresh(template)
    return template


@router.post("/{template_id}/submit", response_model=TemplateOut)
async def submit_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    template = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.id == template_id,
        models.MessageTemplate.client_id == current_user.client_id,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan")

    waba = db.query(models.Waba).filter(models.Waba.id == template.waba_id).first()
    if not waba:
        raise HTTPException(status_code=404, detail="WABA tidak ditemukan")

    # Build template data untuk Meta
    components = []
    if template.header_type == "TEXT" and template.header_text:
        components.append({"type": "HEADER", "format": "TEXT", "text": template.header_text})
    components.append({"type": "BODY", "text": template.body_text})
    if template.footer_text:
        components.append({"type": "FOOTER", "text": template.footer_text})

    template_data = {
        "name": template.name.lower().replace(" ", "_"),
        "language": template.language,
        "category": template.category,
        "components": components,
    }

    result = await meta_api.submit_template(waba, template_data)

    if result.get("success"):
        template.status = models.TemplateStatus.pending
        template.meta_template_id = result.get("data", {}).get("id")
        db.commit()
        db.refresh(template)
        return template
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "Gagal submit ke Meta"))


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    template = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.id == template_id,
        models.MessageTemplate.client_id == current_user.client_id,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan")
    db.delete(template)
    db.commit()
    return {"status": "deleted"}