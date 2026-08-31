"""Live tests against real Razorpay test mode -- no mocking, per CLAUDE.md.

Every payment in test mode requires a browser step (S2S/headless creation
is provisioned per-merchant and not available on these keys -- see
docs/LOG.md 2026-08-31 and the razorpay-testmode skill). There is no way
to produce a fresh authorized or failed payment from inside pytest, and
adding browser-automation tooling is out of scope. So these tests consume
payment ids seeded by a human ahead of time and skip cleanly when one
isn't available, rather than failing `pytest` for lacking a browser or
mocking the one thing this suite exists to prove works for real.

To run these for real:

1. `python scripts/seed.py --count 1`, pay the one order with card
   5267 3181 8797 5449, enter an OTP 4-10 digits long (any value) to
   succeed. Set RAZORPAY_TEST_AUTHORIZED_PAYMENT_ID to the resulting
   razorpay_payment_id.
2. Same seed flow, but enter an OTP under 4 digits to fail it instead.
   Set RAZORPAY_TEST_FAILED_PAYMENT_ID to that payment id.

Each authorized payment is single-use: test_order_capture_refund_live
captures it, which consumes it permanently. Reseed between runs.
"""

import os

import pytest
from dotenv import load_dotenv

from rail.razorpay_client import attempt_capture, fetch_payment, refund

load_dotenv()

AUTHORIZED_PAYMENT_ID = os.environ.get("RAZORPAY_TEST_AUTHORIZED_PAYMENT_ID")
FAILED_PAYMENT_ID = os.environ.get("RAZORPAY_TEST_FAILED_PAYMENT_ID")

REFUND_FLOOR_PAISE = 100


def test_order_capture_refund_live():
    if AUTHORIZED_PAYMENT_ID is None:
        pytest.skip(
            "RAZORPAY_TEST_AUTHORIZED_PAYMENT_ID not set -- see this "
            "module's docstring to seed one."
        )

    before = fetch_payment(AUTHORIZED_PAYMENT_ID)
    if before["status"] != "authorized":
        pytest.skip(
            f"{AUTHORIZED_PAYMENT_ID} is {before['status']!r}, not "
            "'authorized' -- already consumed by a previous run, or past "
            "the manual capture window. Reseed and update the env var."
        )
    amount = before["amount"]

    capture_result = attempt_capture(AUTHORIZED_PAYMENT_ID, amount)
    assert capture_result.success, capture_result.error
    assert capture_result.payment["status"] == "captured"

    partial = amount // 2
    if partial >= REFUND_FLOOR_PAISE:
        refund(AUTHORIZED_PAYMENT_ID, partial)

    after = fetch_payment(AUTHORIZED_PAYMENT_ID)
    assert after["status"] == "captured"
    if partial >= REFUND_FLOOR_PAISE:
        assert after["amount_refunded"] == partial


def test_failure_handle():
    if FAILED_PAYMENT_ID is None:
        pytest.skip(
            "RAZORPAY_TEST_FAILED_PAYMENT_ID not set -- see this module's "
            "docstring to seed one."
        )

    payment = fetch_payment(FAILED_PAYMENT_ID)
    assert payment["status"] == "failed"

    # A capture attempt on a failed payment must not raise -- attempt_capture
    # exists specifically to turn this into a reportable result.
    result = attempt_capture(FAILED_PAYMENT_ID, payment["amount"])
    assert result.success is False
    assert result.error is not None
