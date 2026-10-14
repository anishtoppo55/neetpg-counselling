"""Database connection, migrations and bulk loading helpers."""
from __future__ import annotations

from contextlib import contextmanager

import psycopg

from . import settings


@contextmanager
def connect():
    if not settings.DATABASE_URL:
        raise SystemExit('DATABASE_URL is not set (run inside docker compose, or export it).')
    with psycopg.connect(settings.DATABASE_URL) as conn:
        yield conn


def migrate(conn) -> list[str]:
    """Apply migrations/NNN_*.sql in order; each file runs once (tracked in schema_migrations)."""
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
    done = {r[0] for r in conn.execute('SELECT version FROM schema_migrations')}
    applied = []
    for f in sorted(settings.MIGRATIONS_DIR.glob('*.sql')):
        if f.stem in done:
            continue
        with conn.transaction():
            conn.execute(f.read_text())
            conn.execute('INSERT INTO schema_migrations (version) VALUES (%s)', (f.stem,))
        applied.append(f.stem)
    return applied


def copy_rows(conn, table: str, columns: list[str], rows) -> int:
    """COPY an iterable of tuples into table(columns)."""
    n = 0
    with conn.cursor() as cur:
        with cur.copy(f'COPY {table} ({", ".join(columns)}) FROM STDIN') as cp:
            for r in rows:
                cp.write_row(r)
                n += 1
    return n
