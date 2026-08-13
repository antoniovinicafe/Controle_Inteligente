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

import time

from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

from config import Config

_pool = None

# Quanto tempo tratar o banco como fora de alcance depois de uma falha,
# sem tentar de novo.
#
# Sem isto, cada leitura da porta durante uma queda de internet esperaria o
# tempo de espera inteiro antes de cair no plano B - e o leitor pergunta a
# cada 1,2s. A porta ficaria mais lenta offline do que online, que é o
# oposto do ponto. Depois da janela, a próxima leitura tenta o banco de
# novo e volta sozinha quando a rede voltar.
JANELA_SEM_BANCO = 30.0

_sem_banco_ate = 0.0


def init_pool():
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=Config.DATABASE_URL,
            cursor_factory=RealDictCursor,
            # Sem estes, "cair a internet" não vira erro rápido: o connect
            # espera o tempo do sistema operacional (dezenas de segundos no
            # Windows) e uma conexão já aberta pra um destino morto pode
            # demorar minutos pra desistir, porque o TCP fica retransmitindo.
            # O leitor da porta desiste em 20s e a pessoa fica olhando pra
            # uma tela parada. Com keepalive, o soquete morto é detectado em
            # poucos segundos e o plano B entra a tempo.
            connect_timeout=5,
            keepalives=1,
            keepalives_idle=5,
            keepalives_interval=2,
            keepalives_count=2,
        )


def marcar_sem_banco():
    """Chamada quando uma operação falha por rede/banco fora de alcance."""
    global _sem_banco_ate
    _sem_banco_ate = time.monotonic() + JANELA_SEM_BANCO


def sem_banco() -> bool:
    """True enquanto vale a pena nem tentar o Postgres."""
    return time.monotonic() < _sem_banco_ate


def marcar_com_banco():
    """Uma operação deu certo: volta a confiar no banco imediatamente."""
    global _sem_banco_ate
    _sem_banco_ate = 0.0


def get_conn():
    if _pool is None:
        init_pool()
    conn = _pool.getconn()
    register_vector(conn)  # permite passar/receber np.array direto como vector
    return conn


def put_conn(conn):
    if _pool is not None:
        _pool.putconn(conn)
