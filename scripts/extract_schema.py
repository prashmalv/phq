"""
Run this on any machine connected to ZeroTier VPN.
It prints the full schema of up_police_matrix database.
Share the output with the dev team.

Usage:
  pip install pymysql
  python scripts/extract_schema.py
"""
import pymysql, json

conn = pymysql.connect(
    host="10.242.71.180",
    user="readUser",
    password="readUser@123",
    database="up_police_matrix",
    charset="utf8mb4",
)
cursor = conn.cursor()

cursor.execute("SHOW TABLES")
tables = [r[0] for r in cursor.fetchall()]
print(f"\nTables found: {tables}\n")

schema = {}
for table in tables:
    cursor.execute(f"DESCRIBE `{table}`")
    columns = [{"field": r[0], "type": r[1], "null": r[2], "key": r[3], "default": r[4]} for r in cursor.fetchall()]
    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
    row_count = cursor.fetchone()[0]
    schema[table] = {"columns": columns, "row_count": row_count}
    print(f"\n--- TABLE: {table} ({row_count:,} rows) ---")
    for col in columns:
        print(f"  {col['field']:30s} {col['type']:25s} key={col['key']}")

# Sample 2 rows from each table
print("\n\n=== SAMPLE DATA ===")
for table in tables:
    cursor.execute(f"SELECT * FROM `{table}` LIMIT 2")
    rows = cursor.fetchall()
    col_names = [d[0] for d in cursor.description]
    print(f"\n--- {table} (columns: {col_names})")
    for row in rows:
        sample = {col_names[i]: str(v)[:80] for i, v in enumerate(row)}
        print(json.dumps(sample, ensure_ascii=False, indent=2))

cursor.close()
conn.close()
print("\n\nDone. Share this output with the dev team.")
