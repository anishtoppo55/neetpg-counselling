"""Connection pool. Every session is read-only: the API never writes to the database."""
from __future__ import annotations

from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None


def _configure(conn) -> None:
    conn.read_only = True          # SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY
    conn.autocommit = True
    conn.row_factory = dict_row


def open_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError('DATABASE_URL is not set')
        _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=config.POOL_MAX,
                               configure=_configure, open=True, timeout=10)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection():
    with open_pool().connection() as conn:
        yield conn


def fetch(sql: str, params=None) -> list[dict]:
    with connection() as conn:
        return conn.execute(sql, params).fetchall()
