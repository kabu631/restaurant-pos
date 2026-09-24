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

Supported path formats:
  - Windows COM port:  "COM3"
  - Linux USB device:  "/dev/usb/lp0"
  - Network (IP):      "192.168.1.100"   (uses port 9100)

When no printer is configured the browser print pages (/receipt, /kot-print)
are used instead.
"""
import logging
import threading
from datetime import datetime
from typing import Callable

_log = logging.getLogger(__name__)

W = 42  # characters per line on an 80mm roll


def _get_printer(path: str):
    """Return an escpos Printer instance for the given path, or raise."""
    try:
        from escpos import printer as ep
    except ImportError:
        raise RuntimeError("python-escpos is not installed")

    path = (path or "").strip()
    if not path:
        raise RuntimeError("No thermal printer configured (Settings → Receipt & Print)")

    if path.upper().startswith("COM") or path.startswith("/dev/"):
        return ep.Serial(path, baudrate=9600)

    # Assume IP address, optionally with :port
    host, _, port = path.partition(":")
    return ep.Network(host, port=int(port or 9100))


def _divider(char: str = "-", width: int = W) -> str:
    return char * width


def _money(value) -> str:
    return f"{float(value or 0):,.2f}"


def _run(job: Callable, path: str, label: str) -> dict:
    try:
        p = _get_printer(path)
    except Exception as exc:
        _log.warning("Thermal printer unavailable for %s: %s", label, exc)
        return {"ok": False, "detail": str(exc)}
    try:
        job(p)
        p.cut()
        return {"ok": True}
    except Exception as exc:
        _log.exception("%s print failed", label)
        return {"ok": False, "detail": str(exc)}
    finally:
        try:
            p.close()
        except Exception:
            pass


def print_receipt(bill: dict, restaurant: dict, printer_path: str = "") -> dict:
    """Print a bill receipt.  bill = billing._bill_response(); restaurant has
    name, address, phone, vat_number and optionally receipt_footer."""
    def job(p):
        p.set(align="center", bold=True, double_height=True, double_width=False)
        p.text(restaurant.get("name", "RESTAURANT") + "\n")
        p.set(align="center", bold=False, double_height=False)
        for key, prefix in (("address", ""), ("phone", "Tel: "), ("vat_number", "PAN/VAT: ")):
            if restaurant.get(key):
                p.text(prefix + restaurant[key] + "\n")
        p.text(("TAX INVOICE" if bill.get("vat_amount") else "INVOICE") + "\n")
        if (bill.get("print_count") or 0) > 1:
            p.text(f"COPY OF ORIGINAL - {bill['print_count'] - 1}\n")
        p.text(_divider("=") + "\n")

        p.set(align="left")
        p.text(f"Bill No : {bill.get('bill_number', '')}\n")
        p.text(f"Date    : {bill.get('date_display', '')}\n")
        if bill.get("table_number"):
            p.text(f"Table   : {bill['table_number']}\n")
        if bill.get("customer_name"):
            p.text(f"Customer: {bill['customer_name']}\n")
        if bill.get("customer_pan"):
            p.text(f"PAN     : {bill['customer_pan']}\n")
        if bill.get("cashier_name"):
            p.text(f"Cashier : {bill['cashier_name']}\n")
        p.text(_divider() + "\n")

        p.set(bold=True)
        p.text(f"{'Item':<20} {'Qty':>4} {'Rate':>7} {'Amt':>8}\n")
        p.set(bold=False)
        for item in bill.get("items", []):
            p.text(f"{item['name'][:20]:<20} {item['quantity']:>4} "
                   f"{item['unit_price']:>7.2f} {item['line_total']:>8.2f}\n")
        p.text(_divider() + "\n")

        def row(label, value):
            p.text(f"{label:<28}{value:>14}\n")

        row("Subtotal", _money(bill.get("subtotal")))
        if bill.get("discount_amount"):
            row("Discount", "-" + _money(bill["discount_amount"]))
        if bill.get("service_charge"):
            row(f"Service Charge ({bill.get('service_charge_rate') or 10:g}%)",
                _money(bill["service_charge"]))
        if bill.get("vat_amount"):
            row("Taxable Amount", _money(bill.get("taxable_amount")))
            row(f"VAT ({bill.get('vat_rate') or 13:g}%)", _money(bill["vat_amount"]))
        p.text(_divider() + "\n")
        p.set(bold=True)
        row("TOTAL (NPR)", _money(bill.get("grand_total")))
        p.set(bold=False)
        for pay in bill.get("payments", []):
            row(pay.get("label") or pay["method"].upper(), _money(pay["amount"]))
        if bill.get("change"):
            row("Change", _money(bill["change"]))
        p.text(_divider("=") + "\n")

        p.set(align="center")
        p.text(restaurant.get("receipt_footer") or "Thank you for dining with us!")
        p.text("\n")
    return _run(job, printer_path, "Receipt")


def print_kot(ticket: dict, printer_path: str = "") -> dict:
    """Print a Kitchen Order Ticket.  ticket: kot_number, order_id, order_type,
    table_number, waiter_name, station, items [{name, quantity, notes}]."""
    def job(p):
        station = (ticket.get("station") or "kitchen").upper()
        p.set(align="center", bold=True, double_height=True)
        p.text(f"{'BOT' if station == 'BAR' else 'KOT'} #{ticket.get('kot_number') or '-'}\n")
        where = (f"TABLE {ticket['table_number']}" if ticket.get("table_number")
                 else (ticket.get("order_type") or "").replace("_", " ").upper())
        p.text(where + "\n")
        p.set(bold=False, double_height=False)
        p.text(_divider("=") + "\n")
        p.set(align="left")
        p.text(f"Order  : #{ticket.get('order_id')}\n")
        if ticket.get("waiter_name"):
            p.text(f"Waiter : {ticket['waiter_name']}\n")
        p.text(f"Time   : {ticket.get('time') or datetime.now().strftime('%H:%M')}\n")
        p.text(_divider() + "\n")
        for item in ticket.get("items", []):
            p.set(bold=True, double_height=True)
            p.text(f"{item.get('quantity', 1):>3} x {item.get('name', '')[:30]}\n")
            p.set(bold=False, double_height=False)
            if item.get("notes"):
                p.text(f"      ** {item['notes'][:34]} **\n")
        p.text(_divider("=") + "\n")
    return _run(job, printer_path, "KOT")


def print_async(fn: Callable, *args) -> None:
    """Fire-and-forget print so a slow or missing printer never blocks a request."""
    threading.Thread(target=fn, args=args, name="thermal-print", daemon=True).start()


def test_print(printer_path: str = "") -> dict:
    """Print a test page to verify the printer is working."""
    def job(p):
        p.set(align="center", bold=True)
        p.text("=== PRINTER TEST ===\n")
        p.set(bold=False)
        p.text("Restaurant POS\n")
        p.text("Thermal printer is working!\n")
        p.text("===================\n")
    return _run(job, printer_path, "Test")
