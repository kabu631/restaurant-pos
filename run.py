import os
import socket
import sys
import time
import webbrowser
import threading
import uvicorn
from app.config import HOST, PORT, DATA_DIR

# Auto-reload is for development only (POS_RELOAD=true); it doubles memory use in the shop.
RELOAD = os.getenv("POS_RELOAD", "false").lower() == "true"


def local_url() -> str:
    host = "127.0.0.1" if HOST in ("0.0.0.0", "::", "") else HOST
    return f"http://{host}:{PORT}"


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # no packet is sent
            return s.getsockname()[0]
    except OSError:
        return ""


def open_browser():
    time.sleep(1.5)
    webbrowser.open(local_url())


def main():
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "backups"), exist_ok=True)

    print("=" * 60)
    print("  Restaurant Management & Billing System")
    print("=" * 60)
    print(f"  This computer : {local_url()}")
    if HOST in ("0.0.0.0", "::"):
        ip = lan_ip()
        if ip:
            print(f"  Other devices : http://{ip}:{PORT}   (waiter phones, kitchen tablet)")
    else:
        print("  Other devices : off — set HOST=0.0.0.0 in .env to connect")
        print("                  phones and the kitchen tablet over Wi-Fi")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    # Open browser after a short delay
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        uvicorn.run(
            "app.main:app",
            host=HOST,
            port=PORT,
            reload=RELOAD,
            reload_dirs=["app", "frontend"] if RELOAD else None,
        )
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
