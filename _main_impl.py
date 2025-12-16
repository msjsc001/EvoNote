
# EvoNote internal entry point
# Formerly main.py
import logging
import sys
import traceback
from core.app import EvoNoteApp

def run_app():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    try:
        app = EvoNoteApp()
        return app.run()
    except Exception as e:
        print(f"=== CRASH TRACEBACK ===")
        traceback.print_exc()
        print(f"=== END TRACEBACK ===")
        raise

if __name__ == "__main__":
    sys.exit(run_app())
