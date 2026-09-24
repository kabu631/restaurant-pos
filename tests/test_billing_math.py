"""Bill arithmetic and Nepal date helpers — pure functions, no database."""
from datetime import date, datetime

import pytest
from fastapi import HTTPException

from app.services.billing_calc import compute_totals, validate_discount
from app.services.restaurant_settings import TaxConfig
from app.utils import nepal


def line(total, vat=True):
    return {"line_total": total, "is_vat_applicable": vat}


def test_nepal_standard_bill_1000_becomes_1243():
    t = compute_totals([line(1000)], None, 0, True, TaxConfig())
    assert t["service_charge"] == 100.0
    assert t["taxable_amount"] == 1100.0      # VAT is charged on food + service charge
    assert t["vat_amount"] == 143.0
    assert t["grand_total"] == 1243.0


def test_service_charge_switched_off_for_this_bill():
    t = compute_totals([line(1000)], None, 0, False, TaxConfig())
    assert t["service_charge"] == 0
    assert t["grand_total"] == 1130.0


def test_pan_only_restaurant_charges_no_vat():
    cfg = TaxConfig(vat_enabled=False)
    t = compute_totals([line(1000)], None, 0, True, cfg)
    assert t["vat_amount"] == 0 and t["taxable_amount"] == 0
    assert t["grand_total"] == 1100.0


def test_discount_is_applied_before_service_charge_and_vat():
    t = compute_totals([line(1000)], "percentage", 10, True, TaxConfig())
    assert t["discount_amount"] == 100.0
    assert t["service_charge"] == 90.0
    assert t["vat_amount"] == round(990 * 0.13, 2)
    assert t["grand_total"] == round(990 * 1.13, 2)


def test_flat_discount_cannot_exceed_subtotal():
    t = compute_totals([line(200)], "flat", 500, True, TaxConfig())
    assert t["discount_amount"] == 200.0
    assert t["grand_total"] == 0.0


def test_non_vat_items_are_excluded_from_taxable_amount():
    t = compute_totals([line(600, vat=True), line(400, vat=False)], None, 0, True, TaxConfig())
    # 60 % of (1000 + 100 service charge) is taxable
    assert t["taxable_amount"] == 660.0
    assert t["non_taxable_amount"] == 440.0
    assert t["vat_amount"] == 85.8


def test_custom_rates():
    cfg = TaxConfig(vat_rate=13, service_rate=5)
    t = compute_totals([line(1000)], None, 0, True, cfg)
    assert t["grand_total"] == round(1050 * 1.13, 2)


@pytest.mark.parametrize("dtype,value", [("percentage", 101), ("flat", -1), ("bogus", 5)])
def test_invalid_discounts_are_rejected(dtype, value):
    with pytest.raises(HTTPException):
        validate_discount(dtype, value)


def test_fiscal_year_turns_over_on_16_july():
    assert nepal.fiscal_year(date(2026, 7, 15)) == "2082/83"
    assert nepal.fiscal_year(date(2026, 7, 16)) == "2083/84"
    start, end = nepal.fiscal_year_bounds("2083/84")
    assert start == datetime(2026, 7, 16) and end == datetime(2027, 7, 16)


def test_iso_adds_nepal_offset_to_stored_times():
    assert nepal.iso(datetime(2026, 9, 24, 19, 30)) == "2026-09-24T19:30:00+05:45"
    assert nepal.iso(None) is None


def test_day_bounds_are_half_open():
    start, end = nepal.day_bounds(date(2026, 9, 24))
    assert (start, end) == (datetime(2026, 9, 24), datetime(2026, 9, 25))
