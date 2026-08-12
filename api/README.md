# Fetin — API (backend Flask)

API do projeto Fetin (Inatel): controle de acesso com reconhecimento facial,
turmas, eventos e presença. O app mobile fica em outro repositório
(`AppFlutter`, `C:\Projetos\AppFlutter`).

## Stack

- Flask 3 + `flask-cors`
- Postgres (Supabase) via `psycopg2`, extensão `pgvector` pros embeddings faciais
- Supabase Auth pra login — **esta API nunca gera token nem lida com senha**,
  só valida o JWT que o Supabase emite
- DeepFace (modelo Facenet512, vetor de 512 posições) pro cálculo do embedding facial

## Autenticação

Projetos Supabase recentes assinam o JWT com **ES256** (chave assimétrica),
não mais com um segredo HS256 compartilhado. `utils/auth_middleware.py`
valida contra a JWKS pública do projeto (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`),
usando `jwt.PyJWKClient` (precisa do pacote `cryptography` instalado, além do PyJWT).

`SUPABASE_JWT_SECRET` no `.env` é só fallback legado — pode deixar em branco
em projetos novos.

## Rodando localmente

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # preencha DATABASE_URL, SUPABASE_URL
python app.py
```

**Importante**: use **Python 3.12** especificamente (`py -3.12 -m venv venv`).
Python 3.14 não tem wheels compatíveis com TensorFlow/DeepFace ainda.

`DATABASE_URL` deve apontar pro **pooler** do Supabase
(`aws-0-xxxx.pooler.supabase.com`), não pra conexão direta — a direta falha
por IPv6 dependendo da rede.

Rode `schema.sql` no SQL Editor do Supabase antes do primeiro uso.

## Estrutura

```
app.py                   → cria a app, registra blueprints, JSON provider (datas em ISO 8601)
config.py                → lê .env
utils/db.py               → pool de conexões psycopg2
utils/auth_middleware.py  → valida JWT via JWKS, injeta g.user_id/g.user_role
utils/json_provider.py    → serializa datetime em ISO 8601 (Flask usa formato HTTP por padrão - quebra clients Dart/JS)
routes/usuarios.py        → perfil, complete-cadastro, listar/promover usuários
routes/turmas.py          → CRUD turma + gestão de alunos
routes/eventos.py         → CRUD evento + participantes + liberação manual + logs
routes/faces.py           → cadastro/status/remoção de rosto (reconhecimento ainda não implementado)
services/face_service.py  → DeepFace: calcula o embedding a partir de uma foto
```

## Rotas — visão geral

Todas sob `/api`. `@login_required` exige JWT válido + perfil existente em
`profiles` (usa `@login_required(perfil_obrigatorio=False)` só em
`complete-cadastro`, que é quem cria o perfil). `@require_role(...)` restringe
por papel.

| Rota | Quem pode |
|---|---|
| `GET /usuarios/me` | qualquer autenticado |
| `POST /usuarios/complete-cadastro` | autenticado sem perfil ainda |
| `GET /usuarios`, `PATCH /usuarios/<id>/role` | professor/admin (listar), admin (promover) |
| `POST/GET /turmas`, gestão de alunos | professor/admin |
| `POST/GET/PATCH/DELETE /eventos`, participantes, liberar manual, logs | professor/admin (dono ou admin) |
| `POST/GET/DELETE /faces` | o próprio usuário, sobre o próprio rosto |

## Não implementado ainda

- `POST /faces/recognize` — endpoint que a Raspberry Pi vai chamar. Precisa de
  autenticação própria (chave de API por dispositivo, **não** um JWT de
  usuário — a Pi não é uma pessoa logada) e de um jeito de saber qual evento
  validar (proposta: tabela `dispositivos` mapeando device → sala/local).
- Atualização em tempo real pro app: recomendado usar **Supabase Realtime**
  (o Flutter assina mudanças em `evento_participantes` direto do Postgres)
  em vez de abrir WebSocket no Flask.

## Gotchas de ambiente (Windows)

- Python 3.12 obrigatório (ver acima)
- `tf-keras` precisa estar instalado junto com TensorFlow
- PowerShell: `Set-ExecutionPolicy RemoteSigned` se scripts não rodarem
- O servidor de debug do Flask demora alguns segundos pra reiniciar depois de
  qualquer edição, porque `routes/faces.py` importa DeepFace/TensorFlow no
  nível do módulo — espere o log mostrar "Debugger is active!" antes de
  testar de novo.
