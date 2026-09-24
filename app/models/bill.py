from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base
from app.utils import nepal


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        UniqueConstraint("bill_number", "restaurant_id", name="uq_bill_per_restaurant"),
    )

    id             = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id  = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    order_id       = Column(Integer, ForeignKey("orders.id"), nullable=False)
    bill_number    = Column(String, nullable=False)   # e.g. 2081/82-000001
    subtotal       = Column(Float, nullable=False)
    discount_type  = Column(String, nullable=True)    # percentage / flat / NULL
    discount_value = Column(Float, default=0.0)
    discount_amount= Column(Float, default=0.0)
    taxable_amount = Column(Float, nullable=False)    # amount subject to VAT (incl. service charge)
    vat_amount     = Column(Float, default=0.0)       # 13% VAT
    service_charge = Column(Float, default=0.0)       # 10% service charge
    grand_total    = Column(Float, nullable=False)
    payment_method = Column(String, nullable=True)    # cash/card/qr/esewa/khalti/bank, or "split"
    payment_status = Column(String, default="unpaid") # paid / unpaid / void
    cashier_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    customer_pan   = Column(String, nullable=True)
    customer_name  = Column(String, nullable=True)
    is_printed     = Column(Boolean, default=False)
    print_count    = Column(Integer, default=0)       # IRD reprint tracking
    synced_to_cbms = Column(Boolean, default=False)
    cbms_sync_at   = Column(DateTime, nullable=True)
    fiscal_year    = Column(String, nullable=True)    # e.g. 2081/82
    fonepay_prn    = Column(String, nullable=True, unique=True)
    created_at     = Column(DateTime, default=nepal.now, server_default=func.now())
    updated_at     = Column(DateTime, default=nepal.now, server_default=func.now(), onupdate=nepal.now)


class BillPayment(Base):
    """One tender against a bill — a bill paid by cash + card has two rows."""
    __tablename__ = "bill_payments"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    bill_id       = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    method        = Column(String, nullable=False)    # cash/card/qr/esewa/khalti/bank
    amount        = Column(Float, nullable=False)     # amount applied to the bill
    tendered      = Column(Float, nullable=True)      # cash handed over; change = tendered - amount
    reference     = Column(String, nullable=True)     # wallet / card transaction id
    received_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime, default=nepal.now, server_default=func.now())
