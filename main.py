
#!/usr/bin/env python3
"""
EvoNote Bootstrapper
--------------------
This script ensures the environment is ready before launching the app.
It automatically installs dependencies from requirements.txt if PySide6 is missing.
"""
import sys
import subprocess
import os
from pathlib import Path

def ensure_dependencies():
    """
    Check if critical dependencies (PySide6) are installed. 
    If not, attempt to install from requirements.txt.
    """
    try:
        import PySide6
        return True
    except ImportError:
        print("EvoNote: Critical dependencies missing. Attempting to auto-install...")
        
    # Locate requirements.txt
    root = Path(__file__).parent
    req_path = root / "requirements.txt"
    if not req_path.exists():
        print(f"ERROR: requirements.txt not found at {req_path}. Cannot install dependencies.")
        return False

    # Install
    try:
        print(f"Installing from {req_path}...")
        # Use the current python interpreter executable
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_path)])
        print("Dependencies installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install dependencies: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error during installation: {e}")
        return False

def main():
    if not ensure_dependencies():
        print("Startup Aborted: Environment check failed.")
        input("Press Enter to exit...")
        sys.exit(1)

    # Now that dependencies are present, import and run the real app
    try:
        from _main_impl import run_app
        sys.exit(run_app())
    except ImportError as e:
        print(f"Startup Logic Error: Could not import _main_impl: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Runtime Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
