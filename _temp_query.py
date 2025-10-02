import sqlite3
import os

db_path = os.path.join('.enotes', 'index.db')

if not os.path.exists(db_path):
    print(f"Database file not found at: {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("--- Querying 'links' table ---")
        cursor.execute("SELECT target_path FROM links")
        links_results = cursor.fetchall()
        print(f"Results: {links_results}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()