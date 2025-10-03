#!/usr/bin/env python3
import sqlite3, os, sys, traceback

DB_PATH = ".enotes/index.db"

def print_header():
    print("=== EvoNote Completion DB Prefix Query Test (He) ===")
    print(f"DB_PATH: {DB_PATH}")
    print(f"DB_EXISTS: {os.path.exists(DB_PATH)}")

def list_compile_options(conn):
    try:
        opts = [row[0] for row in conn.execute("PRAGMA compile_options").fetchall()]
    except Exception as e:
        opts = []
    print("COMPILE_OPTIONS:", ",".join(opts))
    print("FTS5_ENABLED:", any("ENABLE_FTS5" in s for s in opts))

def run_sql(conn, sql, label):
    print(f"\n-- {label} --")
    print(f"SQL: {sql}")
    try:
        cur = conn.execute(sql)
        rows = cur.fetchall()
        contents = [r[0] for r in rows]
        print(f"ROW_COUNT: {len(contents)}")
        for c in contents:
            try:
                print("ROW:", c)
            except Exception:
                print("ROW: <non-printable>")
        return contents, None
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return [], e

def main():
    print_header()
    if not os.path.exists(DB_PATH):
        print("FATAL: DB missing")
        sys.exit(2)
    conn = sqlite3.connect(DB_PATH)
    try:
        list_compile_options(conn)
    except Exception:
        pass
    fts_sql = "SELECT content FROM blocks_fts WHERE content MATCH 'He*';"
    like_sql = "SELECT content FROM blocks WHERE content LIKE 'He%';"
    fts_rows, fts_err = run_sql(conn, fts_sql, "FTS_QUERY")
    used = None
    results = []
    if fts_rows:
        used = "FTS"
        results = fts_rows
    else:
        results, like_err = run_sql(conn, like_sql, "LIKE_QUERY")
        used = "LIKE" if results else "NONE"
    found_hw = any(s == "Hello World" for s in results)
    print("\n== SUMMARY ==")
    print("USED:", used)
    print("FOUND_HELLO_WORLD:", found_hw)
    sys.exit(0)

if __name__ == "__main__":
    main()