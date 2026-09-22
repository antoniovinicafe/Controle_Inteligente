# Handoff — página interativa do Fetin para a FETIN

Briefing para construir uma página web interativa que roda na bancada da
feira. Tudo que você precisa está aqui: o projeto, o contexto de uso, o
sistema de design que já existe, o conteúdo de cada seção com os dados
reais, e a especificação do elemento interativo principal.

---

## 1. O que é o projeto

**Fetin** é um sistema de controle de acesso por reconhecimento facial que
registra presença em aula automaticamente. Projeto de engenharia do Inatel.

A pessoa chega na porta da sala, uma câmera a reconhece, e a presença é
gravada sozinha — sem lista de chamada, sem crachá, sem ninguém fazer nada.

São três partes:

- **Um leitor na porta** — Raspberry Pi com câmera e uma tela em modo totem
  que responde LIBERADO ou NEGADO. Ela **não decide nada**, de propósito: só
  tira foto e pergunta ao servidor, não reconhece nada
- **Um servidor** — onde está toda a inteligência: reconhecimento facial
  (Facenet512), detecção de fraude (MiniFASNet) e as regras de acesso
- **Um aplicativo** — professor cria aulas e acompanha quem entrou; aluno
  cadastra o próprio rosto e vê quantas faltas ainda cabem em cada matéria

O rosto vira uma lista de 512 números e a comparação é distância entre
vetores. **A imagem nunca é armazenada** — nem no servidor, nem na porta.

---

## 2. Onde esta página vai rodar — leia antes de desenhar

| | |
|---|---|
| **Contexto** | FETIN, feira de tecnologia do Inatel |
| **Dispositivo** | Notebook ou tablet na bancada, tela sempre ligada |
| **Público** | Visitantes que param 40 segundos e vão embora. Professores, alunos, famílias, gente de empresa |
| **Situação** | O leitor facial de verdade está ligado ao lado, com uma porta e um totem funcionando |

### As quatro restrições que governam o design

**1. Não é apresentação, é estação.** Não tem apresentador avançando slide,
não tem começo nem fim. Alguém chega no meio, mexe, e vai embora. Qualquer
coisa que dependa de ordem ou de alguém explicando está errada.

**2. A página não compete com a porta.** O leitor de verdade é a atração, e
ela está a dois metros. A página mostra **o que a porta não mostra**: as
telas do app, a frequência, a exportação, e os números medidos. Se um
visitante só olhar a página e não a porta, o design falhou.

**3. Precisa funcionar sem ninguém.** Metade do tempo os três da equipe
estarão atendendo outro visitante. A página tem que se explicar sozinha e
convidar ao toque sem instrução.

**4. Tem que sobreviver a ser tocada errado.** Visitante de feira aperta
tudo, arrasta, dá dois toques. Nada pode entrar num estado do qual não se
volta, e não existe botão de "recarregar" que alguém vá achar.

---

## 3. Sistema de design — já existe, é o ativo mais forte

**Não invente identidade.** O app e o totem já têm uma, e ela é boa. A
página precisa parecer a mesma família — principalmente porque o totem vai
estar ligado ao lado, e quem olhar de um pro outro tem que ver um sistema
só.

### As duas vozes tipográficas — a regra central

Esta é a decisão de design mais importante do projeto, e a página deve
seguir e **mostrar** ela:

| Fonte | Para quê |
|---|---|
| **Jost** | o que uma **pessoa** escreveu: nome, título da aula, local, texto corrido |
| **IBM Plex Mono** | o que o **sistema** registrou: matrícula, horário, distância, contador, rótulo de seção |

As duas estão no Google Fonts.

E não é enfeite. Num controle de acesso, a diferença entre "o que alguém
digitou" e "o que a máquina gravou" é exatamente o que dá credibilidade à
tela — e ver isso sem precisar ler é o ponto. Todo número medido nesta
página é voz de máquina. Todo nome de pessoa é voz humana. **Nunca troque.**

O leitor da porta faz a mesma coisa com outras duas fontes (uma gótica
pesada para pessoa, uma monoespaçada para máquina), então a regra é do
sistema, não do app.

### Paleta

O totem é escuro; o app tem claro e escuro. **Para esta página, fundo
escuro** — a bancada tem luz de feira e o totem ao lado é escuro.

```
#0E1518   fundo            (o app escuro)
#161F23   superfície       blocos elevados
#0C1A1E   fundo do totem   quando estiver imitando a tela da porta
#14282E   placa do totem
#15616D   petróleo         cor de marca, estrutura, linhas
#35D6A0   menta            LIBERADO, acerto, confirmação
#F0655A   coral            NEGADO, recusa
#F0B45E   âmbar            alerta, "no limite"
#E8F1F2   texto
#6E8F98   apagado          secundário, rótulos
```

**Menta e coral são vocabulário, não decoração.** Menta só quando o assunto
é acesso concedido; coral só quando é recusa. Usar as duas juntas por
estética destrói o significado das duas.

Cantos: **14px**. Generosos o bastante pra parecer intencional, discretos o
bastante pra não virar bolha.

### Direção estética

O projeto é um **instrumento de medição**, não um produto de consumo. A
referência é painel de controle, leitura de sensor, régua.

A filosofia do tema do app, literalmente do código: *"a ideia é sumir —
nada de sombra, card flutuante ou cor gritando. O que dá forma à tela é
espaçamento e hierarquia de texto, não caixa em volta de tudo."*

**Não faça:** gradiente suave, glassmorphism, ícone genérico de cadeado ou
rosto poligonal, ilustração corporativa, foto de banco de imagem, mockup de
celular flutuando em ângulo com sombra, numeração decorativa 01/02/03 em
coisa que não é sequência, nem aquele visual creme com serifa de alto
contraste e detalhe terracota que aparece em todo site gerado por IA.

**Faça:** hierarquia dura, espaço vazio, alinhamento rígido, um elemento
dominante por seção.

---

## 4. O ELEMENTO PRINCIPAL — o simulador da porta

**Isto é o coração da página.** Se só uma coisa for bem feita, é esta.

### A ideia

O visitante escolhe um cenário e vê a tela do totem responder **exatamente
como a de verdade**, com as cinco checagens acendendo em sequência. Em
cinco segundos ele entendeu o sistema inteiro — e é a única coisa da
bancada que ele pode operar sem pedir licença a ninguém.

### Como funciona

Cinco botões, cada um um cenário:

| Botão | O que acontece |
|---|---|
| **Pessoa cadastrada, com aula** | passa as cinco → **LIBERADO** |
| **Foto na tela** | para na VIVACIDADE → *"Foto ou tela não abre a porta"* |
| **Rosto não cadastrado** | para na IDENTIDADE → *"Cadastre seu rosto no aplicativo"* |
| **Cadastrado, sem aula agora** | para na AULA → *"Nenhuma aula acontecendo aqui agora"* |
| **Cadastrado, fora da lista** | para na LISTA → *"Você não foi convidado para esta aula"* |

### A tela do totem, fielmente

Reproduza o layout da porta. Ele é, de cima pra baixo:

1. Cabeçalho: `INATEL · CONTROLE DE ACESSO` à esquerda, relógio à direita —
   ambos em mono, pequenos, apagados
2. Um **visor retrato 3:4** centralizado, com moldura feita **só de quatro
   cantos** (não uma caixa fechada) — diz "enquadre aqui" sem cercar o
   rosto da pessoa
3. Uma **trilha de cinco segmentos** logo abaixo, rotulados em mono:
   `ROSTO  VIVACIDADE  IDENTIDADE  AULA  LISTA`
4. O veredito em tipografia **enorme**: `LIBERADO` ou `NEGADO`
5. O nome da pessoa abaixo, em Jost
6. A explicação da recusa, menor e apagada

### As regras de cor da trilha — copie exatamente

É o que faz a simulação ensinar em vez de só animar:

- Etapa que **passou** → menta
- Etapa onde **parou** → coral
- Etapa que **nem foi perguntada** → apagada, cor de placa

Uma recusa na AULA mostra ROSTO, VIVACIDADE e IDENTIDADE em menta, AULA em
coral, e LISTA apagada. **Esse é o ponto pedagógico inteiro:** dá pra ver
que o sistema reconheceu a pessoa e ainda assim não abriu.

### O detalhe que faz diferença

O preview no visor é **duotone petróleo enquanto procura** e **vira cor
real quando libera**. Na porta isso resolve um problema prático (a luz de
LED verde da quadra tinge tudo), mas visualmente é o momento da tela.
Reproduza: é a recompensa do LIBERADO.

Ritmo sugerido: as etapas acendem em sequência rápida, ~200ms cada, e o
veredito aparece depois. Rápido o bastante pra não testar a paciência de
ninguém numa feira, lento o bastante pra dar pra ver a sequência.

Respeite `prefers-reduced-motion`.

### O que NÃO fazer aqui

Não peça acesso à câmera do visitante. Não colete imagem de ninguém. Numa
página sobre privacidade biométrica, pedir a câmera de quem passa é
exatamente a contradição que alguém vai notar — e com razão.


---

## 5-bis. A CAIXA EM 3D — o segundo elemento interativo

Depois do simulador, é isto que vai fazer alguém chamar o amigo pra ver.

### Os arquivos

Três peças impressas, em `caixa/` no repositório, formato STL binário:

| Arquivo | Triângulos | Tamanho | Dimensões (mm) |
|---|---|---|---|
| `frente.stl` | 3.036 | 148 KB | 193,5 × 61,0 × 190,5 |
| `tampa.stl` | 2.064 | 101 KB | 193,5 × 11,5 × 171,0 |
| `lateral.stl` | 324 | 16 KB | 7,0 × 61,0 × 65,5 |

**260 KB e 5.424 triângulos no total** — não há preocupação de desempenho.
Carregue com `STLLoader` do Three.js (cdnjs). A malha é de CAD, então tem
normais boas e não precisa de tratamento.

### A interação

**Vista explodida ↔ montada**, controlada por um único controle — botão ou
slider. As três peças se separam ao longo do eixo de montagem e voltam.
Arrastar gira, rolar aproxima.

É a interação certa porque responde a pergunta que a pessoa tem olhando a
caixa fechada na bancada: *"como isso é montado?"*

### O que transforma isso de enfeite em conteúdo: os pontos de interesse

**Este é o ponto da seção.** Marcadores discretos no modelo, e clicar em
cada um conta o que aquele detalhe físico causou no software. A caixa deixa
de ser "olha, a gente imprimiu" e passa a ser o argumento de que hardware e
software foram projetados juntos.

**1. Na abertura da câmera, no topo da frente**

> O cabo flat não cabia com a câmera na posição natural, e ela acabou
> parafusada **girada 90°**. Corrigir isso em software teve um efeito que
> ninguém planejou: o sensor é 16:9 e o visor da porta é retrato 3:4, então
> na orientação original as laterais da imagem eram descartadas. Girada, o
> recorte do rosto saiu de 540×720 para **720×960 — 78% mais pixels**.
>
> E foi isso que deu ao projeto a melhor medição de detecção de fraude que
> ele já teve: 10 fotos, todas recusadas, a mais fraca a 75%. Uma restrição
> de fabricação tornou o sistema **mensuravelmente mais seguro**.

**2. Na moldura inferior, sobre a área da tela**

> A moldura impressa cobre a parte de baixo do LCD, e o veredito ficava
> atrás do plástico. Virou um ajuste de margem e deslocamento vertical no
> arquivo de configuração — porque isso não é decisão de projeto, é
> consequência de como *esta* caixa ficou, e a próxima vai ficar diferente.

**3. Na área da tela**

> O monitor que entrou na caixa é 4:3 e o layout do totem assumia 16:9.
> Agora o desenho calcula a proporção da tela real em tempo de execução: numa
> 4:3 o quadro fica 1440×1080 e preenche tudo, numa 16:9 continua 1920×1080.

Se três marcadores forem demais para o espaço, o da câmera é obrigatório —
é a história boa.

### A frase que resume a seção

> **Três correções de software saíram de uma caixa que não fechava. Uma
> delas deixou o sistema mais seguro.**

### Material e ambiente — onde 3D na web costuma ficar feio

O modelo tem que parecer **peça impressa em PLA**, não render de produto.

**Faça:** material fosco, difuso, sem brilho especular quase nenhum. Duas
ou três luzes suaves, uma de preenchimento pela frente. Cor da peça num tom
dessaturado do petróleo (`#15616D`) ou um grafite neutro que deixe as cores
da interface aparecerem por contraste. Se conseguir sugerir a textura de
camadas da impressão sem virar truque, ótimo — mas sutil.

**Não faça:** material cromado ou vidro, reflexo de estúdio, HDRI de
showroom, piso espelhado com grade infinita, rotação automática que nunca
para (cansa e rouba o foco do simulador, que é mais importante), sombra de
contato exagerada.

### Comportamento

- **Sem rotação automática contínua.** Uma volta lenta de apresentação nos
  primeiros segundos e para, ou nada. A página tem dois elementos
  interativos e eles não podem competir por atenção.
- **Volta ao repouso** junto com o resto da página depois de 30 segundos
  sem toque: montada, no ângulo inicial.
- **Fallback obrigatório.** Se WebGL não estiver disponível, ou o
  carregamento falhar, mostre uma imagem estática da caixa e o texto dos
  pontos de interesse. A seção não pode virar um retângulo vazio na feira.
- **Toque:** um dedo gira, dois dedos aproximam. E o gesto de rolar a página
  precisa continuar funcionando — não capture o scroll vertical dentro do
  canvas, senão o visitante fica preso na seção e não consegue sair.

### Onde ela entra na página

Depois do simulador e antes ou junto da seção de números medidos, porque a
história do ponto de interesse 1 **é** a explicação da terceira medição de
vivacidade. As duas seções se sustentam: a caixa explica por que os números
melhoraram.

---

## 5. As outras seções

Ordem sugerida, mas a página não deve depender dela.

### A frase de abertura

Uma linha, grande, sozinha:

> **A lista de chamada é o documento mais falsificado desta universidade.**

Nada além. Sem logo enorme, sem subtítulo explicando a frase.

### Como a decisão é tomada

As cinco perguntas em ordem, e a ideia de que basta uma falhar:

> Tem um rosto na imagem? É uma pessoa de verdade, ou uma foto? Esse rosto
> bate com alguém cadastrado? Tem aula acontecendo agora nesta sala? Essa
> pessoa foi convidada?

Com uma frase destacada, que é a ideia que o projeto quer que fique:

> **Reconhecer não é autorizar.**

### Rosto vira número

Explique o mecanismo sem jargão: a foto vira uma lista de 512 números, e
reconhecer é medir distância entre pontos. Abaixo de **0,30** é a mesma
pessoa.

Se quiser um elemento gráfico, aqui é o lugar — mas **não** desenhe uma
malha de pontos no rosto de alguém, que é o clichê do gênero. O honesto é
mostrar números.

E o ponto de privacidade, que vale destacar: **do vetor não se reconstrói o
rosto.** É por isso que a lista de capturas no app não tem miniatura — não
há imagem para mostrar.

### Os números medidos — a seção que separa isto de um trabalho escolar

Use os dados reais. Todos em voz de máquina (mono).

**Vivacidade, três medições:**

| Data | Câmera | Fotos detectadas como fraude | Resultado |
|---|---|---|---|
| 15/08 | 640×480 | uma foto marcou **40%** | faixas sobrepostas — **uma foto abriu a porta** |
| 15/08 | 1280×720 | 68%, 99%, 100% | faixas separadas |
| 21/09 | recorte 720×960 | 10 fotos: 100,100,100,99,99,98,97,95,77,**75** | **nenhuma passou**, margem de 15 pontos |

Limiar de recusa: **60%**.

A história por trás é o melhor conteúdo da página: **o que consertou não
foi ajustar o limiar, foi resolução.** O modelo julga textura de pele num
recorte de 80×80 pixels; num rosto de 100px não havia textura para ver, e
ele chutava. E a terceira medição veio de um acidente — o cabo da câmera
não caiu na caixa impressa, ela foi parafusada girada 90°, e corrigir isso
em software fez o recorte do rosto crescer **78%**.

**Identidade:**

| | distância |
|---|---|
| duas capturas da mesma pessoa, as mais próximas | 0,033 a 0,230 |
| duas pessoas diferentes, o par mais próximo | 0,374 |
| par legítimo mais distante já medido | **0,520** |

Repare que 0,520 é maior que 0,374: **não existe limiar único que separe.**
O que faz funcionar é guardar até 5 capturas por pessoa e comparar sempre
com a mais próxima delas. Isso é contraintuitivo e é exatamente o tipo de
coisa que impressiona quem entende.

### Funciona sem internet

O banco fica na nuvem, então toda decisão da porta atravessava a internet.
Hoje o servidor mantém uma cópia local e continua decidindo dentro do
prédio.

O detalhe que prova: em 15/08, três leituras decididas offline subiram
sozinhas quando a rede voltou — **com o horário original**:

```
19:20:56    19:21:02    19:21:07
```

A presença gravada é a hora em que a pessoa entrou, não a hora em que a
rede voltou. Esses três horários em mono são um bom elemento gráfico.

### LGPD

Vetor facial é dado pessoal **sensível** (art. 5º, II), e isso exige
consentimento específico e destacado. Antes da primeira foto a pessoa lê e
aceita um termo, e fica registrado quem, quando e **com qual versão do
texto**.

Três decisões que fazem o registro valer:

- A recusa é do **servidor**, não da tela
- A checagem vem **antes** de calcular o vetor — transformar a foto em
  vetor já é tratar o dado
- Revogar é apagar o rosto, mesma ação. Mas o registro antigo **não** é
  apagado: ele é a prova de que o tratamento anterior era legítimo

### As telas do app

**Não tenho screenshots para te dar.** Recomendo reconstruir as telas como
mockups em HTML/CSS usando o sistema de design acima — sai mais consistente
com o resto da página do que captura de tela, e você controla o conteúdo.

As telas que valem mostrar, nesta prioridade:

1. **Frequência do aluno** — "quantas faltas ainda cabem" por disciplina.
   Três alunos em situações diferentes: tranquilo (menta), no limite
   (âmbar), reprovado por falta (coral)
2. **Agora** — a aula em andamento e quem já entrou, com horário de entrada
3. **Cadastro de rosto** — o termo de consentimento aparecendo **antes** da
   câmera, e a lista de capturas sem miniatura
4. **Lista de presença da aula** — com primeira e última leitura

Conteúdo de exemplo (use estes, são coerentes entre si):

```
Samuel Milan de Pontes    6/6    100%   2 faltas restantes
Gabriel Gregorio          4/6     67%   0 faltas restantes
Pedro Leite               3/6     50%   reprovado por falta
```

### Permanência — o diferencial

Como a porta lê o tempo todo, quem entra e sai deixa **duas marcas**:
chegada e saída. Isso vira permanência.

> Presença por assinatura é fácil de burlar. Presença por permanência é bem
> menos.

Mostre visualmente a diferença entre uma leitura (entrou) e duas (entrou e
ficou).

### Exportação

O professor exporta a lista em planilha, e o dado sai do app pro sistema da
faculdade. Duas planilhas: a da aula e a da turma inteira.

Colunas da aula:

```
Nome · Matrícula · Situação · Primeira leitura · Última leitura ·
Permanência · Leituras · Origem
```

Detalhe que vale uma linha de legenda, porque mostra cuidado: o arquivo sai
com BOM e separador `;` **porque o Excel brasileiro exige** — sem isso
"João" abre como "JoÃ£o" e tudo cai numa coluna só.

### O que ainda não funciona — inclua isto

Uma seção de limitações conhecidas. Numa feira isso é incomum e é
exatamente o que faz um professor confiar no resto:

- **A vivacidade encarece a fraude, não elimina.** As 10 medições foram de
  uma pessoa e um tipo de ataque. Máscara e vídeo em alta qualidade não
  foram testados. Garantia exige outro sensor — infravermelho ou
  profundidade — não outro número
- **A primeira captura de cada conta não tem como ser validada.** O
  servidor não tem com o que comparar um rosto que vê pela primeira vez.
  Fecha com aprovação do professor, e foi decidido não construir porque a
  fraude exige a colaboração presencial de quem vai ficar marcado como
  ausente
- **O login ainda depende de internet.** O offline vale pra porta, não pro
  app

---

## 6. Requisitos técnicos

- **Uma página**, funcionando offline depois de carregada. A rede da feira
  não é confiável, e a página não pode depender dela pra funcionar durante
  o dia
- **Sem backend, sem chamada de API.** Todos os dados são fixos no HTML
- **Three.js + STLLoader** (do cdnjs) para a caixa em 3D, com os três STL
  servidos junto da página. Tudo somado são 260 KB de geometria
- **Fallback sem WebGL** para a seção 3D: imagem estática mais o texto dos
  pontos de interesse
- **Fontes do Google Fonts** (Jost e IBM Plex Mono), com fallback de
  sistema caso a rede falhe na hora de abrir
- **Funciona em tela de toque e com mouse.** Alvos de toque grandes — dedo
  de visitante, não cursor
- **Nenhum estado sem volta.** O simulador sempre volta ao repouso sozinho
  depois de alguns segundos, porque quem tocou já foi embora e o próximo
  visitante tem que encontrar a página pronta
- **Responsiva até largura de celular** — alguém vai abrir o link no
  próprio telefone
- Sem analytics, sem cookie, sem banner de consentimento. Numa página sobre
  privacidade, seria irônico

---

## 7. Critério de aceitação

A página está pronta quando:

1. Um visitante entende **o que o projeto faz** em 10 segundos, sem ler
   parágrafo nenhum
2. O **simulador funciona sem instrução** — dá pra ver o que fazer
3. Uma recusa na AULA mostra claramente que o sistema **reconheceu a pessoa
   e ainda assim não abriu**
4. Lado a lado com uma foto da tela do totem, **parece a mesma família
   visual**
5. Toda voz de máquina está em mono e toda voz humana em Jost, sem exceção
6. Depois de 30 segundos sem toque, a página está de volta ao estado
   inicial
7. A caixa em 3D explode e volta, e **pelo menos o ponto de interesse da
   câmera** conta a história do recorte de 78%
8. Sem WebGL, a seção da caixa continua fazendo sentido
9. O canvas 3D não sequestra o scroll da página
10. Nada nela denuncia ter saído de um template
