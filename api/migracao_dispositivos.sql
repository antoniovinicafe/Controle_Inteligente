-- ============================================================
-- Rode isto no SQL Editor do Supabase, de uma vez só.
-- Cobre duas coisas: o buraco de segurança do RLS (pendente) e
-- o que o reconhecimento facial precisa pra funcionar.
-- ============================================================

-- ------------------------------------------------------------
-- 1) RLS - fecha o acesso direto pela anon key
--
-- Hoje qualquer um com a chave que sai do APK lê e escreve o banco
-- inteiro, passando por cima do Flask. Não precisa criar policy
-- nenhuma: sem policy, o anon não enxerga nada. O Flask continua
-- funcionando porque conecta como `postgres`, que tem bypassrls.
-- ------------------------------------------------------------
alter table profiles             enable row level security;
alter table eventos              enable row level security;
alter table turmas               enable row level security;
alter table turma_alunos         enable row level security;
alter table evento_participantes enable row level security;
alter table faces                enable row level security;
alter table access_logs          enable row level security;
alter table recorrencias         enable row level security;

-- ------------------------------------------------------------
-- 2) Motivo no log de acesso
--
-- `status` só diz liberado/negado. Sem o motivo, um log de negação
-- não conta por que negou - e é justamente isso que interessa
-- ("não reconhecido" é muito diferente de "não está na lista").
-- ------------------------------------------------------------
alter table access_logs add column if not exists motivo text;

-- ------------------------------------------------------------
-- 3) Normalização de sala
--
-- `eventos.local` é texto digitado à mão, então "Sala 201",
-- "sala 201" e "SALA  201" precisam ser a mesma coisa na hora de
-- o leitor procurar a aula da sala dele.
-- ------------------------------------------------------------
-- Sem `unaccent`: no Supabase as extensões ficam no schema `extensions`,
-- que não está no search_path de dentro da função (dá "function
-- unaccent(text) does not exist" na hora do inlining). `translate` faz o
-- mesmo pro punhado de acentos que aparece em nome de sala, e não
-- depende de extensão nenhuma.
-- Tira TODOS os espaços (não só colapsa): assim "Sala 201", "sala201" e
-- "SALA  201" viram a mesma coisa. O local é digitado à mão em dois
-- lugares diferentes (no evento e no cadastro do leitor), então quanto
-- mais tolerante, menos "não achou aula nenhuma" por bobagem.
create or replace function normaliza_local(txt text) returns text as $$
  select regexp_replace(
           translate(lower(coalesce(txt, '')),
                     'áàâãäéèêëíìîïóòôõöúùûüç',
                     'aaaaaeeeeiiiiooooouuuuc'),
           '\s', '', 'g')
$$ language sql immutable;

-- ------------------------------------------------------------
-- 4) Dispositivos (os leitores faciais nas portas)
--
-- A chave nunca é guardada em texto: só o SHA-256 dela.
-- ------------------------------------------------------------
create table if not exists dispositivos (
    id           bigint generated always as identity primary key,
    nome         varchar(100) not null,
    local        varchar(150) not null,
    chave_hash   varchar(64) not null unique,
    ativo        boolean not null default true,
    ultimo_visto timestamptz,
    criado_por   uuid not null references profiles(id),
    criado_em    timestamptz not null default now()
);

alter table dispositivos enable row level security;

create index if not exists idx_dispositivos_chave on dispositivos(chave_hash);

-- Acelera a busca "tem aula nesta sala agora?"
create index if not exists idx_eventos_local_norm
    on eventos (normaliza_local(local));

-- ------------------------------------------------------------
-- Conferência: rode depois e veja se está tudo como esperado.
-- ------------------------------------------------------------
-- select relname, relrowsecurity from pg_class
--  where relname in ('profiles','eventos','turmas','turma_alunos',
--                    'evento_participantes','faces','access_logs',
--                    'recorrencias','dispositivos')
--  order by relname;
