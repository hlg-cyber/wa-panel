from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.schemas import LoginRequest, TokenResponse
from app.security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun tidak aktif",
        )

    if user.role == "client_admin" and user.client:
        if user.client.status == models.ClientStatus.suspended:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun klien sedang disuspend. Hubungi administrator.",
            )

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "client_id": user.client_id,
    })
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        email=user.email,
        client_id=user.client_id,
    )