# EvoNote main entry point
import sys
from en_core.app import EvoNoteApp

if __name__ == "__main__":
    app = EvoNoteApp()
    sys.exit(app.run())
