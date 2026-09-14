from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine, SessionLocal
from app import models
from app.security import hash_password
from app.config import settings

# Buat tabel otomatis (untuk prototipe; produksi pakai Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WA Panel API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed Super Admin
@app.on_event("startup")
def seed_superadmin():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter_by(email=settings.SUPERADMIN_EMAIL).first()
        if not existing:
            user = models.User(
                email=settings.SUPERADMIN_EMAIL,
                hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
                role="super_admin",
            )
            db.add(user)
            db.commit()
            print(f"✅ Super Admin seeded: {settings.SUPERADMIN_EMAIL}")
    finally:
        db.close()

@app.get("/")
def root():
    return {"status": "ok", "message": "WA Panel API running"}

# Nanti router kita tambahkan di sini
# from app.routers import auth, api_managers, wabas, clients, webhook
# app.include_router(auth.router, prefix="/auth", tags=["Auth"])
# app.include_router(api_managers.router, prefix="/api-managers", tags=["API Manager"])
# app.include_router(wabas.router, prefix="/wabas", tags=["WABA"])
# app.include_router(clients.router, prefix="/clients", tags=["Clients"])
# app.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])