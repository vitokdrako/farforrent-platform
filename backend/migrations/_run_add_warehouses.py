#!/usr/bin/env python3
"""Run multi-warehouse migration against the configured RH DB."""
import os, sys, urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('/app/backend/.env')

host = os.environ.get('RH_DB_HOST')
user = os.environ.get('RH_DB_USERNAME')
pwd = os.environ.get('RH_DB_PASSWORD')
db = os.environ.get('RH_DB_DATABASE')
url = f'mysql+pymysql://{user}:{urllib.parse.quote_plus(pwd)}@{host}:3306/{db}?charset=utf8mb4'
print(f'Connecting to {host}/{db}...')
e = create_engine(url)

with open('/app/backend/migrations/add_warehouses_multi_v1.sql', 'r', encoding='utf-8') as f:
    sql_text = f.read()

statements = []
for s in sql_text.split(';'):
    s = s.strip()
    if not s: continue
    non_comment = [l for l in s.split('\n') if l.strip() and not l.strip().startswith('--')]
    if not non_comment: continue
    statements.append(s)

print(f'Running {len(statements)} statements...')
with e.begin() as conn:
    for i, st in enumerate(statements, 1):
        try:
            conn.execute(text(st))
            preview = st[:80].replace('\n', ' ')
            print(f'  [{i:02d}] OK — {preview}')
        except Exception as ex:
            msg = str(ex)[:300]
            print(f'  [{i:02d}] ERR: {msg}')
            if 'already exists' not in msg.lower() and 'duplicate' not in msg.lower() and '1062' not in msg:
                raise
print('✅ Migration done')
