from db import engine
from sqlalchemy import text
import sys

def repair():
    try:
        with engine.begin() as conn:
            # We map Vikram Singh to Agartala, Tripura since Aizawl is in Mizoram but state was Tripura
            coords = "23.8315, 91.2859"
            res = conn.execute(
                text("UPDATE fra_documents SET coordinates = :coords WHERE patta_holder_name LIKE '%Vikram Singh%'"),
                {"coords": coords}
            )
            print(f"✅ Successfully updated {res.rowcount} records for Vikram Singh.")
    except Exception as e:
        print(f"❌ Repair failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    repair()
