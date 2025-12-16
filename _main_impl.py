
# EvoNote internal entry point
# Formerly main.py
import logging
import sys
from core.app import EvoNoteApp

def run_app():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    app = EvoNoteApp()
    return app.run()

if __name__ == "__main__":
    sys.exit(run_app())
