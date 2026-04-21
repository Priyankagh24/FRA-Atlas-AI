from db import engine
from sqlalchemy import text
import json

def get_coords():
    query = text("SELECT claim_id, patta_holder_name, coordinates, village_name, state FROM fra_documents WHERE patta_holder_name LIKE '%Sukhram Baiga%'")
    with engine.connect() as conn:
        res = conn.execute(query).mappings().all()
        for r in res:
            print(dict(r))

if __name__ == "__main__":
    get_coords()
