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
        └──── rede local ─────┘         └──── internet ────┘
                              ▲
                              │ HTTP + JWT
                       ┌─────────────┐
                       │   Flutter   │
                       │  (celular)  │
                       └─────────────┘
```

Repare no lado direito: o banco fica na AWS, então toda decisão da porta
sai do prédio. É a limitação principal do sistema hoje — ver
**O que falta**.

## As três partes

| Pasta | O que é |
|---|---|
| [`app/`](app/) | Aplicativo Flutter. Professor cria turmas e aulas e acompanha quem entrou; aluno vê suas aulas e quantas faltas ainda cabem em cada disciplina. |
| [`api/`](api/) | Servidor Flask. Valida o token, calcula o vetor do rosto e decide se libera. É onde mora toda a regra de negócio. |
| [`api/raspberry/`](api/raspberry/) | Código que roda na Raspberry Pi da porta: captura da câmera e a tela do totem (LIBERADO / NEGADO). |

## Como a decisão de liberar é tomada

Quando um rosto chega, o Flask checa cinco coisas em ordem. Basta uma
falhar para negar:

1. **Rosto** — a foto tem um rosto reconhecível?
2. **Vivacidade** — é gente ali na frente, ou uma foto impressa e uma tela
   erguida diante da câmera?
3. **Identidade** — o vetor bate com alguém cadastrado? (distância de
   cosseno abaixo de 0,30)
4. **Aula** — existe uma aula acontecendo agora naquele lugar?
5. **Lista** — essa pessoa foi convidada para essa aula?

O reconhecimento usa **Facenet512**: a foto vira um vetor de 512 números e
a comparação é uma distância entre vetores, não uma comparação de imagens.
A imagem em si nunca é gravada — nem no servidor, nem no leitor da porta.

## O que impede a burla

O jeito óbvio de enganar uma porta que olha rostos é mostrar o rosto de
outra pessoa. Dá pra tentar de dois lados, e cada um é barrado no seu:

**Na porta**, o passo de vivacidade. O anti-spoofing (MiniFASNet) olha
textura e reflexo pra separar pele de papel e de LCD — levantar o celular
com a foto de alguém cadastrado não abre.

Esse passo tem um limiar, e ele é o ponto de equilíbrio do sistema
inteiro. O MiniFASNet devolve três probabilidades (foto impressa, pessoa
real, tela) e o padrão do DeepFace nega sempre que "real" não é a maior —
decisão no voto de minerva, que barra gente de verdade em luz ruim, de
lado ou longe da câmera. Aqui a recusa só vale quando o modelo está
convicto: `ANTISPOOF_LIMIAR` no `.env` da API, **0.60**, medido.

Como esse número foi parar aí é a parte que interessa. Com a câmera da
porta em 640x480, uma pessoa de verdade foi acusada de ser foto a 77%, 82%
e 86% — e uma **foto** marcou 40%. As faixas se sobrepunham, ou seja,
**nenhum limiar separava**: foi assim que uma foto abriu a porta durante um
teste em 15/08/2026. Dobrando a captura para 1280x720, as faixas se
separaram — pessoa acusada de falsa no máximo a 58%, fotos a 68%, 99% e
100% — e 0.60 cabe no vão, encostado no limite de baixo de propósito: foto
entrando é falha de segurança, pessoa barrada é um segundo de espera, e a
porta lê de novo.

O que melhorou não foi ajuste fino de limiar, foi **resolução**. O
MiniFASNet julga textura de pele num recorte de 80×80 pixels; num rosto de
~100 px não havia textura para ver, e ele chutava. Duas lições que valem
além deste projeto: o reconhecimento se contenta com pouca resolução mas a
vivacidade não, e **o limiar só decide quando negar** — se o modelo disser
"pessoa" sobre uma foto, nenhum valor ali a barra. Contra esse caso existe
uma segunda regra: uma leitura acima de 97% de suspeita vale pelos 6
segundos seguintes, então a foto que oscila entre "fraude" e "pessoa" não
entra na leitura favorável.

**E o mais honesto: com esta câmera as duas faixas se sobrepõem.** Em 16/08
o rosto de uma pessoa presente foi acusado de foto a 96%, e fotos já
marcaram 68%. Ou seja, não existe configuração que dê ao mesmo tempo
entrada instantânea para gente de verdade e recusa garantida para foto — é
escolha, não afinação. O projeto escolheu o lado da segurança: com o limiar
em 0,60 cerca de uma leitura em três é recusada, e como o leitor pergunta a
cada 1,2 s isso vira 1 a 3 segundos parado na porta em vez de entrada
instantânea. A vivacidade aqui **encarece a fraude, não a elimina**; quem
precisar de garantia precisa de outro sensor (infravermelho ou
profundidade), não de outro número.

Toda leitura sai no console do servidor (`[vivacidade] pessoa (91% de
certeza, limiar 60%)`), então recalibrar numa sala nova é olhar os números
de lá, não confiar nestes.

**No cadastro**, três regras. A foto tem que ser tirada na hora, sem opção
de galeria: o anti-spoofing reconhece foto de tela, mas não distingue uma
selfie digital normal de outra pessoa, então qualquer imagem salva no
celular serviria. Um rosto pertence a uma conta só — se já está cadastrado
em outra, o servidor recusa. Sem isso dava pra registrar o rosto de um
colega e receber a presença dele, uma fraude que não é barrada por ninguém
e não aparece no log: só o nome vem trocado.

E, da segunda foto em diante, a captura tem que parecer com alguma que a
pessoa já tem (limiar próprio, 0,70 — bem mais frouxo que o do
reconhecimento, porque duas fotos legítimas em condições diferentes ficam
longe uma da outra). A regra anterior só recusa rosto que **já está** em
outra conta; rosto de quem não é cadastrado entrava calado, e foi o que
aconteceu em 13/08/2026 — a medição achou, entre as 5 capturas de um
aluno, uma a 0,895 de todas as outras. Um vetor desses não atrapalha o
dono, mas fica no banco como uma chave a mais capaz de abrir a porta no
nome dele. A primeira foto da conta segue sem essa proteção, por não ter
com o que se comparar — é a limitação conhecida descrita abaixo.

### A limitação que sobra: a primeira foto

As três regras acima protegem tudo, **menos a primeira captura de uma
conta**. O ataque que continua possível é este:

> Cadastro o rosto de um colega que nunca se cadastrou, com ele ali do meu
> lado. Ele chega na porta, o leitor acha o vetor mais próximo — que está
> na minha conta — e marca **a mim** como presente. Ele consta ausente.

Nenhuma das barreiras pega esse caso, e vale entender por quê. A
vivacidade só confirma que é gente presente, e é: o colega está ali. A
captura ao vivo, sem galeria, só garante que a foto é do momento — não de
quem. "Um rosto pertence a uma conta só" compara com quem **já está**
cadastrado, e ele não está. E a regra nova compara com as outras fotos da
própria conta, que na primeira não existem.

**Não há solução puramente técnica.** O servidor não tem como saber de
quem é um rosto que está vendo pela primeira vez — não existe nada com que
comparar. Fechar isso exige uma confirmação de fora do sistema: a primeira
captura de cada conta ficar pendente até um professor aprovar.

Foi decidido **não** construir isso: custa uma tela nova pro professor e
um estado a mais no cadastro, e o proveito da fraude é baixo perto do
risco de fazê-la — quem tenta precisa da colaboração presencial da pessoa
que vai ficar marcada como ausente, e é ela quem reclama no fim do mês.
Fica registrado aqui como limitação conhecida, e não como descuido.

Na tela de rosto do aplicativo cada captura aparece com a hora em que foi
feita e pode ser removida sozinha, sem apagar as outras. Não há miniatura
porque não há imagem: o servidor extrai o vetor e descarta a foto. O que
permite escolher qual remover é o aviso **"não parece as suas outras
fotos"**, calculado no servidor pelo mesmo critério que recusa uma captura
nova — sem ele seriam cinco linhas idênticas com horários diferentes.

Cada pessoa pode guardar até 5 capturas (luz, ângulo, óculos). A busca
compara contra a mais próxima delas, o que cobre a variação real sem
afrouxar o limiar — capturas a mais não aproximam um estranho.

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

## Consentimento (LGPD)

Vetor facial é **dado pessoal sensível** (LGPD, art. 5º, II), e tratar dado
sensível exige consentimento *específico e destacado* — o consentimento
genérico de usar o app não serve, e "a pessoa apertou o botão de cadastrar
rosto" também não.

Antes da primeira captura, o app mostra o termo (que vem do servidor, não
embutido no APK) e registra o aceite em `consentimentos`: quem, quando, e
com qual **versão** do texto. A versão importa — se o texto mudar, quem
aceitou o anterior não consentiu com o novo, e é perguntado de novo.

Três decisões que fazem esse registro valer alguma coisa:

- **A recusa é do servidor, não da tela.** `POST /faces` responde 403 sem
  consentimento válido. Se quem decidisse fosse o app, bastaria um APK
  antigo — ou qualquer coisa que saiba fazer um POST — pra gravar biometria
  sem consentimento.
- **A checagem vem antes de calcular o embedding.** Transformar a foto em
  vetor já é tratar o dado; checar depois seria processar primeiro e pedir
  licença depois.
- **Revogar é apagar o rosto**, e é a mesma ação: `DELETE /faces` remove as
  capturas e carimba `revogado_em`. O registro antigo **não** é apagado —
  ele é a prova de que o tratamento anterior era legítimo, e sumir junto com
  o dado seria destruir a própria defesa.

Quem cadastrou rosto antes de 16/08/2026 aparece com versão `0-implicito`:
consentiu de fato, mas com um texto que não existia. O sistema trata isso
como pendente e pergunta de novo, em vez de fingir que a pessoa leu.

## Segurança

- `app/lib/config/app_config.dart` contém a chave **publishable** do Supabase.
  Ela pode ficar em repositório público **porque as tabelas têm Row Level
  Security ligado sem nenhuma policy** — ou seja, a Data API nega tudo, e
  todo acesso passa obrigatoriamente pelo Flask.
- `api/.env` **nunca** entra no repositório. Tem a senha do Postgres e o
  segredo de JWT, que dão acesso direto ao banco por fora do Flask.
- **Tudo exige internet** — ver "O que falta" abaixo.

## Estado

Funcionando ponta a ponta, validado em 12/08/2026 com o ciclo completo:
rosto cadastrado pela câmera do aplicativo num celular físico, pessoa
reconhecida na porta pela Raspberry, presença gravada. Naquele dia as
checagens de rosto, identidade, aula e lista foram observadas acertando —
inclusive a mais sutil, alguém **reconhecido** e ainda assim negado por
não estar na lista daquela aula.

Em 13/08/2026 a **vivacidade** foi medida na porta pela primeira vez, e em
15/08 remedida numa sala diferente — onde os números foram outros e a
calibração teve que ser refeita. Ver "O que impede a burla": foi nesse dia
que uma foto conseguiu abrir a porta, e o conserto veio da resolução da
câmera, não do limiar.

Em 15/08/2026 o **modo offline** foi provado na porta. Com o servidor sem
alcançar o Postgres, três leituras foram decididas pela cópia local e
enfileiradas; quando o banco voltou, subiram sozinhas na leitura seguinte —
**com o horário original de cada uma**, 19:20:56, 19:21:02 e 19:21:07, e
não com a hora em que a rede voltou. A presença gravada é a da porta.

No mesmo teste apareceu um defeito que só se vê assim: o servidor **não
subia** sem banco, porque o pool abria uma conexão no boot. Ou seja, o modo
offline só salvava se o processo já estivesse de pé — uma queda de luz
durante o apagão mataria justamente o que existe para sobreviver a ele.
Corrigido: sobe sem banco e se reconecta sozinho.

No mesmo dia o totem passou a se encaixar em qualquer resolução, e isso
foi conferido rodando no mini monitor de 7" da porta: o layout continua
desenhado em 1080p e é ajustado à tela real na hora de exibir.

O que falta:

- **Sem internet, nada funciona.** O desenho parece local — a Raspberry
  fala com o Flask no PC, os dois na mesma rede — mas o Flask guarda tudo
  no Postgres do Supabase, que fica na AWS em São Paulo. Toda decisão da
  porta é uma consulta que atravessa a internet, e o login é no Supabase
  Auth. Cair a rede do prédio derruba o sistema inteiro, não só o app.

  **Começado em 13/08/2026, e a solução mudou de lugar.** O plano era a Pi
  guardar a cópia — mas isso a obriga a calcular o embedding sozinha, que é
  justamente o que ela não faz e o motivo de ser burra. Como o elo que
  quebra é a internet, e não a rede local, a cópia fica no **Flask**:
  `api/services/cache_local.py` monta um retrato dos rostos, dos eventos da
  janela e dos dispositivos, e responde às mesmas três perguntas da porta
  sem sair do prédio. A Pi não muda em nada.

  A porta já decide sem banco: `/faces/recognize` e a autenticação do
  leitor caem pra cópia quando o Postgres não responde, e cada veredito
  tomado assim vai pra uma fila em arquivo (`services/fila_offline.py`)
  que sobe sozinha na primeira leitura em que a rede voltar — carregando a
  hora em que a porta decidiu, não a hora do envio. A cópia se renova de
  carona nas leituras que dão certo.

  **Provado na porta em 15/08/2026** (ver "Estado"), com a Raspberry
  lendo rostos e o servidor sem alcançar o Postgres. O que continua sem
  prova é o caso de a rede cair *no meio* de uma escrita — o teste foi com
  o banco já fora de alcance, não caindo durante.

  O login do app segue dependendo do Supabase Auth de qualquer forma;
  offline vale pra porta, não pra entrar no aplicativo.
- **As duas distribuições se sobrepõem, e o limiar de 0,30 só funciona por
  causa das várias capturas.** Medido em 13/08/2026 com 7 capturas de 3
  pessoas (`cd api && venv/Scripts/python medir_rostos.py`):

  | | distância |
  |---|---|
  | duas capturas da MESMA pessoa | 0,116 a **0,520** |
  | duas pessoas diferentes | a partir de **0,451** |

  Repare que 0,520 é maior que 0,451: existem duas fotos do mesmo rosto
  mais distantes entre si do que dois rostos diferentes. Ou seja, **não
  existe um limiar único que separe "mesma pessoa" de "pessoa diferente"**
  nesses dados. O que faz o sistema funcionar é a busca comparar contra a
  captura MAIS PRÓXIMA das 5: cada captura está entre 0,116 e 0,230 de
  alguma irmã, e é sempre uma delas que responde. Com uma foto só por
  pessoa, a porta barraria quem tem direito.

  A margem também está encolhendo conforme o banco cresce: o par mais
  próximo entre pessoas diferentes era 0,796 com 3 capturas, 0,623 com 7 e
  0,451 depois do recadastro. Ainda sobra folga sobre 0,30, mas isso é
  medida de 3 pessoas — vale remedir a cada leva de cadastros, e é pra isso
  que o `medir_rostos.py` existe.

