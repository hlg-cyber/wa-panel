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
    total_api_managers = db.query(func.count(models.ApiManager.id)).scalar() or 0
    total_clients = db.query(func.count(models.Client.id)).scalar() or 0
    active_clients = db.query(func.count(models.Client.id)).filter(
        models.Client.status == models.ClientStatus.active
    ).scalar() or 0
    suspended_clients = db.query(func.count(models.Client.id)).filter(
        models.Client.status == models.ClientStatus.suspended
    ).scalar() or 0
    total_wabas = db.query(func.count(models.Waba.id)).scalar() or 0
    wabas_green = db.query(func.count(models.Waba.id)).filter(
        models.Waba.quality_rating == models.QualityRating.green
    ).scalar() or 0
    wabas_yellow = db.query(func.count(models.Waba.id)).filter(
        models.Waba.quality_rating == models.QualityRating.yellow
    ).scalar() or 0
    wabas_red = db.query(func.count(models.Waba.id)).filter(
        models.Waba.quality_rating == models.QualityRating.red
    ).scalar() or 0

    return DashboardStats(
        total_api_managers=total_api_managers,
        total_clients=total_clients,
        active_clients=active_clients,
        suspended_clients=suspended_clients,
        total_wabas=total_wabas,
        wabas_green=wabas_green,
        wabas_yellow=wabas_yellow,
        wabas_red=wabas_red,
    )


@router.get("/client-stats", response_model=ClientDashboardStats)
def get_client_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_client_admin),
):
    client_id = current_user.client_id

    total_wabas = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == client_id
    ).scalar() or 0
    active_wabas = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == client_id,
        models.Waba.is_active == True,
    ).scalar() or 0
    wabas_green = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == client_id,
        models.Waba.quality_rating == models.QualityRating.green,
    ).scalar() or 0
    wabas_yellow = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == client_id,
        models.Waba.quality_rating == models.QualityRating.yellow,
    ).scalar() or 0
    wabas_red = db.query(func.count(models.Waba.id)).filter(
        models.Waba.client_id == client_id,
        models.Waba.quality_rating == models.QualityRating.red,
    ).scalar() or 0

    return ClientDashboardStats(
        total_wabas=total_wabas,
        active_wabas=active_wabas,
        wabas_green=wabas_green,
        wabas_yellow=wabas_yellow,
        wabas_red=wabas_red,
    )