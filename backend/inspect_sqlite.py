import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\maxst\Desktop\Projects\nbaPropsPrediction\backend\nba.sqlite")


def fetch_tables(cur):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    return [row[0] for row in cur.fetchall()]


def fetch_columns(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return cur.fetchall()


def fetch_row_count(cur, table):
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def fetch_sample_rows(cur, table, limit=5):
    cur.execute(f"SELECT * FROM {table} LIMIT {limit}")
    return cur.fetchall()


def print_table_details(cur, table):
    print(f"\n=== {table} ===")
    print(f"Row count: {fetch_row_count(cur, table)}")

    columns = fetch_columns(cur, table)
    print("Attributes:")
    for col in columns:
        cid, name, col_type, notnull, dflt_value, pk = col
        flags = []
        if pk:
            flags.append("PK")
        if notnull:
            flags.append("NOT NULL")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        default_str = f" DEFAULT {dflt_value}" if dflt_value is not None else ""
        print(f"  - {name}: {col_type}{flag_str}{default_str}")

    rows = fetch_sample_rows(cur, table, limit=5)
    print("First 5 rows:")
    if rows:
        for row in rows:
            print(row)
    else:
        print("  <empty>")


def main():
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    tables = fetch_tables(cur)
    print("Tables:")
    for t in tables:
        print(f" - {t}")

    for table in tables:
        print_table_details(cur, table)

    conn.close()


if __name__ == "__main__":
    main()
