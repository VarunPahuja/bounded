"""Seed N authorized-but-uncaptured payments, outside the agent's action
space. The agent's action space is capture / refund / payout -- all
server-side, no browser. Payment creation is not in it: in a real
merchant setup the customer pays, the merchant (or its agent) captures
and refunds. This script plays the customer, once, offscreen, ahead of
time -- never at demo time and never on the agent's path.

Run this 24-48h before recording, not the night before and not minutes
before. See docs/DEMO.md's pre-record checklist and
.claude/skills/razorpay-testmode/SKILL.md for why: Razorpay's own docs
disagree on the exact auto-refund window for an authorized-but-uncaptured
payment (3 vs 5 days depending on the page), so 24-48h clears either
figure with a full day or two of margin instead of being read as safe
only under the more generous one.

DEFAULT_AMOUNT_PAISE is chosen from what was actually learned building
this: Razorpay enforces a hard floor of INR 1.00 (100 paise) on every
individual refund call, checked per-call, not against the running total
(BadRequestError: "The amount must be atleast INR 1.00" -- confirmed
empirically, see the skill). At the floor, a "partial" or "split" refund
demo is a degenerate edge case, not a convincing one. 100000 paise
(Rs 1,000) sits in the same order of magnitude as the cap figures already
used in docs/DEMO.md's mandate example (Rs 4,000-15,000), leaves a two-leg
split refund (e.g. Rs 300 + Rs 300) an order of magnitude above the floor
on each leg, and reads as real money on camera instead of a token amount.
"""

from __future__ import annotations

import argparse
import time
import webbrowser
from pathlib import Path

from rail.config import KEY_ID
from rail.razorpay_client import create_order

DEFAULT_AMOUNT_PAISE = 100_000  # Rs 1,000
DEFAULT_COUNT = 5

_CHECKOUT_TEMPLATE = """<!doctype html>
<html><body>
<h3>Seed orders -- click each button, pay with card 5267 3181 8797 5449
(mock OTP), close the tab when done. UPI is not enabled in test-mode
Checkout by default; use the card.</h3>
{buttons}
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
function pay(orderId, amount, btnId) {{
    var options = {{
        "key": "{key_id}",
        "amount": String(amount),
        "currency": "INR",
        "name": "bounded seed",
        "description": "seed auth-only payment " + orderId,
        "order_id": orderId,
        "handler": function (response) {{
            document.getElementById(btnId).outerHTML =
                "<pre>" + JSON.stringify(response, null, 2) + "</pre>";
        }}
    }};
    new Razorpay(options).open();
}}
</script>
</body></html>
"""

_BUTTON_TEMPLATE = (
    '<p><button id="{btn_id}" onclick="pay(\'{order_id}\', {amount}, '
    "'{btn_id}')\">Pay order {order_id} (Rs {rupees})</button></p>"
)


def seed(count: int, amount_paise: int, receipt_prefix: str) -> list[dict]:
    orders = []
    for i in range(count):
        order = create_order(
            amount_paise,
            receipt=f"{receipt_prefix}_{int(time.time())}_{i}",
            capture=False,  # payment_capture: 0 -- manual capture, on purpose
        )
        orders.append(order)
    return orders


def write_checkout_page(orders: list[dict], amount_paise: int, out_path: Path) -> None:
    buttons = "\n".join(
        _BUTTON_TEMPLATE.format(
            btn_id=f"btn{i}",
            order_id=o["id"],
            amount=amount_paise,
            rupees=amount_paise // 100,
        )
        for i, o in enumerate(orders)
    )
    out_path.write_text(
        _CHECKOUT_TEMPLATE.format(buttons=buttons, key_id=KEY_ID), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--amount", type=int, default=DEFAULT_AMOUNT_PAISE)
    parser.add_argument("--receipt-prefix", default="seed")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    orders = seed(args.count, args.amount, args.receipt_prefix)
    for o in orders:
        print(f"order.create -> {o['id']} ({o['amount']} paise, {o['status']})")

    out_path = Path(__file__).parent / "seed_checkout.html"
    write_checkout_page(orders, args.amount, out_path)
    print(f"\nWrote {out_path}")
    print(
        f"Open it and pay all {len(orders)} orders with card "
        "5267 3181 8797 5449 (mock OTP) to leave them authorized, uncaptured."
    )

    if not args.no_open:
        webbrowser.open(str(out_path))


if __name__ == "__main__":
    main()
