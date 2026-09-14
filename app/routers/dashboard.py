from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models
from app.schemas import DashboardStats, ClientDashboardStats
from app.deps import require_super_admin, require_client_admin

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    pending_chats = db.query(func.count(models.ChatSession.id)).filter(
        models.ChatSession.status.in_([
            models.ChatSessionStatus.waiting_admin,
            models.ChatSessionStatus.in_progress,
            models.ChatSessionStatus.waiting_otp,
        ])
    ).scalar() or 0

    return DashboardStats(
        total_api_managers=db.query(func.count(models.ApiManager.id)).scalar() or 0,
        total_clients=db.query(func.count(models.Client.id)).scalar() or 0,
        active_clients=db.query(func.count(models.Client.id)).filter(
            models.Client.status == models.ClientStatus.active).scalar() or 0,
        suspended_clients=db.query(func.count(models.Client.id)).filter(
            models.Client.status == models.ClientStatus.suspended).scalar() or 0,
        total_wabas=db.query(func.count(models.Waba.id)).scalar() or 0,
        wabas_green=db.query(func.count(models.Waba.id)).filter(
            models.Waba.quality_rating == models.QualityRating.green).scalar() or 0,
        wabas_yellow=db.query(func.count(models.Waba.id)).filter(
            models.Waba.quality_rating == models.QualityRating.yellow).scalar() or 0,
        wabas_red=db.query(func.count(models.Waba.id)).filter(
            models.Waba.quality_rating == models.QualityRating.red).scalar() or 0,
        pending_chats=pending_chats,
    )


@router.get("/client-stats", response_model=ClientDashboardStats)
def get_client_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    cid = current_user.client_id

    active_chats = db.query(func.count(models.ChatSession.id)).filter(
        models.ChatSession.client_id == cid,
        models.ChatSession.status.in_([
            models.ChatSessionStatus.waiting_admin,
            models.ChatSessionStatus.in_progress,
            models.ChatSessionStatus.waiting_otp,
        ])
    ).scalar() or 0

    return ClientDashboardStats(
        total_wabas=db.query(func.count(models.Waba.id)).filter(
            models.Waba.client_id == cid).scalar() or 0,
        active_wabas=db.query(func.count(models.Waba.id)).filter(
            models.Waba.client_id == cid, models.Waba.is_active == True).scalar() or 0,
        wabas_green=db.query(func.count(models.Waba.id)).filter(
            models.Waba.client_id == cid,
            models.Waba.quality_rating == models.QualityRating.green).scalar() or 0,
        wabas_yellow=db.query(func.count(models.Waba.id)).filter(
            models.Waba.client_id == cid,
            models.Waba.quality_rating == models.QualityRating.yellow).scalar() or 0,
        wabas_red=db.query(func.count(models.Waba.id)).filter(
            models.Waba.client_id == cid,
            models.Waba.quality_rating == models.QualityRating.red).scalar() or 0,
        total_contacts=db.query(func.count(models.Contact.id)).filter(
            models.Contact.client_id == cid).scalar() or 0,
        total_broadcasts=db.query(func.count(models.Broadcast.id)).filter(
            models.Broadcast.client_id == cid).scalar() or 0,
        total_messages_sent=db.query(func.count(models.MessageLog.id)).filter(
            models.MessageLog.client_id == cid,
            models.MessageLog.direction == "outbound").scalar() or 0,
        total_messages_delivered=db.query(func.count(models.MessageLog.id)).filter(
            models.MessageLog.client_id == cid,
            models.MessageLog.status == "delivered").scalar() or 0,
        total_messages_read=db.query(func.count(models.MessageLog.id)).filter(
            models.MessageLog.client_id == cid,
            models.MessageLog.status == "read").scalar() or 0,
        total_messages_failed=db.query(func.count(models.MessageLog.id)).filter(
            models.MessageLog.client_id == cid,
            models.MessageLog.status == "failed").scalar() or 0,
        active_chats=active_chats,
    )