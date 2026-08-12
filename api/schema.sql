-- ============================================================
-- Fetin - Schema do banco (Supabase / Postgres)
-- Rode isso no SQL Editor do Supabase (ou via psql conectado
-- na DATABASE_URL do projeto).
-- ============================================================

-- Extensão pra guardar o vetor facial (embedding) e permitir
-- busca por similaridade no futuro (ex: reconhecimento pela Raspberry)
create extension if not exists vector;

-- ------------------------------------------------------------
-- PROFILES
-- Supabase Auth já cria e gerencia a tabela auth.users
-- (email, senha, etc). Aqui guardamos os dados de negócio,
-- 1-pra-1 com auth.users.
-- ------------------------------------------------------------
create type user_role as enum ('admin', 'professor', 'aluno');

create table profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    nome        varchar(150) not null,
    matricula   varchar(30) unique,
    role        user_role not null default 'aluno',
    criado_em   timestamptz not null default now()
);

-- ------------------------------------------------------------
-- FACES
-- Um rosto cadastrado por usuário (1-pra-1 por enquanto;
-- se precisar de múltiplas fotos por pessoa no futuro, é só
-- tirar o UNIQUE e tratar "match" contra todas).
-- ------------------------------------------------------------
create table faces (
    id            bigint generated always as identity primary key,
    usuario_id    uuid not null unique references profiles(id) on delete cascade,
    embedding     vector(512) not null,   -- dimensão do modelo Facenet512 (DeepFace)
    modelo        varchar(50) not null default 'Facenet512',
    atualizado_em timestamptz not null default now()
);

-- ------------------------------------------------------------
-- TURMAS
-- Grupo reutilizável de alunos, criado por um professor.
-- ------------------------------------------------------------
create table turmas (
    id           bigint generated always as identity primary key,
    nome         varchar(150) not null,
    professor_id uuid not null references profiles(id),
    criado_em    timestamptz not null default now()
);

create table turma_alunos (
    turma_id  bigint not null references turmas(id) on delete cascade,
    aluno_id  uuid not null references profiles(id) on delete cascade,
    primary key (turma_id, aluno_id)
);

-- ------------------------------------------------------------
-- RECORRENCIAS
-- Regra de "aula toda X e Y, tal horário, entre tal e tal data" pra
-- uma turma. Ao criar, o backend expande em um evento de verdade por
-- ocorrência (ver routes/recorrencias.py) - cada evento gerado é
-- independente depois (cancelar/editar um não mexe nos outros).
-- ------------------------------------------------------------
create table recorrencias (
    id           bigint generated always as identity primary key,
    turma_id     bigint not null references turmas(id),
    titulo       varchar(150) not null,
    descricao    text,
    local        varchar(150),
    dias_semana  smallint[] not null,   -- ISO: 1=segunda .. 7=domingo
    hora_inicio  time not null,
    hora_fim     time not null,
    data_inicio  date not null,
    data_fim     date not null,
    capacidade   int,
    criador_id   uuid not null references profiles(id),
    criado_em    timestamptz not null default now(),
    check (data_fim >= data_inicio),
    check (hora_fim > hora_inicio)
);

-- ------------------------------------------------------------
-- EVENTOS
-- ------------------------------------------------------------
create type evento_status as enum ('agendado', 'em_andamento', 'encerrado', 'cancelado');

create table eventos (
    id           bigint generated always as identity primary key,
    titulo       varchar(150) not null,
    descricao    text,
    local        varchar(150),
    criador_id   uuid not null references profiles(id),
    data_inicio  timestamptz not null,
    data_fim     timestamptz not null,
    capacidade   int,                     -- null = sem limite
    status       evento_status not null default 'agendado',
    recorrencia_id bigint references recorrencias(id), -- null = evento avulso
    criado_em    timestamptz not null default now(),
    check (data_fim > data_inicio)
);

-- ------------------------------------------------------------
-- EVENTO_PARTICIPANTES
-- Lista final de quem pode acessar o evento (já "explodida":
-- se um professor convida uma turma inteira, geramos uma linha
-- por aluno aqui, guardando de onde veio o convite).
-- ------------------------------------------------------------
create type participante_status as enum ('convidado', 'liberado', 'negado');
create type origem_convite as enum ('turma', 'manual');

create table evento_participantes (
    id           bigint generated always as identity primary key,
    evento_id    bigint not null references eventos(id) on delete cascade,
    usuario_id   uuid not null references profiles(id) on delete cascade,
    status       participante_status not null default 'convidado',
    origem       origem_convite not null default 'manual',
    turma_id     bigint references turmas(id),   -- preenchido se origem = 'turma'
    liberado_em  timestamptz,
    unique (evento_id, usuario_id)
);

-- ------------------------------------------------------------
-- ACCESS_LOGS
-- Todo evento de liberação/negação de acesso, seja por
-- reconhecimento facial (futuro, via Raspberry) ou manual
-- (professor liberando pelo app).
-- ------------------------------------------------------------
create type log_tipo as enum ('facial', 'manual');
create type log_status as enum ('liberado', 'negado');

create table access_logs (
    id           bigint generated always as identity primary key,
    evento_id    bigint references eventos(id),
    usuario_id   uuid references profiles(id),   -- null se rosto não reconhecido
    tipo         log_tipo not null,
    status       log_status not null,
    dispositivo  varchar(100),                   -- nome do leitor, ex: 'raspberry-sala-201'
    motivo       text,                           -- por que liberou/negou ('Rosto não reconhecido', etc)
    criado_em    timestamptz not null default now()
);

-- ------------------------------------------------------------
-- Índices úteis
-- ------------------------------------------------------------
create index idx_evento_participantes_evento on evento_participantes(evento_id);
create index idx_evento_participantes_usuario on evento_participantes(usuario_id);
create index idx_turma_alunos_turma on turma_alunos(turma_id);
create index idx_access_logs_evento on access_logs(evento_id);
create index idx_eventos_criador on eventos(criador_id);
create index idx_eventos_recorrencia on eventos(recorrencia_id);
create index idx_recorrencias_turma on recorrencias(turma_id);

-- NÃO crie índice ivfflat aqui. Já existiu um:
--
--   create index idx_faces_embedding on faces using ivfflat (embedding vector_cosine_ops);
--
-- e ele fazia a porta recusar gente cadastrada. O ivfflat é busca
-- APROXIMADA: agrupa os vetores em listas e sonda só uma (ivfflat.probes
-- = 1 por padrão). Criado aqui, com a tabela `faces` ainda vazia, os
-- centroides das listas nascem sem dado nenhum pra aprender - e a
-- consulta passa a devolver ZERO linhas em vez do vizinho mais próximo.
-- O sintoma é traiçoeiro: não é lentidão nem distância alta, é o
-- reconhecimento respondendo "rosto não cadastrado" de forma aleatória,
-- e funcionando de vez em quando por sorte.
--
-- Para o tamanho deste projeto (algumas centenas de rostos), a varredura
-- exata resolve em milissegundos e acerta sempre - e num controle de
-- acesso, acertar sempre vale mais que ser rápido. Se um dia forem
-- dezenas de milhares de rostos, prefira HNSW (não precisa de dados
-- prévios pra treinar) e meça o recall antes de confiar.

-- ------------------------------------------------------------
-- DISPOSITIVOS (leitores faciais nas portas das salas)
-- A Raspberry Pi não é um usuário: autentica por chave própria
-- (header X-Device-Key), não por JWT. No banco só fica o hash.
-- ------------------------------------------------------------
-- `eventos.local` é texto livre, então "Sala 201" e "sala  201"
-- precisam casar quando o leitor procura a aula da sala dele.
-- Usa `translate` em vez de `unaccent` de propósito: no Supabase a
-- extensão vive no schema `extensions` e não é enxergada de dentro de
-- uma função SQL inlined.
-- Tira todos os espaços, caixa e acentos: "Sala 201", "sala201" e
-- "SALA  201" viram a mesma chave de comparação.
create or replace function normaliza_local(txt text) returns text as $$
  select regexp_replace(
           translate(lower(coalesce(txt, '')),
                     'áàâãäéèêëíìîïóòôõöúùûüç',
                     'aaaaaeeeeiiiiooooouuuuc'),
           '\s', '', 'g')
$$ language sql immutable;

create table dispositivos (
    id           bigint generated always as identity primary key,
    nome         varchar(100) not null,
    local        varchar(150) not null,
    chave_hash   varchar(64) not null unique,
    ativo        boolean not null default true,
    ultimo_visto timestamptz,
    criado_por   uuid not null references profiles(id),
    criado_em    timestamptz not null default now()
);

create index idx_dispositivos_chave on dispositivos(chave_hash);
create index idx_eventos_local_norm on eventos (normaliza_local(local));
