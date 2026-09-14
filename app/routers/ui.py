from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["UI"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


# SUPER ADMIN
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


@router.get("/ui/admin-chat", response_class=HTMLResponse)
def admin_chat_page(request: Request):
    return templates.TemplateResponse("admin_chat.html", {"request": request})


@router.get("/ui/admin-chat/{session_id}", response_class=HTMLResponse)
def admin_chat_detail_page(request: Request, session_id: int):
    return templates.TemplateResponse("admin_chat.html", {"request": request, "session_id": session_id})


# CLIENT PORTAL
@router.get("/ui/client-dashboard", response_class=HTMLResponse)
def client_dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard_client.html", {"request": request})


@router.get("/ui/client-chat", response_class=HTMLResponse)
def client_chat_page(request: Request):
    return templates.TemplateResponse("client_chat_cs.html", {"request": request})


@router.get("/ui/client-chat/{session_id}", response_class=HTMLResponse)
def client_chat_detail_page(request: Request, session_id: int):
    return templates.TemplateResponse("client_chat_cs.html", {"request": request, "session_id": session_id})


@router.get("/ui/client-chat-wa", response_class=HTMLResponse)
def client_chat_wa_page(request: Request):
    return templates.TemplateResponse("client_chat.html", {"request": request})


@router.get("/ui/client-wabas", response_class=HTMLResponse)
def client_wabas_page(request: Request):
    return templates.TemplateResponse("client_wabas.html", {"request": request})


@router.get("/ui/client-send-message", response_class=HTMLResponse)
def client_send_message_page(request: Request):
    return templates.TemplateResponse("client_send_message.html", {"request": request})


@router.get("/ui/client-broadcast", response_class=HTMLResponse)
def client_broadcast_page(request: Request):
    return templates.TemplateResponse("client_broadcast.html", {"request": request})


@router.get("/ui/client-contacts", response_class=HTMLResponse)
def client_contacts_page(request: Request):
    return templates.TemplateResponse("client_contacts.html", {"request": request})


@router.get("/ui/client-templates", response_class=HTMLResponse)
def client_templates_page(request: Request):
    return templates.TemplateResponse("client_templates.html", {"request": request})


@router.get("/ui/client-logs", response_class=HTMLResponse)
def client_logs_page(request: Request):
    return templates.TemplateResponse("client_logs.html", {"request": request})