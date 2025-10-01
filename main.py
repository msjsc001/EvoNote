# EvoNote main entry point
import sys
from core.app import EvoNoteApp

if __name__ == "__main__":
    app = EvoNoteApp()
    sys.exit(app.run())
