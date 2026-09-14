from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["UI"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/ui/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/ui/api-managers", response_class=HTMLResponse)
def api_managers_page(request: Request):
    return templates.TemplateResponse("api_managers.html", {"request": request})


@router.get("/ui/wabas", response_class=HTMLResponse)
def wabas_page(request: Request):
    return templates.TemplateResponse("wabas.html", {"request": request})


@router.get("/ui/clients", response_class=HTMLResponse)
def clients_page(request: Request):
    return templates.TemplateResponse("clients.html", {"request": request})


@router.get("/ui/client-dashboard", response_class=HTMLResponse)
def client_dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard_client.html", {"request": request})