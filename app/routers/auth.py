from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app import models
from app.schemas import LoginRequest, TokenResponse, ClientSelfRegister
from app.security import verify_password, create_access_token, hash_password
import re

router = APIRouter(prefix="/auth", tags=["Auth"])


# Rate limiting sederhana (in-memory, cukup untuk prototype)
_register_attempts = {}  # {ip: [timestamp1, timestamp2, ...]}
RATE_LIMIT_WINDOW_HOURS = 24
RATE_LIMIT_MAX = 3  # max 3 pendaftaran per IP per 24 jam


def _check_rate_limit(ip: str) -> bool:
    """Return True kalau boleh lanjut, False kalau kena limit."""
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=RATE_LIMIT_WINDOW_HOURS)
    attempts = _register_attempts.get(ip, [])
    attempts = [t for t in attempts if t > cutoff]
    _register_attempts[ip] = attempts
    if len(attempts) >= RATE_LIMIT_MAX:
        return False
    attempts.append(now)
    _register_attempts[ip] = attempts
    return True


def _validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


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


@router.post("/register", response_model=TokenResponse)
def register(
    payload: ClientSelfRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Self-registration klien baru.
    Auto-approve + auto-login: return token langsung.
    """
    # Rate limit by IP
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Terlalu banyak pendaftaran. Coba lagi dalam {RATE_LIMIT_WINDOW_HOURS} jam.",
        )

    # Validasi input
    name = payload.name.strip()
    email = payload.admin_email.strip().lower()
    password = payload.admin_password

    if len(name) < 3:
        raise HTTPException(status_code=400, detail="Nama minimal 3 karakter")
    if not _validate_email(email):
        raise HTTPException(status_code=400, detail="Format email tidak valid")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password minimal 8 karakter")

    # Cek email sudah dipakai
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")

    # Buat Client
    client = models.Client(
        name=name,
        status=models.ClientStatus.active,
    )
    db.add(client)
    db.flush()

    # Buat User admin klien
    user = models.User(
        email=email,
        hashed_password=hash_password(password),
        role="client_admin",
        client_id=client.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(client)
    db.refresh(user)

    print(f"🎉 Klien baru terdaftar: {name} ({email})")

    # Auto-login: langsung return token
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