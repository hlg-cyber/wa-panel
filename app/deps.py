from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.security import decode_token
from app import models

security_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.query(models.User).filter(models.User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    if user.role == "client_admin" and user.client:
        if user.client.status == models.ClientStatus.suspended:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun klien sedang disuspend",
            )

    return user


def require_super_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required",
        )
    return current_user


def require_client_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if current_user.role != "client_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client Admin access required",
        )
    return current_user