import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL = os.environ["DATABASE_URL"]
    # URL do projeto Supabase (ex: https://xxxxx.supabase.co) - usada pra
    # buscar a JWKS (chave pública) e validar os tokens ES256 emitidos
    # pelo Supabase Auth. Mesmo valor do AppConfig.supabaseUrl no Flutter.
    SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
    # Legado: projetos antigos assinavam com HS256 + segredo compartilhado.
    # Projetos novos usam chaves assimétricas (ES256) validadas via JWKS
    # (ver utils/auth_middleware.py) e não precisam mais disso, mas
    # mantemos como fallback opcional.
    SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")
    PORT = int(os.environ.get("PORT", 5000))
