from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app import models
from app.schemas import WabaOut, ClientDashboardStats
from app.deps import require_client_admin

router = APIRouter(prefix="/client-portal", tags=["Client Portal"])


@router.get("/wabas", response_model=List[WabaOut])
def my_wabas(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    return db.query(models.Waba).filter(
        models.Waba.client_id == current_user.client_id
    ).order_by(models.Waba.id.desc()).all()


@router.get("/stats", response_model=ClientDashboardStats)
def my_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    cid = current_user.client_id

    total_wabas = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == cid).scalar() or 0
    active_wabas = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == cid, models.Waba.is_active == True).scalar() or 0
    wabas_green = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == cid,
        models.Waba.quality_rating == models.QualityRating.green).scalar() or 0
    wabas_yellow = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == cid,
        models.Waba.quality_rating == models.QualityRating.yellow).scalar() or 0
    wabas_red = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == cid,
        models.Waba.quality_rating == models.QualityRating.red).scalar() or 0

    total_contacts = db.query(func.count(models.Contact.id)).filter(
        models.Contact.client_id == cid).scalar() or 0
    total_broadcasts = db.query(func.count(models.Broadcast.id)).filter(
        models.Broadcast.client_id == cid).scalar() or 0
    total_messages_sent = db.query(func.count(models.MessageLog.id)).filter(
        models.MessageLog.client_id == cid,
        models.MessageLog.direction == "outbound").scalar() or 0
    total_messages_delivered = db.query(func.count(models.MessageLog.id)).filter(
        models.MessageLog.client_id == cid,
        models.MessageLog.status == "delivered").scalar() or 0
    total_messages_read = db.query(func.count(models.MessageLog.id)).filter(
        models.MessageLog.client_id == cid,
        models.MessageLog.status == "read").scalar() or 0
    total_messages_failed = db.query(func.count(models.MessageLog.id)).filter(
        models.MessageLog.client_id == cid,
        models.MessageLog.status == "failed").scalar() or 0

    return ClientDashboardStats(
        total_wabas=total_wabas,
        active_wabas=active_wabas,
        wabas_green=wabas_green,
        wabas_yellow=wabas_yellow,
        wabas_red=wabas_red,
        total_contacts=total_contacts,
        total_broadcasts=total_broadcasts,
        total_messages_sent=total_messages_sent,
        total_messages_delivered=total_messages_delivered,
        total_messages_read=total_messages_read,
        total_messages_failed=total_messages_failed,
    )