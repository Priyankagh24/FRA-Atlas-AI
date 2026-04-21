import os
import json
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

# -------------------------
# LOAD ENV VARIABLES
# -------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL not set. Add it in .env file"
    )

# -------------------------
# SQLALCHEMY ENGINE
# -------------------------
engine: Engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

print(f"✅ DB Connected: {engine.url.host}:{engine.url.port}/{engine.url.database}")
print("🔥 USING DB:", DATABASE_URL)
# -------------------------
# RAW CONNECTION (OPTIONAL)
# -------------------------
def get_db_connection():
    """For psycopg2 (if needed)"""
    dsn = DATABASE_URL.replace("+psycopg2", "")
    return psycopg2.connect(dsn)

# -------------------------
# SCHEME FUNCTIONS
# -------------------------
def insert_scheme(name: str, description: str, eligibility: dict):
    query = text("""
        INSERT INTO schemes (name, description, eligibility)
        VALUES (:name, :description, :eligibility)
        RETURNING id;
    """)

    with engine.begin() as conn:
        result = conn.execute(query, {
            "name": name,
            "description": description,
            "eligibility": json.dumps(eligibility),
        })
        return result.scalar()

def fetch_schemes():
    query = text("SELECT id, name, description, eligibility FROM schemes;")

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
        return [dict(r) for r in rows]

def get_scheme_by_name(name: str):
    query = text(
        "SELECT * FROM schemes WHERE name ILIKE :name LIMIT 1;"
    )

    with engine.connect() as conn:
        return conn.execute(query, {"name": name}).mappings().first()

def write_dss_log(query_text: str, result_count: int):
    query = text("""
        INSERT INTO dss_logs (query_text, result_count)
        VALUES (:query_text, :result_count);
    """)

    with engine.begin() as conn:
        conn.execute(query, {
            "query_text": query_text,
            "result_count": result_count,
        })