from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine, SessionLocal
from app import models
from app.security import hash_password
from app.config import settings

Base.metadata.create_all(bind=engine)

app = FastAPI(title="WA Panel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "ok", "message": "WA Panel API running"}


from app.routers import (
    auth, dashboard, ui, api_managers, wabas, clients,
    webhook, messages, contacts, templates, broadcasts, client_portal,
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(ui.router)
app.include_router(api_managers.router)
app.include_router(wabas.router)
app.include_router(clients.router)
app.include_router(webhook.router)
app.include_router(messages.router)
app.include_router(contacts.router)
app.include_router(templates.router)
app.include_router(broadcasts.router)
app.include_router(client_portal.router)