# Handoff — Fetin (controle de acesso inteligente)

> Gerado porque a janela de contexto da sessão anterior encheu. Cole isso como
> primeira mensagem da nova conversa. Há também memória persistente do Claude
> Code em `C:\Users\anton\.claude\projects\C--Projetos-AppFlutter\memory\`
> (arquivo principal: `fetin-access-control-project.md`) — o assistente deve
> carregá-la automaticamente no início da sessão nova.

## 1. Objetivo do momento

Estava testando **ao vivo, tocando na tela do emulador**, a funcionalidade de
**evento recorrente** que acabei de implementar (backend + Flutter). Sequência
exata: naveguei Turmas → toquei na turma **"CSI"** (que já tem 1 aluno, de um
teste anterior) → tirei um screenshot (`screen_new8.png`) que **ainda não foi
analisado** — é o próximo passo. A partir daí, o plano era tocar no ícone
"Nova aula recorrente" (ícone `event_repeat` na AppBar da tela de detalhe da
turma) e preencher o formulário de criação.

## 2. O que foi concluído nesta sessão (cronológico)

### Diagnóstico e correção de bugs críticos de autenticação
- **Tela em branco**: já estava resolvida (credenciais do Supabase já preenchidas em `lib/config/app_config.dart`).
- **Bug real e grave**: o Flask validava JWT com HS256 + segredo compartilhado, mas o projeto Supabase (criado recentemente) assina com **ES256** (chave assimétrica via JWKS). Corrigido reescrevendo `utils/auth_middleware.py` no backend pra validar via `jwt.PyJWKClient` contra `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. Instalei `cryptography` no venv. Adicionei `SUPABASE_URL` no `.env`.
- **Impasse circular**: `POST /usuarios/complete-cadastro` exigia perfil já existente (`@login_required` normal), mas é essa rota que *cria* o perfil. Corrigido: `login_required` agora aceita `perfil_obrigatorio=False` (continua funcionando sem parênteses nas outras rotas).
- **UI travava sem feedback**: `AuthProvider._carregarPerfil()` só tratava `ApiException`; qualquer outro erro deixava a tela presa em "carregando" pra sempre. Adicionei catch geral + `login_screen.dart` agora reage a `AuthProvider.erro` via `context.watch`.

### Feature de cadastro facial
- `register_face_screen.dart` estava usando um `ApiService` antigo/morto, com contrato incompatível com o backend atual. Reescrevi pra usar `ApiClient` certo, **cadastro só do próprio usuário** (decisão consciente — ver seção 3). Deletei `api_service.dart` (código morto).
- `home_screen.dart` ganhou botão real "Cadastrar meu rosto".

### Feature completa de Turmas e Eventos (construída do zero)
- Models: `turma.dart`, `evento.dart`, `participante.dart`, `access_log.dart`, `recorrencia.dart`.
- Services: `turmas_service.dart`, `eventos_service.dart`, `usuarios_service.dart`, `recorrencias_service.dart`.
- Telas: `turmas_screen.dart`, `turma_detail_screen.dart`, `eventos_screen.dart`, `criar_evento_screen.dart`, `evento_detail_screen.dart`, `selecionar_usuarios_screen.dart`, `criar_recorrencia_screen.dart`.
- `home_screen.dart` com `NavigationBar` real (Eventos/Turmas-se-professor/Rosto).

### Bug real #2: formato de data quebrando o app inteiro
- Flask serializa `datetime` em formato HTTP por padrão (`Fri, 14 Aug 2026...`), não ISO 8601 — o `DateTime.parse()` do Dart só entende ISO. Toda tela de evento quebrava. Corrigido com `utils/json_provider.py` (`ISODateJSONProvider`), registrado em `app.py`.

### Bug real #3: FutureBuilder não reconstruía (o mais difícil de achar)
- Depois de certas sequências de navegação (ex: logout→login, criar→voltar), o `FutureBuilder` usado em `ListaAsync` **parava de reconstruir** mesmo com dados novos corretos chegando da API. Confirmado via prints de debug extensivos (rastreando `identityHashCode` do State por várias camadas) que o `build()` do `FutureBuilder` simplesmente nunca era chamado de novo. Causa raiz exata **não identificada** (suspeita: interação `IndexedStack` + `Provider` + `Navigator`), mas o padrão é 100% reproduzível.
- **Correção**: reescrevi `lib/widgets/lista_async.dart` de `StatelessWidget` (recebendo um `Future` já pronto) pra `StatefulWidget` que recebe `carregar: Future<List<T>> Function()` e gerencia seu próprio `_future` internamente. Telas externas forçam reload **trocando a `key`** (`ValueKey(_versao)` com contador incrementando) em vez de reatribuir o Future — isso força o Flutter a destruir/recriar o widget do zero, contornando o bug. Aplicado em **todas** as 5 telas que usavam o padrão antigo. Validado reproduzindo o bug 3x e confirmando o fix.
- **Regra pro futuro**: qualquer tela nova de lista deve usar `ListaAsync(key: ValueKey(_versao), carregar: ...)`, nunca `FutureBuilder(future: campoReatribuido)`.

### Exclusão de evento (feature nova)
- Antes só existia "cancelar" (soft, status='cancelado'). Adicionei exclusão de verdade: `DELETE /api/eventos/<id>` agora apaga a linha, mas recusa com 409 se já existir `access_logs` pra esse evento (preserva auditoria). "Cancelar" continua existindo via `PATCH .../status=cancelado`. UI: menu de 3 pontos (⋮) no AppBar do detalhe do evento, "Excluir evento" em vermelho, com dialog de confirmação explicando a regra. **Testado e validado** (sucesso + bloqueio 409, ambos via curl direto).

### Evento recorrente (feature em teste agora)
- Usuário respondeu **"sim e sim"** às duas perguntas de design: (1) aluno adicionado à turma depois É convidado retroativamente pras aulas futuras já geradas; (2) "cancelar a série" só afeta ocorrências futuras, passadas ficam intactas.
- Backend: tabela `recorrencias` (turma_id, titulo, descricao, local, `dias_semana smallint[]`, hora_inicio/fim, data_inicio/fim, capacidade, criador_id) + `eventos.recorrencia_id` FK — **já aplicado no banco ao vivo** e documentado em `schema.sql`. Nova rota `routes/recorrencias.py`: `POST` (expande dia-a-dia checando `isoweekday()` contra `dias_semana`, cria 1 evento por ocorrência + convida a turma inteira em cada), `GET`, `DELETE /<id>` (cancela só `data_inicio > now()`). Blueprint registrado em `app.py`. `routes/turmas.py`'s `adicionar_alunos` agora também convida o aluno novo pras aulas futuras de qualquer recorrência daquela turma (é o convite retroativo).
- Flutter: `criar_recorrencia_screen.dart` (chips de dias da semana, pickers de hora/data), acessível via ícone `event_repeat` no AppBar de `turma_detail_screen.dart`. `evento.dart` ganhou `recorrenciaId` (nullable). `evento_detail_screen.dart` mostra ícone de repetição + botão "Cancelar série" quando aplicável.
- **Validado via curl direto** (não via UI ainda): criação gerou exatamente as datas certas (testei seg+qua num range de 8 dias → 3 eventos nas datas certas), convite retroativo confirmado (`origem: turma`), cancelamento de série confirmado só afetando futuro (testei inserindo manualmente um evento "passado" com status `encerrado` e confirmei que não foi tocado). Dados de teste limpos depois.
- **Ainda NÃO testado tocando na tela de verdade** — é exatamente onde a sessão foi interrompida.

## 3. Decisões técnicas confirmadas com o usuário

- **Cadastro facial**: só o próprio usuário cadastra o próprio rosto (não professor cadastrando terceiros). Backend já era assim; Flutter foi ajustado pra bater.
- **Papel de professor**: continua **auto-selecionável no cadastro** (sem aprovação de admin) — decisão consciente pra fase de TCC/testes, não é bug de segurança a corrigir sem perguntar. A rota `PATCH /usuarios/<id>/role` (admin-only) já existe no backend caso queiram trocar isso depois.
- **Exclusão de evento**: só permitida sem `access_logs`; com log existente, força "cancelar" em vez de excluir.
- **Evento recorrente**: geração antecipada (eager) de um evento por ocorrência — não é regra "virtual"/lazy. Aluno novo pega aulas futuras automaticamente. Cancelar série preserva passado.
- **Arquitetura de presença via Raspberry Pi** (desenhada, não implementada): Pi precisa de autenticação própria por chave de API de dispositivo (não JWT de usuário) — middleware separado do `login_required`. Mapeamento dispositivo→sala via tabela `dispositivos` (não construída ainda). Recomendado usar **Supabase Realtime** pra atualização ao vivo da tela do professor em vez de WebSocket no Flask.
- **Ideia pendente, não implementada**: indicador "rosto não cadastrado" na lista de participantes do professor.

## 4. Estado atual e ambiente

- **Sem erros conhecidos.** Último `flutter analyze`: limpo (só infos de estilo pré-existentes). Backend: sintaxe Python ok, Flask rodando sem erro.
- **Emulador**: travou uma vez por ter ficado ligado a sessão inteira (relógio parou de avançar, parou de responder a toque). Usuário fechou e eu reabri (`Pixel_6` AVD) — está rodando fresco agora como `emulator-5554`. App reinstalado e rodando (`flutter run -d emulator-5554`).
- **Backend Flask: PARADO.** Um restart que tinha disparado lá atrás (durante a depuração do bug ES256) falhou e não deixou nenhum processo no ar — confirmado com `curl http://127.0.0.1:5000/api/health` (sem resposta) e checagem de processos (nenhum `python.exe` rodando `app.py`). **Primeiro passo prático da sessão nova**: subir o backend de novo antes de qualquer teste (`cd` até a pasta da API, `venv\Scripts\python.exe app.py`, esperar aparecer "Debugger is active!" no log). O emulador (`10.0.2.2:5000` de dentro dele) e a troca de wifi continuam não sendo problema, como confirmado antes — só falta o processo do Flask estar de pé.
- **Conta de teste**: `antonio.vinicius@gec.inatel.br` / senha `123456`, atualmente com `role='professor'` (promovido direto via SQL pra poder testar o lado professor — não existe UI pra isso ainda, ver decisão na seção 3).
- **Dados de teste no banco** (não são "reais", ok deixar ou limpar): turmas "CSI" (1 aluno = o próprio Antonio) e "Turma Teste IA" (0 alunos); vários eventos de teste (Palestra Teste, Pit, TesteFix, TesteDeep, TesteRelogin, Tenis — este último criado pelo próprio usuário testando sozinho).
- Um "erro" cosmético não-bloqueante já visto e explicado: na primeira tentativa de abrir o app numa rede nova, apareceu brevemente "Não foi possível conectar ao servidor" (cold-start race, sumiu sozinho ao relançar o app — não é bug, é o comportamento correto do catch-all que adicionamos).

## 5. Próximos passos exatos

1. **Retomar o teste visual da recorrência**: abrir/analisar `screen_new8.png` (detalhe da turma CSI, já capturado mas não visto), tocar no ícone "Nova aula recorrente" (event_repeat) na AppBar, preencher o formulário (título, dias da semana via chips, hora início/fim, período de/até) e submeter.
2. Verificar que os eventos gerados aparecem na aba Eventos, com o ícone de repetição no cabeçalho do detalhe de cada um.
3. Testar "Cancelar série" a partir do detalhe de um dos eventos gerados.
4. Limpar dados de teste da recorrência depois (mesmo padrão usado antes: apagar via SQL direto os eventos com aquele `recorrencia_id` e a própria recorrência).
5. Considerar (ainda não decidido/pedido explicitamente pra próxima sessão):
   - Indicador de "rosto não cadastrado" na lista de participantes.
   - Implementar Supabase Realtime pra presença ao vivo.
   - Tabela `dispositivos` + autenticação por chave de API pra Raspberry Pi + endpoint `POST /faces/recognize`.

## Caminhos importantes

- App Flutter: `C:\Projetos\AppFlutter`
- Backend Flask: `C:\Users\anton\OneDrive\Desktop\Fetins\Controle\inatel_access_api`
- Memória do Claude Code: `C:\Users\anton\.claude\projects\C--Projetos-AppFlutter\memory\` (ler `fetin-access-control-project.md` primeiro)
- Emulador: AVD `Pixel_6`, rodar via `emulator -avd Pixel_6 -no-snapshot-load`, depois `flutter run -d emulator-5554` dentro de `C:\Projetos\AppFlutter`
- Backend: `cd` até a pasta da API, `venv\Scripts\python.exe app.py` (Python 3.12 obrigatório)
