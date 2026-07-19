import os
import sys
import time
import webbrowser
import threading
import uvicorn
from app.config import HOST, PORT, DATA_DIR

def open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT}")

def main():
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "backups"), exist_ok=True)

    print("=" * 60)
    print("  Restaurant Management & Billing System")
    print("=" * 60)
    print(f"  Starting server at http://{HOST}:{PORT}")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    # Open browser after a short delay
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        uvicorn.run(
            "app.main:app",
            host=HOST,
            port=PORT,
            reload=True,
            reload_dirs=["app", "frontend"],
        )
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
