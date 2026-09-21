# Handoff — slides para o pitch do Fetin (5 minutos)

Briefing para produzir o deck. Tudo que você precisa saber está aqui: o
projeto, o contexto da apresentação, a identidade visual que já existe, e o
conteúdo exato de cada slide.

---

## 1. O que é o projeto

**Fetin** é um sistema de controle de acesso por reconhecimento facial que
registra presença em aula automaticamente. Projeto de engenharia do Inatel.

A pessoa chega na porta da sala, uma câmera a reconhece, e a presença é
gravada sozinha — sem lista de chamada, sem crachá, sem ninguém fazer nada.

São três partes:

- **Um leitor na porta** — Raspberry Pi com câmera e uma tela em modo totem
  que mostra LIBERADO ou NEGADO
- **Um servidor** — onde está toda a inteligência: reconhecimento facial,
  detecção de fraude e as regras de quem pode entrar onde
- **Um aplicativo** — professor cria as aulas e acompanha quem entrou; aluno
  cadastra o próprio rosto e vê quantas faltas ainda cabem em cada matéria

O reconhecimento transforma o rosto em uma lista de 512 números e compara
distâncias. **A imagem nunca é armazenada** — nem no servidor, nem na porta.

---

## 2. Contexto da apresentação — leia isto antes de desenhar

| | |
|---|---|
| **Formato** | 5 minutos de pitch + 10 minutos de arguição |
| **Público** | Banca acadêmica de engenharia. Orientador e avaliadores técnicos |
| **Onde** | Presencial, ao lado da porta com o equipamento montado e funcionando |
| **Objetivo** | Avaliação de 90% do projeto. Eles querem ver rigor técnico e consciência dos próprios limites |

### A restrição que governa todo o design

**A apresentação é uma demonstração ao vivo.** Durante quase todos os 5
minutos, uma pessoa está se cadastrando num celular, andando até a porta e
passando o rosto numa câmera. A banca vai estar **olhando para a porta, não
para o slide**.

Isso muda tudo:

> **Os slides são cenário, não conteúdo.** Eles existem para dar título ao
> que está acontecendo e para segurar a ideia no ar depois que ela é dita.
> Ninguém vai ler texto durante a demonstração.

Consequências diretas, e são obrigatórias:

- **Uma ideia por slide.** Nunca duas.
- **Tipografia enorme.** Um slide precisa ser lido em 1,5 segundo, de pé, a
  seis metros, com a luz acesa.
- **Nenhuma lista com marcadores.** Nenhuma. Em nenhum slide.
- **Máximo de 12 palavras por slide**, salvo os dois slides marcados abaixo
  como exceção.
- Vários slides serão exibidos por 20 ou 30 segundos com o apresentador de
  costas para eles. Precisam funcionar como pôster, não como documento.

---

## 3. Identidade visual — já existe, use-a

Este é o ponto mais importante para o deck ficar bom em vez de genérico.

**A tela do totem na porta vai estar ligada, ao lado da projeção, durante a
apresentação inteira.** O deck precisa parecer a mesma coisa que aquela
tela. Quando a banca olhar do slide para a porta, tem que ser um sistema só.

### Paleta (extraída direto do código do totem)

```
#0C1A1E   fundo         petróleo tão escuro que lê como preto
#14282E   superfície    para blocos elevados sobre o fundo
#15616D   petróleo      cor de marca, estrutura, linhas, detalhes
#35D6A0   menta         LIBERADO, acerto, confirmação
#F0655A   coral         NEGADO, recusa, alerta
#E8F1F2   texto         quase branco, levemente frio
#6E8F98   apagado       texto secundário, rótulos, legendas
```

**Fundo escuro sempre.** Não existe versão clara deste deck. O totem é
escuro, a sala provavelmente terá luz baixa, e menta e coral só têm a força
que precisam ter sobre fundo escuro.

Use **menta e coral com parcimônia e significado**: menta só quando o
assunto é acesso concedido, coral só quando é recusa. Elas são vocabulário,
não decoração. Um slide com as duas ao mesmo tempo perde as duas.

### Tipografia

O sistema tem duas vozes, e o deck deve manter isso:

- **Display** — uma gótica/grotesca condensada e pesada, para os números e
  as palavras-chave (LIBERADO, NEGADO, 0,30). No totem é URW Gothic Demi;
  qualquer grotesca de peso alto com personalidade serve, desde que não seja
  neutra.
- **Texto** — uma sans humanista para as frases. No totem é Nunito Sans.
- **Dados** — uma monoespaçada para números medidos, distâncias, e qualquer
  coisa que represente leitura de instrumento. No totem é DejaVu Sans Mono.

A monoespaçada é o detalhe que faz esse deck parecer de engenharia e não de
startup. Use-a em todo número medido.

### Direção estética

O projeto é um **instrumento de medição**, não um produto de consumo. A
referência certa é painel de controle, leitura de sensor, régua — não
landing page de SaaS.

**Não faça:**

- Gradientes suaves, glassmorphism, cantos muito arredondados
- Ícones genéricos de biblioteca (cadeado, rosto poligonal com linhas, nuvem)
- Ilustrações de pessoas em estilo corporativo
- Fotos de banco de imagem de gente sorrindo em escritório
- Numeração decorativa 01 / 02 / 03 em coisa que não é sequência
- Aquele visual creme com serifa de alto contraste e detalhe terracota que
  aparece em todo deck gerado por IA

**Faça:** hierarquia dura, muito espaço vazio, alinhamento rígido, um único
elemento dominante por slide. Se um slide parece vazio demais, provavelmente
está certo.

---

## 4. Os slides

**11 slides.** O tempo indicado é quanto cada um fica no ar. As marcações de
*[ação]* dizem o que está acontecendo na sala — use isso para calibrar o
peso visual: quando há ação, o slide recua.

---

### Slide 1 — Abertura · 25s

Texto único, ocupando o slide:

> **A lista de chamada é o documento mais falsificado desta universidade.**

Nada além disso. Sem logo, sem subtítulo, sem nome de equipe. É a frase que
abre a boca da banca.

---

### Slide 2 — Identificação · fica no ar durante o cadastro ao vivo (45s)

*[ação: uma pessoa está se cadastrando no celular. Ninguém olha o slide.]*

Este slide precisa **não competir**. É o mais quieto do deck.

> **FETIN**
> Controle de acesso e presença por reconhecimento facial
>
> `Inatel` · nomes da equipe

Se quiser um elemento gráfico no deck inteiro, é aqui — algo estrutural e
discreto: uma marcação de enquadramento, quatro cantos como o visor da
câmera do totem. Nada de ilustração.

---

### Slide 3 — A ideia central · 35s

*[ação: a pessoa recém-cadastrada foi até a porta e foi NEGADA, com o nome
dela aparecendo na tela.]*

Este é um dos dois slides mais importantes do deck.

> **Reconhecer não é autorizar.**

Sozinho, imenso, centralizado. Se quiser um apoio mínimo abaixo, em texto
apagado e pequeno:

> `identidade confirmada · acesso negado`

O contraste conceitual pode ser sugerido com as duas cores em elementos
mínimos — mas resista a desenhar um diagrama. A frase é o slide.

---

### Slide 4 — Como o reconhecimento funciona · 25s

*[ação: a pessoa foi autorizada pelo professor e entrou. LIBERADO na porta.]*

Uma linha de raciocínio, com o número em destaque:

> Um rosto vira **512 números**.
> Reconhecer é medir a distância entre dois pontos.
>
> `bateu 0,12` · `limite 0,30`

Os dois valores em monoespaçada, como leitura de instrumento. O `0,12` em
menta — foi um acesso concedido.

---

### Slide 5 — Antifraude · 25s

*[ação: alguém levanta uma foto impressa na frente da câmera. NEGADO.]*

> **Foto não abre.**
>
> Um modelo lê textura de pele e reflexo,
> e separa gente de papel e de tela.

Coral. É o slide mais agressivo do deck e pode ser o mais gráfico — mas sem
ícone de proibido.

---

### Slide 6 — Para que serve · 30s

*[ação: o celular é erguido mostrando a tela de frequência do aluno.]*

O slide que faz a banca entender por que isso importa:

> O aluno não vê "presente".
> Vê **quantas faltas ainda cabem**.

Se quiser um segundo tempo, em texto menor e apagado:

> `Um número em que dá pra agir em março — não a descoberta em julho.`

---

### Slide 7 — Rigor · 20s

Primeiro dos três fechos. Todos os três seguem exatamente o mesmo layout,
mudando só o texto — a repetição formal é o efeito.

> **Nenhum número foi escolhido.**
> Todos foram medidos.

---

### Slide 8 — Resiliência · 20s

Mesmo layout do 7.

> **Funciona sem internet.**
> E a presença guarda a hora em que a pessoa entrou —
> não a hora em que a rede voltou.

*(Exceção autorizada ao limite de 12 palavras. A segunda linha pode ir em
corpo menor e apagado.)*

---

### Slide 9 — Escala e privacidade · 20s

Mesmo layout do 7 e 8.

> **Ninguém precisa de um posto de cadastro.**
> A pessoa entrou no sistema em quatro minutos, sozinha.

---

### Slide 10 — O fecho · 25s

O segundo slide mais importante. Deve ser o mais bonito do deck.

> Uma porta que decide sozinha.
> Que continua decidindo quando a internet cai.
> Que sabe o que pode guardar sobre uma pessoa.
>
> **E que a gente sabe exatamente onde ainda quebra.**

As três primeiras linhas em peso normal, a última em display, grande. É o
clímax — a construção depende do contraste entre as três e a quarta.

*(Exceção autorizada ao limite de palavras.)*

---

### Slide 11 — Slide de espera para a arguição

Fica no ar durante os 10 minutos de perguntas. Vai ser visto por muito mais
tempo que qualquer outro — precisa aguentar o olhar.

> **FETIN**
>
> `medições · modo offline · LGPD · limitações conhecidas`

A linha de baixo em monoespaçada apagada, funcionando como um menu discreto
do que a banca pode pedir. Não é um índice numerado — é um convite.

---

## 5. Entrega

- **Proporção 16:9**, projetor.
- **Contraste alto de verdade.** Projetor de sala de aula lava as cores; o
  que parece bom no monitor pode sumir na parede. Texto secundário nunca
  abaixo de `#6E8F98` sobre o fundo escuro.
- **Nada de animação de transição elaborada.** O apresentador vai avançar
  slide enquanto anda e fala. Corte seco ou fade curto.
- **Nenhum slide com número de página**, exceto se for discretíssimo.
- Se houver espaço para uma única assinatura visual recorrente no deck, que
  seja **a marcação de enquadramento de câmera** (quatro cantos), que é o
  elemento que já existe na tela do totem.

---

## 6. Critério de aceitação

O deck está pronto quando:

1. Cada slide é legível em **1,5 segundo**, a seis metros.
2. Nenhum slide tem lista com marcadores.
3. Colocado lado a lado com uma foto da tela do totem, **parece a mesma
   família visual**.
4. Os slides 3 e 10 dão vontade de fotografar.
5. Nada nele denuncia ter sido feito a partir de um template.
