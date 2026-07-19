"""
Thermal printer service (ESC/POS).

Wraps python-escpos so that:
  - If no printer is configured or connected, every call returns a clear error
    instead of crashing the server.
  - Receipt and KOT formats are defined here; routes just call print_receipt()
    and print_kot().

Printer path is read from:
  1. The per-restaurant AppSettings key "thermal_printer_path" (if set)
  2. The THERMAL_PRINTER_PATH env var / config.py fallback
  3. Auto-detect: first USB printer found by python-escpos

Supported path formats:
  - Windows COM port:  "COM3"
  - Linux USB device:  "/dev/usb/lp0"
  - Network (IP):      "192.168.1.100"   (uses port 9100)
"""
import logging
from typing import Optional

_log = logging.getLogger(__name__)


def _get_printer(path: str):
    """Return an escpos Printer instance for the given path, or raise."""
    try:
        from escpos import printer as ep
    except ImportError:
        raise RuntimeError("python-escpos is not installed")

    path = (path or "").strip()

    if not path:
        # Try USB auto-detect
        try:
            p = ep.Usb(0, 0)   # placeholder — will be replaced by real detect
            # python-escpos ≥ 3.x auto-detects first USB printer
            p = ep.Usb()
            return p
        except Exception as exc:
            raise RuntimeError(f"No USB printer found: {exc}")

    if path.upper().startswith("COM") or path.startswith("/dev/"):
        return ep.Serial(path, baudrate=9600)

    # Assume IP address
    return ep.Network(path, port=9100)


def _center(text: str, width: int = 42) -> str:
    return text.center(width)


def _divider(char: str = "-", width: int = 42) -> str:
    return char * width


def print_receipt(bill: dict, restaurant: dict, printer_path: str = "") -> dict:
    """Print a bill receipt to the thermal printer.

    Args:
        bill: dict from billing._bill_response()
        restaurant: dict with name, address, phone, vat_number
        printer_path: optional override; falls back to config/auto-detect
    """
    try:
        from app.config import THERMAL_PRINTER_PATH
        path = printer_path or THERMAL_PRINTER_PATH
        p = _get_printer(path)
    except Exception as exc:
        _log.warning("Thermal printer unavailable: %s", exc)
        return {"ok": False, "detail": str(exc)}

    try:
        W = 42  # character width for 80mm roll

        p.set(align="center", bold=True, double_height=True, double_width=False)
        p.text(restaurant.get("name", "RESTAURANT") + "\n")
        p.set(align="center", bold=False, double_height=False)
        if restaurant.get("address"):
            p.text(restaurant["address"] + "\n")
        if restaurant.get("phone"):
            p.text("Tel: " + restaurant["phone"] + "\n")
        if restaurant.get("vat_number"):
            p.text("VAT: " + restaurant["vat_number"] + "\n")
        p.text(_divider("=", W) + "\n")

        p.set(align="left")
        p.text(f"Bill No : {bill.get('bill_number', '')}\n")
        p.text(f"Date    : {(bill.get('created_at') or '')[:19].replace('T', ' ')}\n")
        if bill.get("table_number"):
            p.text(f"Table   : {bill['table_number']}\n")
        if bill.get("order_type"):
            p.text(f"Type    : {bill['order_type'].replace('_', ' ').title()}\n")
        if bill.get("cashier_name"):
            p.text(f"Cashier : {bill['cashier_name']}\n")
        p.text(_divider("-", W) + "\n")

        # Header row
        p.set(bold=True)
        p.text(f"{'Item':<22} {'Qty':>3} {'Price':>7} {'Total':>7}\n")
        p.set(bold=False)
        p.text(_divider("-", W) + "\n")

        for item in bill.get("items", []):
            name  = item["name"][:22]
            qty   = item["quantity"]
            price = item["unit_price"]
            total = item["line_total"]
            p.text(f"{name:<22} {qty:>3} {price:>7.2f} {total:>7.2f}\n")

        p.text(_divider("-", W) + "\n")

        subtotal = bill.get("subtotal", 0)
        discount = bill.get("discount_amount", 0)
        taxable  = bill.get("taxable_amount", 0)
        vat      = bill.get("vat_amount", 0)
        svc      = bill.get("service_charge", 0)
        grand    = bill.get("grand_total", 0)

        p.text(f"{'Subtotal':<30} {subtotal:>10.2f}\n")
        if discount:
            p.text(f"{'Discount':<30} {-discount:>10.2f}\n")
        if svc:
            p.text(f"{'Service Charge (10%)':<30} {svc:>10.2f}\n")
        p.text(f"{'VAT (13%)':<30} {vat:>10.2f}\n")
        p.text(_divider("-", W) + "\n")
        p.set(bold=True)
        p.text(f"{'TOTAL':<30} {grand:>10.2f}\n")
        p.set(bold=False)
        p.text(f"{'Payment':<30} {bill.get('payment_method','').upper():>10}\n")
        p.text(_divider("=", W) + "\n")

        footer = restaurant.get("receipt_footer", "Thank you for dining with us!")
        p.set(align="center")
        p.text(footer + "\n")
        p.text("IRD Certified Bill — Please keep this receipt\n")
        p.text(_divider("=", W) + "\n")

        p.cut()
        p.close()
        return {"ok": True}

    except Exception as exc:
        _log.exception("Receipt print failed")
        try:
            p.close()
        except Exception:
            pass
        return {"ok": False, "detail": str(exc)}


def print_kot(order_id: int, kot_number: int, items: list,
              table_number: Optional[str], printer_path: str = "") -> dict:
    """Print a Kitchen Order Ticket slip."""
    try:
        from app.config import THERMAL_PRINTER_PATH
        path = printer_path or THERMAL_PRINTER_PATH
        p = _get_printer(path)
    except Exception as exc:
        _log.warning("Thermal printer unavailable for KOT: %s", exc)
        return {"ok": False, "detail": str(exc)}

    try:
        W = 42
        p.set(align="center", bold=True, double_height=True)
        p.text("KITCHEN ORDER\n")
        p.set(bold=False, double_height=False)
        p.text(_divider("=", W) + "\n")
        p.set(align="left")
        p.text(f"Order  : #{order_id}\n")
        p.text(f"KOT    : #{kot_number}\n")
        if table_number:
            p.text(f"Table  : {table_number}\n")
        from datetime import datetime
        p.text(f"Time   : {datetime.now().strftime('%H:%M:%S')}\n")
        p.text(_divider("-", W) + "\n")
        p.set(bold=True)
        p.text(f"{'Item':<30} {'Qty':>5}\n")
        p.set(bold=False)
        p.text(_divider("-", W) + "\n")
        for item in items:
            name = item.get("name", "")[:30]
            qty  = item.get("quantity", 1)
            p.text(f"{name:<30} {qty:>5}\n")
            if item.get("notes"):
                p.text(f"  ** {item['notes'][:38]} **\n")
        p.text(_divider("=", W) + "\n")
        p.cut()
        p.close()
        return {"ok": True}

    except Exception as exc:
        _log.exception("KOT print failed")
        try:
            p.close()
        except Exception:
            pass
        return {"ok": False, "detail": str(exc)}


def test_print(printer_path: str = "") -> dict:
    """Print a test page to verify the printer is working."""
    try:
        from app.config import THERMAL_PRINTER_PATH
        path = printer_path or THERMAL_PRINTER_PATH
        p = _get_printer(path)
        p.set(align="center", bold=True)
        p.text("=== PRINTER TEST ===\n")
        p.set(bold=False)
        p.text("Restaurant POS\n")
        p.text("Thermal printer is working!\n")
        p.text("===================\n")
        p.cut()
        p.close()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
