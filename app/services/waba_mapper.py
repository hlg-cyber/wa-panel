from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any
from app import models


def find_best_api_manager(db: Session) -> Optional[models.ApiManager]:
    """
    Cari API Manager yang masih punya slot kosong, urut dari yang paling sedikit WABA-nya.
    Return None kalau semua penuh.
    """
    # Subquery: hitung jumlah WABA per api_manager
    waba_counts = db.query(
        models.Waba.api_manager_id,
        func.count(models.Waba.id).label("total")
    ).filter(
        models.Waba.api_manager_id.isnot(None)
    ).group_by(models.Waba.api_manager_id).subquery()

    # Query API Manager aktif dengan WABA count
    candidates = db.query(
        models.ApiManager,
        func.coalesce(waba_counts.c.total, 0).label("waba_count")
    ).outerjoin(
        waba_counts, models.ApiManager.id == waba_counts.c.api_manager_id
    ).filter(
        models.ApiManager.is_active == True
    ).order_by(
        func.coalesce(waba_counts.c.total, 0).asc(),
        models.ApiManager.id.asc()
    ).all()

    # Cari yang masih punya slot
    for am, count in candidates:
        if count < am.max_waba_slots:
            return am

    return None


def get_all_api_managers_status(db: Session) -> list:
    """Return list status semua API Manager + slot tersedia."""
    waba_counts = db.query(
        models.Waba.api_manager_id,
        func.count(models.Waba.id).label("total")
    ).filter(
        models.Waba.api_manager_id.isnot(None)
    ).group_by(models.Waba.api_manager_id).subquery()

    results = db.query(
        models.ApiManager,
        func.coalesce(waba_counts.c.total, 0).label("waba_count")
    ).outerjoin(
        waba_counts, models.ApiManager.id == waba_counts.c.api_manager_id
    ).order_by(models.ApiManager.id.asc()).all()

    return [
        {
            "id": am.id,
            "name": am.name,
            "max_waba_slots": am.max_waba_slots,
            "used_slots": count,
            "available_slots": max(0, am.max_waba_slots - count),
            "is_active": am.is_active,
            "is_full": count >= am.max_waba_slots,
        }
        for am, count in results
    ]