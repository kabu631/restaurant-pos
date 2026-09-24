# Restaurant Management & Billing System

A restaurant POS and billing system for Nepal: take orders, send them to the kitchen,
book tables, and take any kind of payment — from one PC, and from waiters' phones and a
kitchen tablet over the restaurant Wi-Fi. IRD-style billing: fiscal-year invoice numbers,
VAT invoices, reprint labels and an audit trail.

Built with Python (FastAPI) + MySQL/MariaDB (XAMPP) or PostgreSQL + HTML/Tailwind CSS.
Works without internet — all scripts and styles are served locally.

## A day in the restaurant

| Who | Where | What they do |
|-----|-------|--------------|
| Waiter | **Floor** | Tap a table → tap dishes → *Send to kitchen*. The table shows **⏳ to accept** until the kitchen accepts, and a green **🔔 ready** badge when the food is done. |
| Kitchen | **Kitchen display** | New tickets beep and flash. One big button per ticket: **✓ Accept order** → *All ready* → *Served*. Accepting sends the table's total to the cashier. Kitchen and Bar each see their own items. |
| Cashier | **Billing** | Tables arrive in *Ready to bill* (with a beep) once the kitchen accepts. The customer pays last: **💳 Take payment** — cash (with change), card, FonePay, eSewa, Khalti, bank, or split — then **🖨 Print bill**. |
| Anyone | **Bookings** | Name, phone, guests, time → the best-fitting free table is suggested. When guests arrive, *Seat* opens their order. |
| Owner | **Dashboard, Reports, Settings** | Today's sales by payment method, VAT reports, staff, menu, tax and printer settings. |

The floor plan shows each table as a simple table-and-chairs icon: **green** when free, **red**
with two guests seated when occupied, **amber** when booked ahead.

### Taking orders
- Tap dishes to add them — instant, even on a slow network. Tap a line to add a kitchen note
  (“No spice”, “Less oil”… set your own quick notes in Settings).
- **Send to kitchen** saves the order and prints/sends the KOT in one tap. Unsent items are kept
  if the page is refreshed, and you're warned before leaving with unsent items.
- Item status is live: Waiting for kitchen → Accepted · cooking → Ready → Served. Move the order to another table or print a
  guest check from the ⋯ menu.
- **Once food has gone to the kitchen it can't be cancelled** — not by anyone. Until then, items can
  be changed or removed and the order cancelled; after that the order can only be closed by billing it.
  (If a dish really can't be served, give a discount on the bill.)
- **Takeaway / Delivery** from the top of the floor plan; phone numbers remember returning guests.

### Billing
Waiter sends the order → the kitchen taps **✓ Accept order** → the table's total appears in the
cashier's **Billing → Ready to bill** list (the cashier's home screen). When the customer pays,
the cashier taps **💳 Take payment**, picks the method and confirms, then prints the **final bill**
(tick *Print the bill automatically* to skip that tap). Anything still unsent goes to the kitchen
before billing.

### Kitchen tickets (KOT / BOT)
- KOT numbers run **per day** (#1 is the first ticket after midnight).
- On the **Menu** page, each category is prepared at the **Kitchen**, the **Bar** (bar ticket),
  or **No ticket** (bottled drinks go straight to “served”).
- Print from the ticket, or turn on *Settings → Kitchen & orders → Print every KOT automatically*
  (uses a thermal printer if configured, otherwise the browser print dialog).

### Payments
- Upload your **FonePay / eSewa / Khalti / bank merchant QR** in *Settings → Payments*. When the
  cashier picks that method the QR is shown full-size for the guest; check your phone, tap Confirm.
- Split a bill across several methods, apply a quick discount (5 / 10 / 15 % or any amount),
  switch off service charge for one bill, and add a customer name + PAN for business bills.
- Real FonePay merchant credentials in `.env` add a dynamic QR that confirms itself.

### How the bill is calculated
Service charge is charged on the food (after any discount), and VAT on food + service charge:

```
Food 1,000.00  →  Service charge 10 % 100.00  →  Taxable 1,100.00  →  VAT 13 % 143.00  →  Total 1,243.00
```

PAN-only (non-VAT) restaurants turn VAT off in *Settings → Tax & charges*; rates are editable there too.

## Installation

1. Install **Python 3.12+** and a database:
   - **XAMPP** — start MySQL from the XAMPP Control Panel, then in phpMyAdmin
     (http://localhost/phpmyadmin) create a database `restaurant_pos`, collation `utf8mb4_unicode_ci`; or
   - **PostgreSQL** — in pgAdmin create a database `restaurant_pos`.
2. Set up the app:
   ```
   python -m venv venv
   venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
   pip install -r requirements.txt
   copy .env.example .env         # Linux/macOS: cp .env.example .env
   ```
   Edit `DATABASE_URL` in `.env` (the XAMPP line works as-is with its default `root` user and no
   password; for PostgreSQL put in your password), and set `SECRET_KEY` to a random value
   (`python -c "import secrets; print(secrets.token_hex(32))"`).
3. Run it:
   ```
   python run.py
   ```
   Opens your browser at http://127.0.0.1:8000. With XAMPP, MySQL must already be running.
   Set `HOST=0.0.0.0` in `.env` to serve it to other devices on the network — see
   *Phones, tablets and the kitchen screen* below. For a production deployment, run it behind a
   proper ASGI server/process manager the way you would any FastAPI app (e.g.
   `uvicorn app.main:app --host 0.0.0.0 --port 8000`) instead of `run.py`, which is meant for local use.

To try everything on clean data, `python scripts/add_sample_restaurant.py` adds a
*Sample Restaurant* (code `sample`) with a menu, 14 tables and staff. To move your data between
PostgreSQL and XAMPP, use `scripts/copy_database.py --from <url> --to <url>`.

`data/restaurant_mysql.sql` and `data/restaurant_postgres.sql` are reference dumps of the current
schema with only the demo/sample accounts above — handy for setting up a new database by hand
(`mysql -u root restaurant_pos < data/restaurant_mysql.sql`, or phpMyAdmin → Import) instead of
letting the app create it on first run. They never contain real restaurant data — regenerate them
with `python scripts/add_sample_restaurant.py` against a fresh database, never by dumping a live one.

### Phones, tablets and the kitchen screen
Set `HOST=0.0.0.0` in `.env`, restart, and allow access if your firewall asks. *Settings → Devices*
then shows a QR code: scan it on any phone or tablet on the same Wi-Fi, and staff log in with their PIN.

### Default logins (brand-new database)

A fresh install creates a **demo** restaurant with a sample menu and tables. Restaurant code: `demo`.

| Role    | Username  | Password  | PIN  | Opens on |
|---------|-----------|-----------|------|----------|
| Admin   | admin     | admin123  | 0000 | Dashboard |
| Cashier | cashier1  | cash123   | 1111 | Billing |
| Waiter  | waiter1   | wait123   | 2222 | Floor |
| Kitchen | kitchen1  | kit123    | 3333 | Kitchen display |

Platform superadmin (no restaurant code): `superadmin` / `superadmin123`. **Change all of these
before going live.**

## Printing
Receipts, guest checks and KOTs are 80 mm print pages, so any printer installed in Windows works
(choose it in the print dialog once). For a direct ESC/POS connection, enter the printer's COM port
or IP in *Settings → Receipt & printing*. Reprints are labelled **COPY OF ORIGINAL - N**.

## Backups
The database is backed up every night to `data/backups/` (kept 30 days), and on demand from
*Settings → Backup*. XAMPP backups use its `mysqldump` (restore in phpMyAdmin → Import);
PostgreSQL backups use `pg_dump` (found automatically in `C:\Program Files\PostgreSQL\<version>\bin`,
or set `PG_DUMP_PATH` in `.env`) — restore with `psql -d restaurant_pos -f <backup file>`.

## Development

```
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest            # uses a throwaway SQLite database — never your real data
```

Set `POS_RELOAD=true` to auto-reload on code changes. Times are stored as Nepal time
(`app/utils/nepal.py`); bill arithmetic lives only in `app/services/billing_calc.py`.

| Layer      | Technology                                     |
|------------|------------------------------------------------|
| Backend    | Python 3.12+ + FastAPI                         |
| Database   | MySQL/MariaDB (XAMPP) or PostgreSQL + SQLAlchemy (SQLite for tests) |
| Frontend   | HTML + Tailwind CSS + JS (served locally)      |
| Printing   | Browser print pages, or python-escpos          |
