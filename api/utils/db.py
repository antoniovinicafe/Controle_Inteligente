"""
Pool de conexões com o Postgres do Supabase.

Uso típico numa rota:

    from utils.db import get_conn, put_conn

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("select * from eventos where id = %s", (evento_id,))
            row = cur.fetchone()
        conn.commit()
    finally:
        put_conn(conn)
"""

from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

from config import Config

_pool = None


def init_pool():
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=Config.DATABASE_URL,
            cursor_factory=RealDictCursor,
        )


def get_conn():
    if _pool is None:
        init_pool()
    conn = _pool.getconn()
    register_vector(conn)  # permite passar/receber np.array direto como vector
    return conn


def put_conn(conn):
    if _pool is not None:
        _pool.putconn(conn)
