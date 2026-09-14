from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["UI"])
templates = Jinja2Templates(directory="templates")


def _render(name):
    return lambda request: templates.TemplateResponse(name, {"request": request})


# Login
router.add_api_route("/login", _render("login.html"), methods=["GET"], response_class=HTMLResponse)

# Super Admin
router.add_api_route("/ui/dashboard", _render("dashboard.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/api-managers", _render("api_managers.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/wabas", _render("wabas.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/clients", _render("clients.html"), methods=["GET"], response_class=HTMLResponse)

# Client Portal
router.add_api_route("/ui/client-dashboard", _render("dashboard_client.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/client-wabas", _render("client_wabas.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/client-send-message", _render("client_send_message.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/client-broadcast", _render("client_broadcast.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/client-contacts", _render("client_contacts.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/client-templates", _render("client_templates.html"), methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/ui/client-logs", _render("client_logs.html"), methods=["GET"], response_class=HTMLResponse)