# Restaurant Management & Billing System

A lightweight, offline-first restaurant management and billing system for Nepal.
IRD/CBMS compliant. Built with Python (FastAPI) + SQLite + HTML/Tailwind CSS.

## Features

- Billing with 13% VAT and 10% service charge (IRD compliant)
- Kitchen Order Tickets (KOT) and Bill of Treatment (BOT)
- QR-based customer self-ordering (no app required)
- Per-dish profit tracking with ingredient cost mapping
- Offline-first: works during internet outages, syncs when back online
- Fiscal year invoice numbering (Nepal BS calendar)
- Immutable audit trail for IRD certification
- Thermal printer support

## Tech Stack

| Layer      | Technology                      |
|------------|---------------------------------|
| Backend    | Python 3.12 + FastAPI           |
| Database   | SQLite + SQLAlchemy ORM         |
| Frontend   | HTML + Tailwind CSS + JS        |
| Printing   | python-escpos (thermal)         |
| PDF        | ReportLab (IRD invoices)        |
| Packaging  | PyInstaller (Windows .exe)      |

## Installation

1. Install Python 3.12+
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the app:
   ```
   python run.py
   ```
4. Browser opens automatically at http://localhost:8000

## Default Login

| Role    | Username  | Password  |
|---------|-----------|-----------|
| Admin   | admin     | admin123  |
| Cashier | cashier1  | cash123   |
| Waiter  | waiter1   | wait123   |
| Kitchen | kitchen1  | kit123    |

## Build Windows Installer

```
python scripts/create_installer.py
```

## Target Market

Nepal — IRD/CBMS compliant from day one.
