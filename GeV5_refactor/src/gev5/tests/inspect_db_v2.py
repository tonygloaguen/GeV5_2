import sqlite3
from pathlib import Path

from gev5.utils.paths import GEV5_DB_PATH, BRUIT_FOND_DB_PATH

def inspect_passages():
    print("=== PASSAGES_V2 ===")
    db_path = Path(GEV5_DB_PATH)
    print(f"DB_GeV5: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Liste des tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    print("Tables :", tables)

    if "passages_v2" not in tables:
        print("⚠ Table passages_v2 introuvable !")
        conn.close()
        return

    # Colonnes
    cur.execute("PRAGMA table_info(passages_v2);")
    print("Colonnes passages_v2 :")
    for cid, name, col_type, notnull, dflt, pk in cur.fetchall():
        print(f"  - {name} ({col_type})")

    # Derniers passages
    cur.execute("SELECT * FROM passages_v2 ORDER BY rowid DESC LIMIT 5;")
    rows = cur.fetchall()
    print(f"\nDerniers passages ({len(rows)}) :")
    for r in rows:
        print(r)

    conn.close()


def inspect_bdf():
    print("\n=== BRUIT_DE_FOND (bdf_history) ===")
    db_path = Path(BRUIT_FOND_DB_PATH)
    print(f"Bruit_de_fond: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    print("Tables :", tables)

    if "bdf_history" not in tables:
        print("⚠ Table bdf_history introuvable !")
        conn.close()
        return

    cur.execute("PRAGMA table_info(bdf_history);")
    print("Colonnes bdf_history :")
    for cid, name, col_type, notnull, dflt, pk in cur.fetchall():
        print(f"  - {name} ({col_type})")

    cur.execute("SELECT * FROM bdf_history ORDER BY rowid DESC LIMIT 5;")
    rows = cur.fetchall()
    print(f"\nDerniers points de bruit de fond ({len(rows)}) :")
    for r in rows:
        print(r)

    conn.close()


if __name__ == "__main__":
    inspect_passages()
    inspect_bdf()
