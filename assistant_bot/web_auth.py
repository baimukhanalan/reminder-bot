import hashlib
import hmac
import json
import time
from typing import Any, Dict
from urllib.parse import parse_qsl


class WebAppAuthError(ValueError):
    pass


def validate_init_data(
    init_data: str, bot_token: str, max_age_seconds: int = 86400
) -> Dict[str, Any]:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise WebAppAuthError("Missing Telegram signature")
    data_check_string = "\n".join(
        "{}={}".format(key, pairs[key]) for key in sorted(pairs)
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise WebAppAuthError("Invalid Telegram signature")

    try:
        auth_date = int(pairs["auth_date"])
        user = json.loads(pairs["user"])
        user_id = int(user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WebAppAuthError("Incomplete Telegram identity") from exc
    now = int(time.time())
    if auth_date > now + 300 or now - auth_date > max_age_seconds:
        raise WebAppAuthError("Expired Telegram identity")
    return {"user_id": user_id, "user": user, "auth_date": auth_date}

