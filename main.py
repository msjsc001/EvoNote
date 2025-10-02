# EvoNote main entry point
import sys
import logging
from core.app import EvoNoteApp

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    app = EvoNoteApp()
    sys.exit(app.run())
