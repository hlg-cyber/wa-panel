from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine, SessionLocal
from app import models
from app.security import hash_password
from app.config import settings

# Buat tabel otomatis (untuk prototipe)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WA Panel API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


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
        else:
            print(f"ℹ️  Super Admin already exists: {settings.SUPERADMIN_EMAIL}")
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "ok", "message": "WA Panel API running"}


# Register routers
from app.routers import auth, dashboard, ui

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(ui.router)