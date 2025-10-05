import os
import sys
import traceback

"""
EvoNote V0.4.5b Smoke Test Runner

Purpose:
- Headless run of critical tests without interactive UI.
- Covers:
  1) Content-block input stability ({{ sequences) via pytest
  2) File indexer self-test (ST-02) end-to-end via scripts.st02_selftest.run()

Usage:
  - python scripts/run_smoke_tests.py            # run all
  - python scripts/run_smoke_tests.py unit       # only pytest unit (tests/test_content_block_input.py)
  - python scripts/run_smoke_tests.py selftest   # only scripts/st02_selftest.py

Notes:
  - Forces QT_QPA_PLATFORM=offscreen for headless environments.
  - Exits with code 0 on success; 1 on any failure.
"""

def _set_headless_env():
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        print("[SMOKE] QT_QPA_PLATFORM =", os.environ.get("QT_QPA_PLATFORM"))
    except Exception as e:
        print("[SMOKE][WARN] failed to set headless env:", e)


def run_pytest_unit() -> bool:
    try:
        import pytest
    except Exception as e:
        print("[SMOKE][FAIL] pytest not available:", e)
        return False
    try:
        print("[SMOKE] Running pytest unit: tests/test_content_block_input.py")
        rc = pytest.main(["-q", "tests/test_content_block_input.py"])
        ok = (rc == 0)
        print("[SMOKE] Pytest result:", "PASSED" if ok else f"FAILED(rc={rc})")
        return ok
    except Exception as e:
        print("[SMOKE][FAIL] pytest execution error:", e)
        traceback.print_exc()
        return False


def run_st02_selftest() -> bool:
    try:
        from scripts.st02_selftest import run as st_run
    except Exception as e:
        print("[SMOKE][FAIL] cannot import scripts.st02_selftest:", e)
        traceback.print_exc()
        return False
    try:
        print("[SMOKE] Running ST-02 self-test...")
        st_run()
        print("[SMOKE] ST-02 self-test PASSED")
        return True
    except Exception as e:
        print("[SMOKE][FAIL] ST-02 self-test error:", e)
        traceback.print_exc()
        return False


def main():
    _set_headless_env()
    mode = (sys.argv[1].strip().lower() if len(sys.argv) > 1 else "all")

    passed = True
    if mode in ("all", "unit"):
        ok = run_pytest_unit()
        passed = passed and ok

    if mode in ("all", "selftest"):
        ok = run_st02_selftest()
        passed = passed and ok

    print("\n[SMOKE] Summary:", "ALL PASSED" if passed else "FAILED")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()