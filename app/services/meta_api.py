import httpx
import json
from typing import Optional, Dict, Any
from app import models
from app.security import decrypt_token

META_API_VERSION = "v22.0"
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


def _get_access_token(waba: models.Waba) -> str:
    return decrypt_token(waba.api_manager.access_token_encrypted)


async def subscribe_waba_to_app(waba: models.Waba) -> Dict[str, Any]:
    """
    Force subscribe WABA ke Meta App.
    Ini WAJIB dipanggil setiap WABA baru ditambahkan, agar webhook menerima pesan.
    """
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.waba_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers)
            data = res.json()
            if res.status_code >= 400:
                print(f"❌ Subscribe WABA {waba.waba_id} gagal: {data}")
                return {"success": False, "error": data.get("error", {}).get("message", str(data))}
            print(f"✅ WABA {waba.waba_id} subscribed to app")
            return {"success": True, "data": data}
    except Exception as e:
        print(f"❌ Subscribe WABA error: {e}")
        return {"success": False, "error": str(e)}


async def send_text_message(waba: models.Waba, to: str, text: str) -> Dict[str, Any]:
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    return await _post(url, token, payload)


async def send_template_message(
    waba: models.Waba, to: str, template_name: str, language: str = "id",
    params: Optional[list] = None,
) -> Dict[str, Any]:
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
    return await _post(url, token, payload)


async def send_media_message(
    waba: models.Waba, to: str, media_type: str, media_url: str,
    caption: Optional[str] = None,
) -> Dict[str, Any]:
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
    return await _post(url, token, payload)


async def _post(url: str, token: str, payload: dict) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            data = res.json()
            if res.status_code >= 400:
                return {"success": False, "error": data.get("error", {}).get("message", str(data))}
            return {"success": True, "data": data, "message_id": data.get("messages", [{}])[0].get("id")}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def submit_template(waba: models.Waba, template_data: dict) -> Dict[str, Any]:
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.waba_id}/message_templates"
    return await _post(url, token, template_data)


async def get_template_status(waba: models.Waba, template_name: str) -> Dict[str, Any]:
    token = _get_access_token(waba)
    url = f"{META_BASE_URL}/{waba.waba_id}/message_templates?name={template_name}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, headers=headers)
            return res.json()
    except Exception as e:
        return {"error": str(e)}