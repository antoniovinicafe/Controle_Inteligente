# Fetin — Controle de Acesso Inteligente

Projeto desenvolvido para a FETIN, no Inatel. O sistema registra presença em
aula por reconhecimento facial: a pessoa chega na porta, a câmera reconhece,
e a entrada é gravada sozinha — sem lista de chamada, sem crachá.

São três partes que conversam entre si, e este repositório tem as três.

```
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│  Raspberry  │  foto  │    Flask    │  SQL   │  Supabase   │
│   na porta  │ ─────► │   (no PC)   │ ─────► │  Postgres   │
│   + câmera  │ ◄───── │   DeepFace  │ ◄───── │  + pgvector │
└─────────────┘ libera └─────────────┘        └─────────────┘
                              ▲
                              │ HTTP + JWT
                       ┌─────────────┐
                       │   Flutter   │
                       │  (celular)  │
                       └─────────────┘
```

## As três partes

| Pasta | O que é |
|---|---|
| [`app/`](app/) | Aplicativo Flutter. Professor cria turmas e aulas e acompanha quem entrou; aluno vê suas aulas e sua presença. |
| [`api/`](api/) | Servidor Flask. Valida o token, calcula o vetor do rosto e decide se libera. É onde mora toda a regra de negócio. |
| [`api/raspberry/`](api/raspberry/) | Código que roda na Raspberry Pi da porta: captura da câmera e a tela do totem (LIBERADO / NEGADO). |

## Como a decisão de liberar é tomada

Quando um rosto chega, o Flask checa quatro coisas em ordem. Basta uma
falhar para negar:

1. **Rosto** — a foto tem um rosto reconhecível?
2. **Identidade** — o vetor bate com alguém cadastrado? (distância de
   cosseno abaixo de 0,30)
3. **Aula** — existe uma aula acontecendo agora naquele lugar?
4. **Lista** — essa pessoa foi convidada para essa aula?

O reconhecimento usa **Facenet512**: a foto vira um vetor de 512 números e
a comparação é uma distância entre vetores, não uma comparação de imagens.
A imagem em si nunca é gravada — nem no servidor, nem no leitor da porta.

## Rodando

**API** (precisa de Python 3.12 e de um `.env` — copie de `api/.env.example`):

```bash
cd api && python -m venv venv && venv/Scripts/pip install -r requirements.txt && venv/Scripts/python app.py
```

**App** (precisa do Flutter):

```bash
cd app && flutter pub get && flutter run
```

O endereço do servidor é editável dentro do app, em **Ajustes → Servidor** —
não precisa recompilar quando o IP da máquina muda.

## Segurança

- `app/lib/config/app_config.dart` contém a chave **publishable** do Supabase.
  Ela pode ficar em repositório público **porque as tabelas têm Row Level
  Security ligado sem nenhuma policy** — ou seja, a Data API nega tudo, e
  todo acesso passa obrigatoriamente pelo Flask.
- `api/.env` **nunca** entra no repositório. Tem a senha do Postgres e o
  segredo de JWT, que dão acesso direto ao banco por fora do Flask.
- Login exige internet: a autenticação é no Supabase (nuvem). O
  reconhecimento e a presença funcionam na rede local, mas entrar no app não.

## Estado

App e API funcionando ponta a ponta, validados com duas pessoas distintas.
O que falta está anotado em [`app/HANDOFF.md`](app/HANDOFF.md).
