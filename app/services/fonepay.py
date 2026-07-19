"""
FonePay Nepal merchant payment service.

Docs reference: https://developer.fonepay.com/
Credentials come from app.config (set via env vars in production).
"""
import hashlib
import hmac
import uuid
from datetime import datetime

import httpx

from app.config import (
    FONEPAY_BASE_URL,
    FONEPAY_CALLBACK_BASE,
    FONEPAY_MERCHANT_CODE,
    FONEPAY_MERCHANT_PASSWORD,
    FONEPAY_SECRET_KEY,
)

_QR_PATH = "merchant/merchantDetailsForThirdParty"


def _prn_for_bill(bill_id: int) -> str:
    """Unique payment reference number per bill (≤ 25 chars, alphanumeric)."""
    return f"BILL{bill_id}-{uuid.uuid4().hex[:8].upper()}"


def _fmt_date() -> str:
    """FonePay expects date as MM/DD/YYYY."""
    return datetime.now().strftime("%m/%d/%Y")


def _compute_hash(*fields: str) -> str:
    """HMAC-SHA512 of comma-joined fields, hex-uppercased."""
    message = ",".join(fields)
    return hmac.new(
        FONEPAY_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha512,
    ).hexdigest().upper()


def build_qr_payload(bill_id: int, amount: float, remarks: str = "Food Bill") -> dict:
    """
    Build the form-data payload for FonePay QR initiation.
    Returns the full payload dict including the computed hashCode.
    """
    prn = _prn_for_bill(bill_id)
    dt  = _fmt_date()
    crn = "NPR"
    r1  = remarks[:50]
    r2  = "RestaurantPOS"
    ru  = f"{FONEPAY_CALLBACK_BASE}/api/billing/fonepay/callback"
    amt = f"{amount:.2f}"

    hash_code = _compute_hash(
        FONEPAY_MERCHANT_CODE,
        FONEPAY_MERCHANT_PASSWORD,
        prn, amt, crn, dt, r1, r2, ru,
    )

    return {
        "prn": prn,
        "payload": {
            "PID": FONEPAY_MERCHANT_CODE,
            "MD":  FONEPAY_MERCHANT_PASSWORD,
            "PRN": prn,
            "AMT": amt,
            "CRN": crn,
            "DT":  dt,
            "R1":  r1,
            "R2":  r2,
            "RU":  ru,
            "hashCode": hash_code,
        },
    }


async def initiate_qr(bill_id: int, amount: float, remarks: str = "Food Bill") -> dict:
    """
    Call FonePay API and return:
        { "prn": str, "qr_data": str, "qr_image": str|None }

    qr_data  — the raw QR string (can be rendered client-side with qrcode.js)
    qr_image — base64 PNG if FonePay returns one, else None
    """
    built = build_qr_payload(bill_id, amount, remarks)
    url   = FONEPAY_BASE_URL.rstrip("/") + "/" + _QR_PATH

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=built["payload"])

    resp.raise_for_status()
    data = resp.json()

    # FonePay response shape (production):
    # { "success": true, "qrMessage": "<QR string>", "remarks": "..." }
    # Some endpoints return base64 image in "qrImage".
    qr_message = data.get("qrMessage") or data.get("qrData") or ""
    qr_image   = data.get("qrImage") or data.get("qrBase64") or None

    return {
        "prn":      built["prn"],
        "qr_data":  qr_message,
        "qr_image": qr_image,
    }


def verify_callback(prn: str, bid: str, amt: str, uid: str,
                    bc: str, ini: str, received_hash: str) -> bool:
    """
    Verify the HMAC-SHA512 signature FonePay sends in the payment callback.
    Returns True if the callback is authentic.
    """
    expected = _compute_hash(prn, bid, amt, uid, bc, ini)
    return hmac.compare_digest(expected, received_hash.upper())
