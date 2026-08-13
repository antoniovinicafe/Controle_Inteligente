# Fetin — API (backend Flask)

API do projeto Fetin (Inatel): controle de acesso com reconhecimento facial,
turmas, eventos e presença. O app Flutter e o código da Raspberry estão no
mesmo repositório, em [`../app/`](../app/) e em [`raspberry/`](raspberry/) —
o [README da raiz](../README.md) explica como as três partes se encaixam.

## Stack

- Flask 3 + `flask-cors`, servido por `waitress`
- Postgres (Supabase) via `psycopg2`, extensão `pgvector` pros embeddings faciais
- Supabase Auth pra login — **esta API nunca gera token nem lida com senha**,
  só valida o JWT que o Supabase emite
- DeepFace (modelo Facenet512, vetor de 512 posições) pro cálculo do embedding
  facial, com anti-spoofing (MiniFASNet, exige `torch`) na captura

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

Rode `schema.sql` no SQL Editor do Supabase antes do primeiro uso — ele já
vem com tudo. Os `migracao_*.sql` são só pra bancos criados antes de cada
mudança; num banco novo não precisa rodar nenhum.

## Estrutura

```
app.py                    → cria a app, registra blueprints, JSON provider (datas em ISO 8601)
config.py                 → lê .env
utils/db.py               → pool de conexões psycopg2
utils/auth_middleware.py  → valida JWT via JWKS, injeta g.user_id/g.user_role
utils/device_auth.py      → autentica a Raspberry por X-Device-Key (não é uma pessoa logada)
utils/curso.py            → deduz o curso do e-mail institucional (gec → Computação)
utils/json_provider.py    → serializa datetime em ISO 8601 (Flask usa formato HTTP por padrão - quebra clients Dart/JS)
routes/usuarios.py        → perfil, complete-cadastro, listar/promover usuários, frequência própria
routes/turmas.py          → CRUD turma + gestão de alunos + frequência da turma
routes/eventos.py         → CRUD evento + participantes + liberação manual + logs
routes/recorrencias.py    → "aula toda seg/qua", expandida em um evento por ocorrência
routes/dispositivos.py    → cadastro dos leitores de porta e rotação da chave
routes/faces.py           → cadastro/status/remoção de rosto + reconhecimento na porta
medir_rostos.py           → mede as distâncias entre rostos cadastrados (calibra o limiar de 0,30)
services/face_service.py  → DeepFace: embedding + anti-spoofing a partir de uma foto
services/cache_local.py   → cópia dos rostos/eventos/dispositivos pra decidir sem internet
services/fila_offline.py  → vereditos tomados offline, esperando subir pro Postgres
raspberry/                → o que roda na Pi da porta (totem, captura, descoberta do servidor)
tests/                    → pytest, sem banco: só a lógica que erra calado se quebrar
```

```bash
venv/Scripts/python -m pytest tests/ -q
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
| `POST/GET/DELETE /recorrencias` | professor/admin (dono ou admin) |
| `POST/GET/PATCH/DELETE /dispositivos`, rotação de chave | professor/admin |
| `POST/GET/DELETE /faces`, `DELETE /faces/<id>` | o próprio usuário, sobre o próprio rosto |
| `POST /faces/recognize` | a Raspberry, por `X-Device-Key` — **não** por JWT |

## Decisões que não são óbvias no código

- **`/faces/recognize` não usa JWT.** A Pi não é uma pessoa logada: autentica
  por chave própria no header `X-Device-Key`, e o banco guarda só o hash. É a
  chave que diz de qual sala o leitor é, e daí sai qual aula validar.
- **O app não usa Supabase Realtime.** A tela "Agora" relê `/eventos` de 10 em
  10 segundos. Realtime seria mais elegante, mas exigiria abrir a Data API
  pro cliente, e hoje o RLS nega tudo justamente pra obrigar todo acesso a
  passar por aqui.
- **Nada de índice `ivfflat` na tabela `faces`.** Já existiu um e fazia a porta
  recusar gente cadastrada — o porquê está comentado no `schema.sql`.
- **Vários rostos por pessoa** (até 5), **um rosto pertence a uma conta só**, e
  **da segunda foto em diante a captura tem que parecer com as que a conta já
  tem**. O motivo das três regras está no cabeçalho de
  `tests/test_multiplos_rostos.py`, `tests/test_rosto_duplicado.py` e
  `tests/test_rosto_estranho.py`.
- **São três limiares diferentes de distância, e confundi-los quebra coisas
  opostas.** 0,30 decide "é a mesma pessoa" na porta e no cadastro (o mesmo
  número nos dois, de propósito); 0,70 decide "essa foto é sua" ao acrescentar
  captura, e é frouxo porque duas fotos legítimas da mesma pessoa ficam longe
  uma da outra; e o limiar da vivacidade (0,75) não é distância nenhuma, é
  confiança do anti-spoofing.
- **Frequência é por disciplina, e o limite de faltas sai das aulas MARCADAS.**
  75% é por matéria — somar todas as turmas dá um número que não decide nada
  (80% no agregado esconde 50% numa delas). E `reprovado_por_falta` só é
  afirmado quando já cabia pelo menos uma falta: `previstas` são as aulas já
  criadas, não o tamanho do semestre, então sem essa condição quem perde a
  primeira aula do ano aparece reprovado. O porquê está em
  `tests/test_frequencia.py`.
- **A porta tem dois caminhos que precisam concordar.** `_decidir_no_banco`
  (SQL, em `routes/faces.py`) e `cache_local.decidir` (Python, sobre a cópia)
  fazem as mesmas três perguntas e devolvem o MESMO dicionário, com as mesmas
  mensagens — o totem mostra esse texto e ele não pode mudar conforme a
  internet. As duas são pra ser lidas lado a lado; mexeu numa, mexa na outra.
  O limiar de 0,30 mora em `services/face_service.py` justamente pra que as
  duas o importem do mesmo lugar em vez de cada uma ter o seu.
- **A manutenção pega carona na porta.** Subir a fila offline e renovar a
  cópia acontecem depois de uma leitura que já deu certo, não numa thread de
  fundo: se a porta está sendo usada, é o único momento em que isso importa,
  e é quando já se sabe que o banco responde.
- **A vivacidade não usa o veredito pronto do DeepFace.** `represent(anti_spoofing=True)`
  nega sempre que "real" não é a maior das três probabilidades do MiniFASNet —
  no voto de minerva — e joga fora o quanto ele estava certo disso. Como esse
  número é o que permite afrouxar sem desligar, `face_service.py` chama
  `extract_faces` (que devolve `is_real` + `antispoof_score`) e passa o recorte
  pronto pro `represent` com `detector_backend="skip"`: o detector continua
  rodando uma vez só. O limiar fica em `ANTISPOOF_LIMIAR` no `.env`.

## Gotchas de ambiente (Windows)

- Python 3.12 obrigatório (ver acima)
- `tf-keras` precisa estar instalado junto com TensorFlow
- `torch` também é obrigatório, não opcional: sem ele o anti-spoofing não
  carrega. A API responde 500 dizendo isso, de propósito — o DeepFace sinaliza
  a falta com uma mensagem que contém a palavra "spoof", e tratá-la como
  veredito faria a porta negar todo mundo com "isso parece uma foto".
- PowerShell: `Set-ExecutionPolicy RemoteSigned` se scripts não rodarem
- `python app.py` sobe o waitress, sem recarregar sozinho ao salvar arquivo —
  é preciso parar e subir de novo. Era com o servidor de debug do Flask, que
  travava com o TensorFlow carregado e derrubava a API sozinho no meio do uso.
  Pra voltar ao reload automático: `python app.py --dev`.
- A primeira requisição depois de subir demora: o DeepFace baixa/carrega os
  pesos do Facenet512 e do anti-spoofing na primeira chamada, não no import.
