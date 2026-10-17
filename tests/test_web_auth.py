import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from assistant_bot.web_auth import WebAppAuthError, validate_init_data


def signed_init_data(token: str) -> str:
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "test-query",
        "user": json.dumps({"id": 123, "first_name": "Alan"}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_telegram_init_data():
    identity = validate_init_data(signed_init_data("123:test"), "123:test")
    assert identity["user_id"] == 123


def test_tampered_telegram_init_data_is_rejected():
    with pytest.raises(WebAppAuthError):
        validate_init_data(signed_init_data("123:test") + "x", "123:test")
