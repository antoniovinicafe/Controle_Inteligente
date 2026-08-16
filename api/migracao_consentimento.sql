-- Registro de consentimento pro tratamento do dado biométrico.
--
-- POR QUÊ
-- Vetor facial é dado pessoal SENSÍVEL pela LGPD (art. 5º, II), e tratar
-- dado sensível exige consentimento específico e destacado - não serve o
-- consentimento genérico de usar o app, nem "a pessoa apertou o botão de
-- cadastrar rosto". Sem registro de quem consentiu, quando e com qual
-- texto, não há como demonstrar que houve consentimento; e a LGPD põe o
-- ônus dessa prova em quem trata o dado, não em quem forneceu.
--
-- POR QUE UMA TABELA, E NÃO DUAS COLUNAS EM profiles
-- O registro precisa sobreviver à revogação. Se a pessoa revoga, o rosto
-- some do banco (é o direito dela), mas a prova de que o tratamento
-- anterior era legítimo tem que continuar existindo - senão revogar apaga
-- também a defesa de quem tratou corretamente. Por isso cada evento é uma
-- linha: aceitar cria uma, revogar carimba a data na mesma.
--
-- A VERSÃO importa: se o texto do consentimento mudar, quem aceitou o
-- anterior não consentiu com o novo. O código compara a versão registrada
-- com a atual e pede de novo quando diferem.
--
-- Rodar só em bancos criados antes de 16/08/2026. Em banco novo, o
-- schema.sql já vem com isto.

create table if not exists consentimentos (
    id           bigint generated always as identity primary key,
    usuario_id   uuid not null references profiles(id) on delete cascade,
    versao       varchar(20) not null,      -- qual texto a pessoa leu
    aceito_em    timestamptz not null default now(),
    revogado_em  timestamptz                -- null = ainda vale
);

create index if not exists idx_consentimentos_usuario on consentimentos (usuario_id);

-- Quem já tinha rosto cadastrado antes desta migração consentiu de fato
-- (foi até a tela, tirou a foto), mas com um texto que não existia. Fica
-- registrado como versão "0-implicito" pra que a diferença apareça: o
-- código vai pedir o consentimento novo na próxima vez que a pessoa
-- cadastrar um rosto, em vez de fingir que ela já leu algo que não leu.
insert into consentimentos (usuario_id, versao, aceito_em)
select distinct f.usuario_id, '0-implicito', min(f.atualizado_em)
from faces f
group by f.usuario_id
on conflict do nothing;
