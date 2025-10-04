import os
import time
import sqlite3
from pathlib import Path

from services.file_indexer_service import FileIndexerService

from whoosh.index import open_dir
from whoosh.query import Term


def assert_exists(p, message):
    if not Path(p).exists():
        raise AssertionError(message)


def run():
    vault = "."
    fis = FileIndexerService(vault)
    fis.start()
    fis.wait_for_idle()
    print("[ST-02] started")
    assert_exists(".EvoNotDB/index.db", "Missing .EvoNotDB/index.db after start")
    assert_exists(".EvoNotDB/whoosh_index", "Missing .EvoNotDB/whoosh_index after start")
    assert_exists("pages", "Missing pages/ after start")
    assert_exists("assets", "Missing assets/ after start")
    test_path = Path("pages/ST-02 SelfTest.md")
    test_path.parent.mkdir(exist_ok=True)
    test_path.write_text("# ST-02 SelfTest\n\nLink: [[Note A]]\n\nBlock: {{Hello Block}}\n", encoding="utf-8")
    time.sleep(1.2)
    fis.wait_for_idle()
    db = sqlite3.connect(".EvoNotDB/index.db")
    cur = db.cursor()
    cur.execute("SELECT path FROM files WHERE path LIKE ?", ("%ST-02 SelfTest.md",))
    rows = cur.fetchall()
    print("[ST-02] files rows:", rows)
    if len(rows) < 1:
        db.close()
        raise AssertionError("files table missing selftest")
    cur.execute("SELECT COUNT(*) FROM block_instances WHERE file_path LIKE ?", ("%ST-02 SelfTest.md",))
    cnt = cur.fetchone()[0]
    db.close()
    if cnt < 1:
        raise AssertionError("block_instances missing entry")
    idx = open_dir(".EvoNotDB/whoosh_index")
    with idx.searcher() as searcher:
        # Try multiple canonical path variants because indexer may store relative vs absolute and OS-specific separators.
        candidates = [
            str(test_path.resolve()),
            str(test_path),
            os.path.normpath(str(test_path)),
            os.path.normpath(".\\" + str(test_path)),
            os.path.normpath("./" + str(test_path)),
        ]
        found = False
        for c in candidates:
            hits = list(searcher.search(Term("path", c), limit=1))
            if hits:
                found = True
                break
        if not found:
            # Fallback: scan all stored docs and match by filename suffix (robust across path normalization differences)
            for docnum in range(searcher.doc_count_all()):
                fields = searcher.stored_fields(docnum)
                p = fields.get("path")
                if p and p.replace("/", "\\").endswith(test_path.as_posix().replace("/", "\\")):
                    found = True
                    break
        if not found:
            raise AssertionError(f"whoosh missing document for selftest; tried: {candidates}")
    print("[ST-02] rebuild_index...")
    fis.rebuild_index()
    fis.wait_for_idle()
    assert_exists(".EvoNotDB/index.db", "Missing .EvoNotDB/index.db after rebuild")
    db = sqlite3.connect(".EvoNotDB/index.db")
    cur = db.cursor()
    cur.execute("SELECT path FROM files WHERE path LIKE ?", ("%ST-02 SelfTest.md",))
    rows = cur.fetchall()
    db.close()
    if len(rows) < 1:
        raise AssertionError("files table missing after rebuild")
    fis.stop()
    print("ST-02 self-test passed")


if __name__ == "__main__":
    run()