-- Permite mais de uma foto cadastrada por pessoa.
--
-- POR QUÊ
-- Um vetor por pessoa significa uma única condição de luz, ângulo e óculos.
-- Quem cadastrou num corredor claro e chega na quadra (luz de LED verde, que
-- já se mostrou problemática) tem menos margem pra ser reconhecido. Guardar
-- 3-4 capturas cobre a variação real e reduz a rejeição de quem tem direito.
--
-- De quebra, é o que torna possível MEDIR o sistema: sem duas fotos da mesma
-- pessoa não existe "distância intra-pessoa", e sem ela não dá pra dizer onde
-- fica a fronteira entre reconhecer e recusar.
--
-- O QUE MUDA NA BUSCA: nada. A consulta de reconhecimento já é
--   order by embedding <=> %s limit 1
-- ou seja, pega o vetor mais próximo da tabela inteira. Com várias linhas por
-- pessoa ela passa a comparar contra a melhor captura daquela pessoa sem
-- precisar de uma linha de código a mais.
--
-- Rodar uma vez:
--   psql "$DATABASE_URL" -f migracao_multiplos_rostos.sql

alter table faces drop constraint if exists faces_usuario_id_key;

-- O índice continua útil pra buscar/contar as fotos de uma pessoa.
create index if not exists idx_faces_usuario on faces (usuario_id);

-- Para reverter (só funciona se cada pessoa tiver no máximo uma linha):
--   delete from faces a using faces b
--    where a.usuario_id = b.usuario_id and a.id < b.id;
--   alter table faces add constraint faces_usuario_id_key unique (usuario_id);
