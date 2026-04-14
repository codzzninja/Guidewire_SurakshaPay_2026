"""Quick SQLite peek for Docker/local — usage: python scripts/peek_db.py [path]"""
import sqlite3
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "/app/data/surakshapay.db"
con = sqlite3.connect(path)
cur = con.cursor()
print("TABLES:", [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")])
print("\nusers (id, phone, zone_id):")
for r in cur.execute("SELECT id, phone, zone_id FROM users"):
    print(" ", r)
con.close()
