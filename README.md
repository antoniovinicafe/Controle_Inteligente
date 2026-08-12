# Fetin — Controle de Acesso Inteligente (app)

App Flutter do projeto Fetin (Inatel): controle de acesso com reconhecimento
facial, turmas, eventos e liberação de presença. Este repositório é só o
**app mobile** — o backend fica em [`inatel_access_api`](../../Users/anton/OneDrive/Desktop/Fetins/Controle/inatel_access_api) (pasta separada, não versionada junto).

## Stack

- Flutter 3.x / Dart, Material 3
- [`supabase_flutter`](https://pub.dev/packages/supabase_flutter) — login/sessão/JWT (o app nunca fala com senha diretamente com o backend)
- [`provider`](https://pub.dev/packages/provider) — estado de autenticação (`AuthProvider`)
- `camera` + `image_picker` — captura de foto pro cadastro facial
- `http` — chamadas REST pra API Flask

## Rodando localmente

1. `flutter pub get`
2. Preencha [`lib/config/app_config.dart`](lib/config/app_config.dart) com a URL/anon key do seu projeto Supabase e o endereço da API Flask:
   - Emulador Android: `http://10.0.2.2:5000/api` (não `localhost` — o emulador não enxerga a máquina host por esse nome)
   - Celular físico na mesma rede: IP da máquina, ex. `http://192.168.x.x:5000/api`
3. Suba a API Flask (veja o README dela) — sem ela no ar, login funciona (é direto com o Supabase) mas todo o resto trava.
4. `flutter run`

## Arquitetura (resumo)

Login e sessão são 100% Supabase Auth. A API Flask nunca vê senha — só valida
o JWT (assinado com **ES256**, via JWKS do projeto Supabase) e serve os dados
de negócio. Ver a pasta `lib/` abaixo pro detalhe de cada camada.

```
lib/
  config/     app_config.dart          → URL do Supabase + da API
  models/     perfil, turma, evento, participante, access_log
  services/   api_client.dart          → wrapper HTTP fino, injeta Bearer token
              auth_provider.dart       → ChangeNotifier: estado de sessão
              turmas_service, eventos_service, usuarios_service
  screens/    login → completar_cadastro → home (abas por papel) → turmas/eventos/rosto
  widgets/    lista_async.dart         → loading/erro/vazio/pull-to-refresh genérico
```

`AuthProvider` decide qual tela mostrar (`_AuthGate` em `main.dart`) reagindo
ao estado do Supabase automaticamente — não precisa navegar manualmente
entre login/cadastro/home.

## Papéis de usuário

`profiles.role` é `aluno`, `professor` ou `admin`. A `HomeScreen` monta as
abas de acordo (`Turmas` só aparece pra professor/admin). **Hoje o papel é
auto-selecionado pelo próprio usuário** na tela de completar cadastro — não
tem verificação/aprovação. É uma decisão consciente pra essa fase do
projeto (ver seção "Próximos passos" abaixo se isso mudar).

## Estado atual

**Pronto e testado:**
- Login/cadastro/sessão (Supabase Auth)
- Cadastro de rosto (auto-cadastro, 1 rosto por pessoa)
- Turmas: criar, listar, adicionar/remover aluno
- Eventos: criar (com seletor de data/hora), listar, detalhe (participantes +
  logs), convidar por aluno ou turma inteira, liberação manual de presença

**Não implementado ainda:**
- Reconhecimento facial em tempo real (a Raspberry Pi ainda não existe/integra)
- Atualização ao vivo da presença na tela do professor (hoje é pull-to-refresh manual — ver sugestão de usar Supabase Realtime)
- Edição de evento além de status/cancelamento
- Indicador de "aluno sem rosto cadastrado" na lista de participantes

## Gotchas de ambiente (Windows)

Ver `.claude/` deste projeto ou perguntar ao Claude — tem memória detalhada
de fixes de Python 3.12/TensorFlow, JDK 21 pro Gradle, NDK, OneDrive
travando build, etc. Resumo rápido:
- Java: use Eclipse Adoptium JDK 21 (`flutter config --jdk-dir`), não o JDK do Android Studio
- Projeto fora de pastas sincronizadas por OneDrive (causa lock de arquivo durante build)
- Caminho curto (`C:\Projetos\...`) pra evitar erro de path longo do Windows
