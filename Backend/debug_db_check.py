import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
print('DATABASE_URL=', DATABASE_URL)
if not DATABASE_URL:
    raise SystemExit('DATABASE_URL missing')
engine = create_engine(DATABASE_URL, echo=False, future=True)
with engine.connect() as conn:
    print('SCHEME counts:')
    result = conn.execute(text('SELECT eligible_scheme, COUNT(*) AS cnt FROM fra_documents GROUP BY eligible_scheme ORDER BY cnt DESC'))
    for row in result:
        print(row.eligible_scheme, row.cnt)
    print('TOTAL records:', conn.execute(text('SELECT COUNT(*) FROM fra_documents')).scalar())
    print('Scheme table:')
    result = conn.execute(text('SELECT id, name FROM schemes ORDER BY id'))
    for row in result:
        print(row.id, row.name)
