"""
Valida o token JWT emitido pelo Supabase Auth (o Flask NUNCA gera
token nem lida com senha - isso é 100% responsabilidade do Supabase).

O Flutter faz login via `supabase_flutter`, pega o `access_token` da
sessão e manda em todo request pra API assim:

    Authorization: Bearer <access_token>

Projetos Supabase criados recentemente assinam o token com uma chave
assimétrica (ES256), não mais com o segredo compartilhado HS256 antigo.
Por isso validamos contra a JWKS (chave pública) do projeto, buscada em
`{SUPABASE_URL}/auth/v1/.well-known/jwks.json` - o PyJWKClient já cuida
de cache e de buscar a chave certa pelo `kid` do header do token.
Depois disso, busca o perfil (nome, role) na tabela `profiles`.
"""

from functools import wraps
import jwt
from flask import request, jsonify, g

from config import Config
from utils.db import get_conn, put_conn

# PyJWKClient cacheia as chaves em memória (tem cache_keys=True por
# padrão) - só busca no Supabase de novo se aparecer um `kid` novo.
_jwks_client = jwt.PyJWKClient(
    f"{Config.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
)


def _extract_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1]


def login_required(perfil_obrigatorio=True):
    """
    Exige um token Supabase válido. Popula g.user_id e g.user_role.

    perfil_obrigatorio=False libera rotas que rodam ANTES do perfil existir
    (ex: /usuarios/complete-cadastro, que é justamente quem cria o perfil -
    exigir perfil ali criava um impasse: pra criar o perfil você precisaria
    já ter um). Nesses casos g.user_id vem do token e g.user_role fica None.

    Aceita ser usado com ou sem parênteses:
        @login_required
        @login_required(perfil_obrigatorio=False)
    """
    # Uso sem parênteses: o "perfil_obrigatorio" recebido é a própria função.
    if callable(perfil_obrigatorio):
        return _login_required_impl(perfil_obrigatorio, True)

    def decorator(f):
        return _login_required_impl(f, perfil_obrigatorio)

    return decorator


def _login_required_impl(f, perfil_obrigatorio):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"erro": "Token não informado"}), 401

        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                # Sem leeway o token recém-emitido é recusado de vez em
                # quando com ImmatureSignatureError ("not yet valid"): o
                # `iat` vem do relógio do Supabase e basta ele estar uma
                # fração de segundo à frente do nosso pra cair na checagem.
                # Aparecia como "Token inválido" logo depois do login, que
                # sumia se a pessoa tentasse de novo. 30s cobre isso e a
                # deriva normal de relógio sem afrouxar o `exp` de forma
                # relevante (o token vale 1h).
                leeway=30,
            )
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"erro": "Token inválido"}), 401

        user_id = payload.get("sub")
        if not user_id:
            return jsonify({"erro": "Token inválido"}), 401

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "select id, nome, matricula, role from profiles where id = %s",
                    (user_id,),
                )
                profile = cur.fetchone()
        finally:
            put_conn(conn)

        if not profile:
            if perfil_obrigatorio:
                return jsonify({"erro": "Perfil não encontrado. Cadastro incompleto."}), 404
            # Ainda não tem perfil, mas a rota permite - segue com os dados do token.
            g.user_id = str(user_id)
            g.user_role = None
            g.user_nome = None
            g.user_matricula = None
            return f(*args, **kwargs)

        g.user_id = str(profile["id"])
        g.user_role = profile["role"]
        g.user_nome = profile["nome"]
        g.user_matricula = profile["matricula"]

        return f(*args, **kwargs)

    return wrapper


def require_role(*roles):
    """Use depois de @login_required. Ex: @require_role('professor', 'admin')"""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if g.get("user_role") not in roles:
                return jsonify({"erro": "Você não tem permissão para isso"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator
