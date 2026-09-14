import httpx
import json
from typing import Optional, Dict, Any
from app import models
from app.security import decrypt_token

META_API_VERSION = "v22.0"
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


def _get_access_token(waba: models.Waba) -> str:
    return decrypt_token(waba.api_manager.access_token_encrypted)


def _get_token_from_api_manager(api_manager: models.ApiManager) -> str:
    return decrypt_token(api_manager.access_token_encrypted)


async def _post(url: str, token: str, payload: dict = None, params: dict = None) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, json=payload, params=params)
            try:
                data = res.json()
            except Exception:
                data = {"raw": res.text}
            if res.status_code >= 400:
                err_msg = data.get("error", {}).get("message", str(data))
                return {"success": False, "error": err_msg, "raw": data}
            return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _get(url: str, token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, headers=headers)
            data = res.json()
            if res.status_code >= 400:
                return {"success": False, "error": data.get("error", {}).get("message", str(data))}
            return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =====================
# WABA REGISTRATION FLOW
# =====================

async def register_phone_number(
    api_manager: models.ApiManager,
    meta_waba_id: str,
    cc: str,
    phone_number: str,
    verified_name: str,
) -> Dict[str, Any]:
    """
    Step 1: Daftarkan nomor telepon ke WABA Meta.
    Return: { success, phone_number_id }
    """
    token = _get_token_from_api_manager(api_manager)
    url = f"{META_BASE_URL}/{meta_waba_id}/phone_numbers"
    payload = {
        "cc": cc,
        "phone_number": phone_number,
        "verified_name": verified_name,
    }
    result = await _post(url, token, payload)
    if result.get("success"):
        data = result.get("data", {})
        return {"success": True, "phone_number_id": data.get("id"), "data": data}
    return result


async def request_verification_code(
    api_manager: models.ApiManager,
    phone_number_id: str,
    code_method: str = "SMS",
    language: str = "id",
) -> Dict[str, Any]:
    """Step 2: Minta kode verifikasi dikirim ke nomor."""
    token = _get_token_from_api_manager(api_manager)
    url = f"{META_BASE_URL}/{phone_number_id}/request_code"
    params = {"code_method": code_method, "language": language}
    return await _post(url, token, params=params)


async def verify_phone_number(
    api_manager: models.ApiManager,
    phone_number_id: str,
    code: str,
) -> Dict[str, Any]:
    """Step 3: Verifikasi kode OTP."""
    token = _get_token_from_api_manager(api_manager)
    url = f"{META_BASE_URL}/{phone_number_id}/verify_code"
    payload = {"code": code}
    return await _post(url, token, payload)


async def register_phone_for_cloud_api(
    api_manager: models.ApiManager,
    phone_number_id: str,
    pin: str,
) -> Dict[str, Any]:
    """Step 4: Registrasi nomor untuk Cloud API dengan PIN 6 digit."""
    token = _get_token_from_api_manager(api_manager)
    url = f"{META_BASE_URL}/{phone_number_id}/register"
    payload = {
        "messaging_product": "whatsapp",
        "pin": pin,
    }
    return await _post(url, token, payload)


async def subscribe_waba_to_app_by_id(
    api_manager: models.ApiManager,
    meta_waba_id: str,
) -> Dict[str, Any]:
    """Subscribe WABA (via Meta WABA ID) ke app. Dipakai setelah registrasi."""
    token = _get_token_from_api_manager(api_manager)
    url = f"{META_BASE_URL}/{meta_waba_id}/subscribed_apps"
    return await _post(url, token)


# =====================
# WABA MANAGEMENT (existing)
# =====================

async def subscribe_waba_to_app(waba: models.Waba) -> Dict[str, Any]:
    """Subscribe WABA ke app (untuk WABA yang sudah ada di panel)."""
    if not waba.waba_id:
        return {"success": False, "error": "WABA ID belum diisi"}
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.waba_id}/subscribed_apps"
    return await _post(url, token)


async def send_text_message(waba: models.Waba, to: str, text: str) -> Dict[str, Any]:
    if not waba.phone_number_id:
        return {"success": False, "error": "Phone Number ID belum diisi"}
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    result = await _post(url, token, payload)
    if result.get("success"):
        msg_id = result.get("data", {}).get("messages", [{}])[0].get("id")
        return {"success": True, "message_id": msg_id, "data": result.get("data")}
    return result


async def send_template_message(
    waba: models.Waba, to: str, template_name: str, language: str = "id",
    params: Optional[list] = None,
) -> Dict[str, Any]:
    if not waba.phone_number_id:
        return {"success": False, "error": "Phone Number ID belum diisi"}
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.phone_number_id}/messages"

    components = []
    if params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": p} for p in params],
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components,
        },
    }
    result = await _post(url, token, payload)
    if result.get("success"):
        msg_id = result.get("data", {}).get("messages", [{}])[0].get("id")
        return {"success": True, "message_id": msg_id, "data": result.get("data")}
    return result


async def send_media_message(
    waba: models.Waba, to: str, media_type: str, media_url: str,
    caption: Optional[str] = None,
) -> Dict[str, Any]:
    if not waba.phone_number_id:
        return {"success": False, "error": "Phone Number ID belum diisi"}
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.phone_number_id}/messages"
    media_obj = {"link": media_url}
    if caption and media_type in ("image", "video", "document"):
        media_obj["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": media_type,
        media_type: media_obj,
    }
    result = await _post(url, token, payload)
    if result.get("success"):
        msg_id = result.get("data", {}).get("messages", [{}])[0].get("id")
        return {"success": True, "message_id": msg_id, "data": result.get("data")}
    return result


async def submit_template(waba: models.Waba, template_data: dict) -> Dict[str, Any]:
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.waba_id}/message_templates"
    return await _post(url, token, template_data)


async def get_template_status(waba: models.Waba, template_name: str) -> Dict[str, Any]:
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.waba_id}/message_templates?name={template_name}"
    return await _get(url, token)