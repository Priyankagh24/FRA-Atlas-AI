import psycopg2
import os
import json
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def insert_scheme(name: str, description: str, eligibility: dict):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO schemes (name, description, eligibility) VALUES (%s, %s, %s) RETURNING id",
        (name, description, json.dumps(eligibility)),
    )
    scheme_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return scheme_id


def get_scheme_by_name(name: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, description, eligibility FROM schemes WHERE name ILIKE %s",
        (name,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "description": row[2], "eligibility": row[3]}


def fetch_schemes():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, eligibility FROM schemes")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "description": r[2], "eligibility": r[3]}
        for r in rows
    ]


def _json_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def write_dss_log(user_query: str, parsed: dict, scheme_id: int, count: int, sample: list):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO dss_logs (user_query, parsed, scheme_id, result_count, sample)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            user_query,
            json.dumps(parsed, default=_json_serializer),
            scheme_id,
            count,
            json.dumps(sample, default=_json_serializer),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()
