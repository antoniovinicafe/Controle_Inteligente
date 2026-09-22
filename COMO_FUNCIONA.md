# Como o Fetin funciona, camada por camada

Este documento é pra **explicar o projeto**: o caminho completo de uma
leitura, da câmera da porta até a linha gravada no banco, e o que cada peça
resolve.

O [README](README.md) tem as decisões e o histórico (por que cada limiar é o
que é, o que já falhou). Aqui é o funcionamento.

---

## O mapa em uma frase

**Uma câmera na porta manda uma foto pra um servidor, o servidor transforma
o rosto em números, compara com o cadastro, checa se tem aula ali agora e se
a pessoa foi convidada — e devolve LIBERADO ou NEGADO. O aplicativo é onde o
professor monta as aulas e vê quem entrou.**

```
┌──────────────┐   foto (JPEG)     ┌──────────────┐    SQL      ┌──────────────┐
│  Raspberry   │ ────────────────► │    Flask     │ ──────────► │   Supabase   │
│   na porta   │                   │   (no PC)    │             │   Postgres   │
│  + câmera    │ ◄──────────────── │   DeepFace   │ ◄────────── │  + pgvector  │
└──────────────┘  LIBERADO/NEGADO  └──────────────┘             └──────────────┘
       └────────── rede local ──────────┘        └──── internet (AWS SP) ────┘
                                    ▲
                                    │ HTTPS + JWT
                             ┌──────────────┐
                             │   Flutter    │
                             │  (celular)   │
                             └──────────────┘
```

A divisão importa: **a Raspberry e o servidor estão no prédio; o banco não.**
É essa fronteira que criou o modo offline.

---

## Camada 1 — A Raspberry Pi: a porta

**O que é:** uma Raspberry Pi com câmera CSI (módulo imx219) e um monitor
pequeno, rodando `api/raspberry/totem.py` em tela cheia.

**O que ela NÃO faz, e é o ponto principal:** nada de reconhecimento. Não tem
TensorFlow, não tem DeepFace, não tem nenhum rosto guardado, não tem senha de
banco. Ela não decide nada, e isso é decisão de projeto.

> **Como explicar:** "A Pi só tira foto e pergunta 'pode entrar?'. Toda a
> inteligência está no servidor. Isso não é preguiça — é o que permite trocar
> o modelo de reconhecimento sem tocar em hardware nenhum, e é o que faz não
> ser um problema se alguém levar a Pi embora: não tem nada dentro dela."

### O laço de execução

1. **Desenha o preview da câmera** na tela, em duotone (rampa petróleo→menta).
2. **Detecta movimento** — diferença entre quadros consecutivos, em numpy.
   Só quando algo se move ela decide perguntar ao servidor.
3. **Manda a foto** por `POST /api/faces/recognize`, numa thread separada.
4. **Mostra o veredito**: LIBERADO em cor real, NEGADO com o motivo em texto.

Três detalhes que explicam o código:

- **Só pergunta quando alguém se mexe.** Um totem que enviasse foto sem parar
  transformaria uma sala vazia num NEGADO piscando pra sempre e encheria a
  tabela de logs com "nenhum rosto detectado".
- **A rede roda em thread separada.** O POST leva de 0,2 a 1 segundo; se
  fosse no laço de desenho, a imagem congelaria a cada tentativa.
- **O preview vira cor real quando libera.** Além de ser o momento visual, a
  luz de LED da quadra tinge tudo de verde, e a rampa duotone normaliza isso.

### Como ela acha o servidor

Não tem IP fixo. `descobrir_api.py` tenta, em ordem: o `--api` da linha de
comando, a variável `FETIN_API`, o arquivo `~/.fetin/api`, e por último **uma
varredura da rede local** procurando quem responde `/api/health` (254
endereços em ~2,6s). O que funcionar é gravado em `~/.fetin/api`.

> **Como explicar:** "O IP do PC muda sozinho, por DHCP — num único dia de
> trabalho mudou cinco vezes. Antes o endereço estava fixo no serviço do
> systemd, e consertar exigia achar a Pi na rede, dar SSH e editar o
> arquivo. Hoje ela se acha sozinha."

### Como ela se identifica

Header `X-Device-Key`. Um leitor não é uma pessoa: não faz login, não tem
senha pra digitar e não pode depender de um JWT que expira em 1 hora.

A chave aparece em texto **uma única vez**, quando o dispositivo é
cadastrado. No banco fica só o **SHA-256** dela.

> **Como explicar:** "E é a chave que diz de qual sala aquele leitor é. Ele
> não informa a sala na requisição — se informasse, qualquer um poderia
> mentir e liberar acesso na sala errada. O servidor procura a chave, e a
> linha do banco diz `local = FETIN`."

O hash é SHA-256 puro, sem salt, de propósito: a chave é aleatória de 256
bits (não é senha escolhida por humano), então não há dicionário nem rainbow
table pra quebrar — e o hash precisa ser determinístico pra dar pra procurar
por ele numa consulta.

**Sobe sozinho no boot** como serviço de usuário do systemd
(`totem.service`), com `Restart=always`.

---

## Camada 2 — O Flask: onde tudo é decidido

Roda no PC, servido por `waitress`. É o único lugar que fala com o banco.

### O caminho de uma leitura, na ordem exata

`POST /api/faces/recognize` (`api/routes/faces.py`)

**Passo 0 — Autenticar o leitor** (`utils/device_auth.py`)
Procura o hash da `X-Device-Key`. Se achar, popula `g.dispositivo_local`
(= `FETIN`) e atualiza `ultimo_visto`, que serve de heartbeat. Chave
inválida = 401.

**Passo 1 — Vivacidade + embedding** (`services/face_service.py`)
Aqui a foto encontra os dois modelos, e é uma chamada só:

```
extract_faces(anti_spoofing=True)  →  recorte do rosto + is_real + antispoof_score
represent(detector_backend="skip") →  vetor de 512 números (Facenet512)
```

O detector roda **uma vez**: o recorte que o anti-spoofing produziu é passado
pronto pro `represent`.

> **Como explicar por que não usamos o veredito pronto do DeepFace:** "O
> `represent(anti_spoofing=True)` nega sempre que 'real' não é a maior das
> três probabilidades do MiniFASNet — decide no voto de minerva e joga fora o
> quanto ele estava certo. Esse número é exatamente o que permite afrouxar
> sem desligar, então a gente pega as duas coisas separadas e decide aqui."

A recusa só vale quando o modelo está convicto: **`ANTISPOOF_LIMIAR = 0.60`**.
E existe uma segunda regra: uma leitura acima de **97%** de suspeita vale
pelos **6 segundos** seguintes, pra que uma foto que oscila entre "fraude" e
"pessoa" não entre na leitura favorável.

Se falhar aqui, o resto nem roda — a etapa é `vivacidade`.

**Passo 2 — Identidade** (`_decidir_no_banco`)

```sql
select f.usuario_id, p.nome, (f.embedding <=> %s::vector) as distancia
from faces f join profiles p on p.id = f.usuario_id
order by f.embedding <=> %s::vector
limit 1
```

`<=>` é distância de cosseno do pgvector. Busca **exata** (varredura da
tabela) de propósito. Se a distância for maior que **0,30**, é "Rosto não
reconhecido".

> **Como explicar:** "Não se comparam imagens, se comparam vetores. E repare
> que a busca pega a captura mais próxima entre TODAS — cada pessoa tem até
> 5, e é sempre uma delas que responde. É isso que faz o limiar de 0,30
> funcionar, porque duas fotos legítimas da mesma pessoa podem ficar longe
> uma da outra."

**Passo 3 — Tem aula agora aqui?**

```sql
where normaliza_local(local) = normaliza_local(%s)
  and status in ('agendado','em_andamento')
  and now() between data_inicio and data_fim
order by data_inicio limit 1
```

`normaliza_local` é uma função no Postgres que tira acento, caixa e espaços
dos dois lados — "Sala 201" e "sala201" batem. Existe índice sobre ela.

**Passo 4 — Foi convidado?**
Uma linha em `evento_participantes` com aquele evento e aquela pessoa. Se
não tiver: "Não está na lista".

> **Este é o passo que mais impressiona.** A pessoa foi reconhecida pelo nome
> e ainda assim é negada. Reconhecer não é autorizar.

**Passo 5 — Gravar** (`_gravar`)
Todo veredito vira uma linha em `access_logs`, com motivo — **inclusive as
recusas**. Tentativa negada é exatamente o que um controle de acesso precisa
registrar. Se liberou, também marca `evento_participantes.liberado_em`.

**A imagem é descartada.** Nunca é gravada, nem no servidor nem na Pi.

### O modo offline

O banco fica na AWS em São Paulo. Se a internet cai, as quatro perguntas
continuam as mesmas — quem responde muda.

- **`services/cache_local.py`** guarda um retrato em arquivo: os rostos, os
  eventos da janela e os dispositivos. `decidir()` responde às mesmas
  perguntas em Python (vizinho mais próximo por cosseno em numpy) e devolve
  **o mesmo dicionário, com as mesmas mensagens** que a versão SQL.
- **`services/fila_offline.py`** é uma fila em arquivo JSONL. Cada veredito
  tomado offline é enfileirado **com o horário em que a porta decidiu**.
- Quando a rede volta, a fila sobe na primeira leitura que der certo, e os
  logs entram com o `criado_em` original.

> **Como explicar:** "A presença gravada é a da porta, não a do envio. Dia 15
> três leituras foram gravadas 19:20:56, 19:21:02 e 19:21:07 — os horários
> reais — e não a hora em que a internet voltou."

Duas decisões de projeto aqui:

- **A cópia mora no Flask, não na Pi.** O plano inicial era a Pi guardar tudo,
  mas isso a obrigaria a calcular o embedding sozinha, que é justamente o que
  ela não faz. Como o elo que quebra é a internet e não a rede local, a cópia
  fica do lado que já tem os modelos. **A Pi não muda em nada.**
- **A manutenção pega carona.** Subir a fila e renovar a cópia acontecem
  depois de uma leitura que deu certo, não numa thread de fundo: é o único
  momento em que isso importa, e é quando já se sabe que o banco responde.

### Autenticação de pessoas (o app)

Diferente do leitor. `utils/auth_middleware.py` valida o JWT que o **Supabase
Auth** emitiu, contra a **JWKS pública** do projeto — assinatura **ES256**,
chave assimétrica. A API nunca vê senha e nunca emite token.

> **Como explicar:** "A API não faz login. Quem autentica é o Supabase; aqui
> a gente só verifica a assinatura do token com a chave pública. Se essa API
> for comprometida, não tem senha nenhuma pra vazar."

---

## Camada 3 — O banco: Supabase Postgres + pgvector

Nove tabelas. As que importam pra entender o fluxo:

| Tabela | O que guarda |
|---|---|
| `profiles` | nome, matrícula, papel (`admin`/`professor`/`aluno`). O `id` é o mesmo do `auth.users` |
| `faces` | **o embedding** (`vector(512)`), até 5 por pessoa. Sem imagem |
| `consentimentos` | quem consentiu, quando, e com qual **versão** do texto |
| `turmas` / `turma_alunos` | a disciplina e seus alunos |
| `recorrencias` | a regra "toda segunda, 20h-22h", que gera eventos |
| `eventos` | a aula: título, **local**, início e fim (`timestamptz`) |
| `evento_participantes` | a lista de quem pode entrar naquela aula, já explodida |
| `access_logs` | toda leitura, liberada ou negada, com motivo |
| `dispositivos` | os leitores: nome, **local**, hash da chave, `ultimo_visto` |

### Três coisas não óbvias

**1. Não existe índice `ivfflat` na tabela `faces`.** Já existiu, e fazia a
porta **recusar gente cadastrada** — um índice aproximado devolvia zero
linhas. A busca é varredura exata. Com o volume de uma escola isso é
irrelevante; com milhões de rostos precisaria ser revisto.

**2. O Row Level Security nega tudo.** As tabelas têm RLS ligado e **nenhuma
policy**. Ou seja, a Data API do Supabase não devolve nada pra ninguém.

> **Como explicar:** "É de propósito, e é o que permite a chave publishable do
> Supabase estar num repositório público sem risco: ela não abre nada. Todo
> acesso a dado passa obrigatoriamente pelo Flask, que é onde as regras
> estão. É também por isso que o app não usa Realtime — a tela relê de 10 em
> 10 segundos."

**3. `evento_participantes` é a lista já explodida.** Quando o professor
convida uma turma, o servidor grava uma linha por aluno em vez de guardar
"turma 3". A coluna `origem` diz se veio de turma ou foi manual, e `turma_id`
é o que liga a presença de volta à disciplina — é dele que sai a frequência.

### A conta de frequência

```
faltas    = aulas encerradas − presenças
limite    = int(aulas PREVISTAS × 0,25)
reprovado = limite ≥ 1 e faltas > limite
```

Duas decisões que valem explicar:

- **O limite sai das aulas MARCADAS, não das já dadas.** Faltar 1 de 2 aulas
  dadas não é reprovação se o semestre tem 30. Calcular sobre as encerradas
  faria o app gritar em março com quem está bem.
- **O `limite ≥ 1` não é detalhe.** `previstas` são as aulas já criadas, e o
  sistema não sabe o tamanho do semestre. Sem essa condição, quem perdesse a
  primeira aula do ano apareceria reprovado — foi o que aconteceu rodando
  contra o banco real.

E **frequência é por disciplina**: 75% é por matéria. Somar todas dá um
número que não decide nada — 80% no agregado esconde 50% numa delas.

---

## Camada 4 — O app Flutter

Estrutura em quatro pastas: `screens/` (13 telas), `services/` (chamadas
HTTP), `models/` (o que vem do JSON), `config/` (tema e endereço).

### O que o professor faz

- **Turmas** — cria a disciplina, adiciona alunos
- **Aulas** — evento avulso ou recorrência ("toda segunda, 20h-22h"), e
  convida turmas ou pessoas
- **Agora** — a aula em andamento, com quem já entrou, atualizando de 10 em
  10 segundos
- **Frequência da turma** — quem está por um fio
- **Dispositivos** — cadastrar leitor e rotacionar chave

### O que o aluno faz

- **Cadastrar o rosto** — consentimento, câmera, e a lista das suas capturas
- **Minha frequência** — por disciplina, com **quantas faltas ainda cabem**

### Três detalhes de implementação

**O endereço do servidor é editável na tela** (Ajustes → Servidor). Não
precisa recompilar quando o IP do PC muda — foi o que resolveu o problema
mais repetido do desenvolvimento.

**A recorrência conta as ocorrências duas vezes.** `contarOcorrencias` no
Dart mostra "vai criar 15 aulas" **antes** de enviar, e
`expandir_ocorrencias` no Python cria de verdade. São duas implementações da
mesma regra, e existem testes espelhados nos dois lados justamente porque, se
discordarem, o app mente sobre o que o botão vai fazer — e a criação é em
lote, enquanto desfazer é de um em um.

**Datas em ISO 8601.** O Flask serializa `datetime` em formato HTTP por
padrão, que quebra o parser do Dart. `utils/json_provider.py` existe só pra
isso.

---

## O que impede a burla, em uma passada

| Ataque | O que barra |
|---|---|
| Foto ou tela com o rosto de outro | Vivacidade (MiniFASNet), + janela de 6s após suspeita forte |
| Cadastrar foto de alguém tirada da galeria | Captura ao vivo obrigatória, sem opção de galeria |
| Cadastrar o rosto de um colega já cadastrado | Um rosto pertence a uma conta só — o servidor recusa |
| Colar uma captura estranha na própria conta | Da 2ª foto em diante ela tem que parecer com as que a conta já tem (limiar 0,70) |
| Entrar numa aula que não é sua | Passo 4: tem que estar na lista |
| Roubar a Raspberry | Não tem rosto nem senha dentro dela; a chave é revogável |
| Ler o banco por fora do Flask | RLS nega tudo, sem policy nenhuma |
| Gravar biometria sem consentimento | 403 no servidor, **antes** de calcular o vetor |

**E o que continua possível:** a primeira captura de uma conta. Dá pra
cadastrar o rosto de um colega que nunca se cadastrou e receber a presença
dele. Nenhuma barreira pega — a vivacidade confirma que é gente, e é; "um
rosto por conta" compara com quem já está cadastrado, e ele não está; e a
regra de parecer com as outras não tem com o que comparar na primeira. **Não
há solução puramente técnica**: o servidor não tem como saber de quem é um
rosto que vê pela primeira vez. Fecharia com aprovação do professor na
primeira foto.

---

## LGPD, em três frases

Vetor facial é **dado pessoal sensível** (art. 5º, II), e tratar dado
sensível exige consentimento **específico e destacado** — o consentimento
genérico de usar o app não serve.

O app mostra o termo antes da primeira captura, o texto **vem do servidor**
(não embutido no APK, senão um app antigo mostraria uma versão diferente da
que o banco registra), e o aceite é gravado com **versão**: se o texto mudar,
quem aceitou o anterior é perguntado de novo.

Três decisões fazem esse registro valer algo: a recusa é do **servidor** (403,
não da tela); a checagem vem **antes** de calcular o embedding, porque
transformar a foto em vetor já é tratar o dado; e revogar **é** apagar o
rosto, mas o registro antigo é carimbado, não removido — ele é a prova de que
o tratamento anterior era legítimo.

---

## Números que a gente mediu

Ter medido é o argumento; os valores são consequência.

| | |
|---|---|
| Limiar de identidade | **0,30** |
| Duas capturas da mesma pessoa | 0,033 a 0,230 da irmã mais próxima (já houve par legítimo a 0,520) |
| Duas pessoas diferentes, par mais próximo | **0,374** — folga de +0,074 |
| Margem ao longo do tempo | 0,796 (3 capturas) → 0,623 (7) → 0,374 (16) |
| Limiar de vivacidade | **0,60**, e suspeita forte a 0,97 valendo 6s |
| Pessoa real acusada de foto | até 58% em condições normais, **96% num caso** |
| Foto acusada de foto | 68%, 72%, 99%, 100% |

**A conclusão honesta:** as duas faixas da vivacidade se sobrepõem com esta
câmera. Não existe configuração que dê ao mesmo tempo entrada instantânea e
recusa garantida de foto — é **escolha, não afinação**, e o projeto escolheu
segurança. A vivacidade aqui **encarece a fraude, não a elimina**; garantia
exigiria outro sensor (infravermelho ou profundidade), não outro número.

O que mais melhorou o sistema não foi ajuste de limiar, foi **resolução**: o
MiniFASNet julga textura de pele num recorte de 80×80, e num rosto de ~100
pixels não havia textura pra ver. 640x480 → 1280x720 separou as faixas.

Reproduzir as medidas: `cd api && venv/Scripts/python medir_rostos.py`
