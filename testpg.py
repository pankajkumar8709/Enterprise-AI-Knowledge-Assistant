import psycopg

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="enterprise_ai_ka",
    user="postgres",
    password="Pankaj@39"
)

print("Connected successfully!")

conn.close()