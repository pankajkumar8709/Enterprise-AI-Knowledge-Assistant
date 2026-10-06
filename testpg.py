"""Scratch connectivity check for the local PostgreSQL instance.

Credentials come from the environment so nothing sensitive is committed
(audit F-004). Set PGPASSWORD (and optionally PGHOST/PGPORT/PGDATABASE/PGUSER).
"""

import os

import psycopg

conn = psycopg.connect(
    host=os.environ.get("PGHOST", "localhost"),
    port=int(os.environ.get("PGPORT", "5432")),
    dbname=os.environ.get("PGDATABASE", "enterprise_ai_ka"),
    user=os.environ.get("PGUSER", "postgres"),
    password=os.environ.get("PGPASSWORD", ""),
)

print("Connected successfully!")

conn.close()