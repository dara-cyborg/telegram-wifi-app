import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from app.config import get_settings


def verify_init_data(init_data: str) -> dict:
    settings = get_settings()
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received = values.pop("hash", "")
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(received, expected):
        raise HTTPException(403, "Unauthorized: Admin access only")
    try:
        user = json.loads(values["user"])
    except (KeyError, json.JSONDecodeError) as error:
        raise HTTPException(403, "Unauthorized: Admin access only") from error
    if user.get("id") != settings.admin_telegram_id:
        raise HTTPException(403, "Unauthorized: Admin access only")
    return user


async def verify_admin(authorization: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    if settings.dev_mode and not authorization:
        return {"id": settings.admin_telegram_id}
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(403, "Unauthorized: Admin access only")
    return verify_init_data(authorization[4:])
