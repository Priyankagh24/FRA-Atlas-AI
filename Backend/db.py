from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# =========================
# DATABASE CONFIG
# =========================


import psycopg2
import os



from dotenv import load_dotenv
import os
print("🔗 DATABASE_URL =", engine.url)

DATABASE_URL = os.getenv("DATABASE_URL")

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Priya***567@localhost:5434/fra_db"
)




def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "fra_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "YOUR_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5434")
    )


DATABASE_URL = "postgresql+psycopg2://postgres:Priya***567@localhost:5434/fra_db"

engine: Engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# =========================
# COMMON DB ACCESS
# =========================

def get_db_connection():
    return engine.connect()

# =========================
# DSS SCHEME FUNCTIONS
# =========================

def insert_scheme(name: str, description: str, eligibility: dict):
    query = text("""
        INSERT INTO schemes (name, description, eligibility)
        VALUES (:name, :description, :eligibility)
        RETURNING id;
    """)
    with engine.begin() as conn:
        result = conn.execute(
            query,
            {
                "name": name,
                "description": description,
                "eligibility": str(eligibility)
            }
        )
        return result.scalar()


def fetch_schemes():
    query = text("SELECT * FROM schemes;")
    with engine.connect() as conn:
        return conn.execute(query).mappings().all()


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
        conn.execute(
            query,
            {
                "query_text": query_text,
                "result_count": result_count
            }
        )
