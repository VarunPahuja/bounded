"""Boot-time guardrails for Razorpay credentials. Fail at import, not at
first charge -- a live key reaching this process is a bad afternoon.

Loaded from .env via python-dotenv, never expected as a pre-set shell env
var. The key secret and webhook secret are never logged: anything that
needs to show which key is in use calls masked_key_id(), never KEY_SECRET
or WEBHOOK_SECRET directly, not even in an exception message.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

KEY_ID = os.environ["RAZORPAY_KEY_ID"]
KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]
WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
ALLOW_LIVE = os.getenv("RAZORPAY_ALLOW_LIVE", "false").lower() == "true"


def masked_key_id(key_id: str = KEY_ID) -> str:
    return f"{key_id[:12]}...{key_id[-4:]}"


if not KEY_ID.startswith("rzp_test_") and not ALLOW_LIVE:
    raise RuntimeError(
        f"Refusing to boot with non-test Razorpay key {masked_key_id()}. "
        "Set RAZORPAY_ALLOW_LIVE=true only in production."
    )
