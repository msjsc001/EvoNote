import os
import time
import random

# --- Configuration ---
NUM_FILES = 500
VAULT_PATH = "."  # Assumes the script is run from the vault's root directory
# ---------------------

def create_files():
    print(f"--- Creating {NUM_FILES} files... ---")
    for i in range(NUM_FILES):
        filename = f"pressure_note_{i}.md"
        with open(os.path.join(VAULT_PATH, filename), "w", encoding="utf-8") as f:
            f.write(f"# Test Note {i}\n\nThis is a link to [[pressure_note_{i+1}]].")
        if (i + 1) % 50 == 0:
            print(f"  ...created {i+1}/{NUM_FILES}")
    print("--- Creation complete. ---")

def modify_files():
    print(f"\n--- Modifying {NUM_FILES} files... ---")
    for i in range(NUM_FILES):
        filename = f"pressure_note_{i}.md"
        with open(os.path.join(VAULT_PATH, filename), "a", encoding="utf-8") as f:
            f.write(f"\n\n*Updated at {time.time()}*")
        if (i + 1) % 50 == 0:
            print(f"  ...modified {i+1}/{NUM_FILES}")
    print("--- Modification complete. ---")

def delete_files():
    print(f"\n--- Deleting {NUM_FILES} files... ---")
    for i in range(NUM_FILES):
        filename = f"pressure_note_{i}.md"
        os.remove(os.path.join(VAULT_PATH, filename))
        if (i + 1) % 50 == 0:
            print(f"  ...deleted {i+1}/{NUM_FILES}")
    print("--- Deletion complete. ---")

if __name__ == "__main__":
    print("Starting pressure test in 3 seconds. Please start interacting with the UI now.")
    time.sleep(3)
    
    create_files()
    time.sleep(5) # Give the indexer some time to catch up
    
    modify_files()
    time.sleep(5)
    
    delete_files()
    
    print("\n--- Pressure test finished. ---")
