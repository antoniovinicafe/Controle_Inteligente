# Roteiro da banca — 90%

Do zero: o que abrir, o que subir, o que fazer na frente do orientador e o
que falar em cada parte.

O fluxo escolhido é o mais forte que o sistema tem, porque ele fecha o
ciclo inteiro ao vivo: **uma pessoa se cadastra na frente do orientador, o
professor cria a aula, e essa mesma pessoa entra pela porta minutos
depois.** Nada de tela pronta, nada de "aqui já estava configurado".

Isso também é o que o torna arriscado. Duas coisas nesse caminho nunca
rodaram num aparelho, e a Parte 0 existe por causa delas. **Não pule.**

---

## As três coisas que quebram a demonstração

Leia antes de qualquer outra coisa. Todas as três já aconteceram aqui.

| | |
|---|---|
| **A aula tem que ser na sala `FETIN`** | O campo "local" é texto livre. A porta procura aula **pela sala do leitor**, e o leitor está cadastrado como `FETIN`. Aula em "Sala 201", "Quadra" ou vazio = todo mundo negado, com o rosto reconhecido e tudo certo |
| **Quem se cadastrar ao vivo precisa de 3+ capturas** | Com uma foto só a porta pode não reconhecer. Os números estão na Parte 0 |
| **O termo de consentimento nunca rodou num celular** | Ele **bloqueia** o cadastro de rosto. Se travar, trava exatamente o Ato 3 |

---

## Parte 0 — Ensaio, antes do orientador chegar

Reserve 20 minutos. Você vai **fazer a demonstração inteira sozinho**, na
ordem, e só depois desfazer pra repetir ao vivo.

Por que isso não é paranoia: o Ato 3 apaga as 5 capturas do Samuel, que
foram tiradas dia 13/08 e estão medidas e funcionando. Se o cadastro novo
der errado na frente do orientador, você não tem pra onde voltar. O ensaio
prova o caminho **antes** de destruir o que funciona.

1. Suba tudo (Parte 1).
2. Samuel apaga o próprio rosto no app e cadastra **3 capturas** de novo.
3. Samuel vai até a porta e passa. **Liberou?** Então o caminho está provado.
4. Apaga de novo e deixa pronto pro ao vivo.

**Se no passo 3 der "Rosto não reconhecido"**, é o risco previsto — pule pra
"Plano B" no fim deste arquivo antes de continuar.

### Por que 3 capturas, e não 1

Medido agora (`venv/Scripts/python medir_rostos.py`), 11 capturas de 3
pessoas:

| | distância |
|---|---|
| duas pessoas diferentes, par mais próximo | **0,374** (folga de só +0,074 sobre o limiar) |
| cada captura e a irmã mais próxima | 0,033 a 0,230 |

As 5 capturas do Samuel são todas de uma sessão só, 13/08 entre 18:04 e
18:06 — mesma luz, mesmo ângulo, mesma lente. É por isso que ele é
reconhecido com folga hoje.

Um cadastro novo feito ao vivo pela câmera do **celular**, seguido de uma
leitura pela câmera da **Raspberry**, é justamente o caso em que a distância
sobe: lente diferente, luz diferente. Com uma captura só não há de onde a
busca escolher — ela compara com aquela e pronto. Com três, ela compara com
a mais próxima das três, que é o mecanismo que faz o limiar de 0,30
funcionar.

**Na hora de tirar as 3, varie de propósito:** uma de frente, uma levemente
de lado, uma com a luz do outro lado. Fotos idênticas não ajudam em nada.

---

## Parte 1 — Subir tudo, do zero

Nesta ordem. Cada passo tem como saber que deu certo.

### 1. Rede

PC, Raspberry e celular no mesmo Wi-Fi. Pegue o IP do PC:

```bash
ipconfig
```

Guarde esse número. Ele muda sozinho e é a causa mais comum de tudo parecer
quebrado — já mudou de `.53` pra `.88` entre uma sessão e outra.

### 2. A API, no PC

```bash
cd api; venv/Scripts/python app.py
```

Espere `Serving on http://...:5000`.

**Deixe esta janela visível durante a banca inteira.** É nela que sai:

```
[vivacidade] pessoa (91% de certeza, limiar 60%)
[identidade] bateu 0.101 com Antonio Teste (limiar 0.3)
```

Mostrar esse log ao vivo vale mais que qualquer slide — é a prova de que
tem número por trás da decisão, não mágica.

### 3. Aqueça a API

A primeira requisição depois de subir demora ~30 segundos: o DeepFace
carrega os pesos do Facenet512 e do anti-spoofing na primeira chamada, não
no import. **Não deixe isso acontecer na frente do orientador.** Dê uma
passada de rosto na porta agora, sozinho.

### 4. Popule o banco

```bash
cd api; venv/Scripts/python semear_demo.py --sem-aula
```

Cria 8 aulas de histórico (6 encerradas, 2 futuras) — é o que faz as telas
de frequência terem o que mostrar.

**O `--sem-aula` é obrigatório neste roteiro.** Sem ele o script também cria
uma aula em andamento, e aí ficariam **duas aulas simultâneas na mesma
sala**: a semeada e a que o Antonio vai criar ao vivo no Ato 4. A porta
procura "aula acontecendo agora aqui" e fica com a que começou primeiro — a
semeada. O orientador veria o Samuel entrando numa aula que não é a que ele
acabou de ver nascer, e a tela **Agora** aberta na aula nova não mexeria.

No **ensaio** (Parte 0) rode sem o `--sem-aula`: aí a aula já vem pronta e
você testa a porta sem depender do app.

### 5. O totem da porta

Sobe sozinho no boot da Raspberry. Confira:

```bash
ssh -4 -i ~/.ssh/fetin_pi controle@controle.local "systemctl --user is-active totem"
```

**Se responder `activating` ou o totem não aparecer:** ele está em loop de
crash, e a causa quase sempre é não achar o servidor. Ele sai quando não
acha, e o systemd tenta de novo a cada 5s — parece quebrado, mas é o
comportamento certo. Corrija apontando o endereço novo:

```bash
ssh -4 -i ~/.ssh/fetin_pi controle@controle.local "echo 'http://SEU_IP:5000/api' > ~/.fetin/api; systemctl --user restart totem"
```

### 6. O celular

App instalado (build da véspera), logado, e **Ajustes → Servidor** apontando
pro IP do PC. Não precisa recompilar quando o IP muda — é pra isso que essa
tela existe.

### 7. Passada de teste com a sala vazia

Se liberar, está pronto.

---

## Parte 2 — A demonstração

### Ato 1 — O problema (30 segundos, sem tela)

> "Chamada em aula é uma lista passando de mão em mão e assinatura de quem
> não veio. O que a gente fez foi tirar a chamada da mão do professor e
> botar na porta: quem entra na sala está presente, e ninguém precisa fazer
> nada."

Não abra nada ainda. Deixe a pergunta no ar.

### Ato 2 — Apagar o rosto (e isso é uma funcionalidade, não uma preparação)

Celular **na conta do Samuel**. Tela **Cadastro facial** → **Remover todas**.

Não trate isso como setup. É o Ato mais fácil de desperdiçar:

> "Antes de cadastrar, olha o que acontece quando alguém quer sair. Isso
> aqui é a revogação do consentimento, e é a mesma ação que apagar o rosto —
> de propósito. Dois botões separados criariam um estado impossível:
> consentido sem rosto, ou rosto sem consentimento.
>
> O que **não** é apagado é o registro de que ele consentiu um dia. Esse
> registro é a prova de que o tratamento anterior era legítimo — sumir com
> ele junto com o dado seria destruir a própria defesa."

### Ato 3 — Cadastrar ao vivo (consentimento + capturas)

Ainda na conta do Samuel: **Cadastrar meu rosto**.

**O termo aparece antes da câmera.** Deixe o orientador ler.

> "Vetor facial é dado pessoal **sensível** pela LGPD, artigo 5º, inciso II.
> Tratar dado sensível exige consentimento específico e destacado — o
> consentimento genérico de usar o app não serve, e 'a pessoa apertou o
> botão de cadastrar rosto' também não.
>
> Três decisões fazem esse registro valer alguma coisa. A recusa é do
> **servidor**, não da tela: se quem decidisse fosse o app, um APK antigo —
> ou qualquer coisa que saiba fazer um POST — gravaria biometria sem
> consentimento nenhum. A checagem vem **antes** de calcular o vetor, porque
> transformar a foto em vetor já é tratar o dado; checar depois seria
> processar primeiro e pedir licença depois. E o texto vem do servidor, não
> embutido no app, senão a pessoa concordaria com uma coisa e o banco
> guardaria outra."

**Concordo** → câmera. Tire **3 fotos**, variando ângulo e luz.

> "Não tem opção de galeria, e isso é uma decisão de segurança: o
> anti-spoofing reconhece foto de tela, mas não distingue uma selfie digital
> normal da selfie de outra pessoa. Qualquer imagem salva no celular
> serviria."

Mostre a lista de capturas.

> "Repare que não tem miniatura. Não tem porque **não existe imagem** — o
> servidor extrai o vetor de 512 números e descarta a foto. Nem aqui, nem no
> leitor da porta.
>
> O que permite escolher qual apagar é esse aviso, 'não parece as suas outras
> fotos', calculado no servidor pelo mesmo critério que recusaria uma captura
> nova. Sem ele seriam três linhas idênticas com horários diferentes."

**Se quiser fechar a explicação com o número**, aponte o console: a captura
acabou de gerar um vetor, e a distância dele pras irmãs é o que aparece na
lista.

### Ato 4 — Trocar de conta: o professor monta a aula

**Sair** → entrar como **Antonio Teste** (professor).

**4a. Criar a turma.** Turmas → nova turma → adicionar o Samuel como aluno.

> "O professor cria a turma uma vez. Os alunos ficam ligados a ela, e é isso
> que faz a frequência ser por disciplina mais pra frente."

**4b. Criar a aula.** Novo evento:

- **Local: `FETIN`** ← **este campo decide se a demonstração funciona**
- Horário: começando agora, terminando daqui a algumas horas
- Depois de criar: **convidar a turma**

> "O campo de local não é decoração. A porta procura a aula pelo local, e o
> leitor daquela sala sabe qual é a dele. Aula sem local preenchido não
> libera ninguém — o app até avisa isso na tela."

### Ato 5 — "Como essa aula chega na Raspberry?"

**Pare aqui e explique antes de ir pra porta.** É a pergunta que o
orientador vai fazer, e a resposta é melhor do que ele espera:

> "Nada foi enviado pra Raspberry. Ela não sabe que essa aula existe, e não
> precisa saber.
>
> A Pi é burra de propósito: ela só tira foto e pergunta 'pode entrar?'. Todo
> o reconhecimento e toda a regra ficam no servidor. Quando alguém chega, o
> servidor é que pergunta: tem aula acontecendo agora **na sala deste
> leitor**? Quem é esse leitor, ele mesmo diz — autentica com uma chave
> própria, e é a chave que diz de qual sala ele é.
>
> Por isso a aula que eu acabei de criar já vale. Não tem sincronização, não
> tem espera, não tem nada instalado lá. E é também por isso que a Pi não
> precisa de TensorFlow: se a gente trocar o modelo de reconhecimento
> amanhã, não se mexe em nenhum hardware."

### Ato 6 — A porta liberando (o momento)

Vá até a porta com o celular na tela **Agora**, aberto na aula que acabou de
criar. **Samuel passa o rosto** — o mesmo rosto cadastrado há cinco minutos.

Sequência: preview duotone procurando → **LIBERADO** com o nome → e o
celular, que relê de 10 em 10 segundos, mostra ele entrando na lista.

> "Entre a câmera e essa tela aconteceram cinco checagens em ordem, e basta
> uma falhar pra negar: tem rosto? é gente de verdade ou uma foto? esse rosto
> bate com alguém cadastrado? tem aula agora nesta sala? essa pessoa foi
> convidada?"

**Aponte o console** e leia a linha em voz alta:

```
[identidade] bateu 0.101 com Samuel Milan de Pontes (limiar 0.3)
```

> "Reconhecimento aqui não é comparar imagens. A foto vira um vetor de 512
> números pelo Facenet512, e o que se compara é a distância entre vetores.
> Esse número é a distância que deu; 0,30 é o limite."

### Ato 7 — A porta negando (onde está a engenharia)

A porta liberando é o que todo mundo espera. A porta negando é o que dá
trabalho.

**7a. A foto no celular.** Levante uma foto do Samuel na frente da câmera. →
**NEGADO**.

> "É a checagem de vivacidade, e ela é o ponto de equilíbrio do sistema
> inteiro. O modelo devolve o quanto acha que aquilo é papel, pele ou tela, e
> a gente nega quando ele passa de 60% de certeza de fraude."

**Conte a história — é o que interessa numa banca:**

> "Esse 0,60 não foi escolhido, foi medido, e na primeira vez a gente errou.
> Com a câmera em 640x480, uma pessoa de verdade foi acusada de ser foto a
> 77%, 82% e 86% — e uma foto marcou 40%. As faixas se sobrepunham:
> **nenhum limiar separava**. Foi assim que uma foto abriu a porta num teste
> dia 15.
>
> O conserto não foi mexer no limiar, foi **subir a resolução pra 720p**. O
> anti-spoofing julga textura de pele num recorte de 80×80 pixels; num rosto
> de 100 pixels não havia textura pra ver, e ele chutava. A lição é que o
> reconhecimento se contenta com pouca resolução, mas a vivacidade não."

**7b. Reconhecido e ainda assim negado.** Alguém com rosto no banco mas fora
da lista da aula — o Gabriel serve. → **NEGADO**, com o nome na tela.

> "Repare: ele foi **reconhecido** e ainda assim negado. Reconhecer não é
> autorizar. A porta sabe quem é, e sabe que essa pessoa não tem aula aqui
> agora."

Essa é a mais sutil das cinco checagens e a que mais convence, porque prova
que não é um classificador de rosto com uma fechadura pendurada.

### Ato 8 — Sem internet (a carta mais forte)

**Desligue a internet do PC** — só a internet; a rede local com a Raspberry
continua. Samuel passa de novo.

> "O banco fica na AWS em São Paulo, então toda decisão da porta é uma
> consulta que atravessa a internet. Se a rede do prédio cai, cai o sistema
> inteiro — era a limitação principal do projeto.
>
> Agora o servidor mantém uma cópia local dos rostos, das aulas da janela e
> dos leitores, e responde às mesmas três perguntas sem sair do prédio."

Religue e passe de novo.

> "E o que foi decidido offline sobe sozinho na primeira leitura em que a rede
> voltar — **com o horário original**. Dia 15 três leituras foram gravadas
> 19:20:56, 19:21:02 e 19:21:07, não com a hora em que a rede voltou. A
> presença gravada é a da porta, não a do envio."

**O defeito que esse teste revelou** — bancas gostam disso:

> "Esse teste achou um bug que só aparece assim: o servidor não **subia** sem
> banco, porque o pool abria uma conexão no boot. Ou seja, o modo offline só
> salvava se o processo já estivesse de pé — uma queda de luz mataria
> justamente o que existe pra sobreviver a ela."

### Ato 9 — Para que serve tudo isso (a frequência)

Volte pro app na conta do professor: **Turmas → Fetin → frequência**. Depois
mostre a tela do aluno.

> "Tudo isso existe pra chegar aqui. Frequência é por disciplina, e o sistema
> diz quantas faltas **ainda cabem** em cada uma. 75% é por matéria — somar
> todas dá um número que não decide nada: 80% no agregado esconde 50% numa
> delas."

Mostre os três alunos em situações diferentes de propósito: um tranquilo, um
no limite, um reprovado por falta. E a **permanência** — o aluno com duas
leituras na mesma aula, uma na chegada e uma perto do fim.

> "Duas leituras na mesma aula viram permanência: a pessoa não só entrou,
> ficou. Presença por chegada é fácil de burlar; presença por permanência é
> bem menos."

---

## Os 10% que faltam — diga você, antes de perguntarem

Banca de 90% pergunta o que falta. Chegar com a lista pronta muda o tom da
conversa inteira: deixa de ser arguição e vira conversa técnica.

1. **A vivacidade encarece a fraude, não elimina.** Com esta câmera as duas
   faixas ainda se sobrepõem: dia 16 uma pessoa presente foi acusada de foto
   a 96%, e fotos já marcaram 68%. Não existe configuração que dê ao mesmo
   tempo entrada instantânea e recusa garantida — é **escolha, não
   afinação**, e o projeto escolheu segurança. Quem precisar de garantia
   precisa de outro sensor (infravermelho ou profundidade), não de outro
   número.
2. **A primeira captura de cada conta.** Dá pra cadastrar o rosto de um
   colega que nunca se cadastrou e receber a presença dele. Nenhuma barreira
   pega: a vivacidade confirma que é gente presente, e é; "um rosto pertence
   a uma conta só" compara com quem **já está** cadastrado, e ele não está; e
   a regra de parecer com as outras fotos não tem com o que comparar na
   primeira. Não há solução puramente técnica — o servidor não tem como saber
   de quem é um rosto que vê pela primeira vez. Fecha com aprovação do
   professor na primeira foto, e foi decidido não construir porque a fraude
   exige a colaboração presencial de quem vai ficar marcado como ausente.
3. **A margem entre pessoas diferentes está encolhendo** conforme o banco
   cresce: 0,796 com 3 capturas, 0,623 com 7, **0,374 agora com 11**. Ainda
   sobra folga sobre 0,30, mas são 3 pessoas. Em escala real isso precisa ser
   remedido, e é pra isso que o `medir_rostos.py` existe.
4. **O login ainda exige internet** (Supabase Auth). O offline vale pra
   porta, não pra entrar no app.
5. **A rede caindo no meio de uma escrita** não foi testada — o teste foi com
   o banco já fora de alcance, não caindo durante.
6. **Luz na porta.** Metade dos problemas de leitura é iluminação.

---

## Perguntas prováveis, respostas curtas

**"Por que 0,30?"** — Medido. Duas capturas da mesma pessoa ficam a 0,033–
0,230 de alguma irmã; duas pessoas diferentes, a partir de 0,374. Mas já
houve par legítimo a 0,520, ou seja, **não existe limiar único que separe**.
O que faz funcionar é guardar até 5 capturas por pessoa e comparar sempre com
a mais próxima delas. Com uma foto só por pessoa, a porta barraria quem tem
direito — é literalmente por isso que o cadastro de hoje teve três.

**"Por que a Raspberry não faz o reconhecimento?"** — Ela é burra de
propósito: tira foto e pergunta. Todo o DeepFace e toda a regra de negócio
ficam no servidor. O Pi não precisa de TensorFlow, e trocar o modelo não
exige mexer em hardware nenhum.

**"E se roubarem a Raspberry?"** — Ela não tem rosto nenhum nem senha de
banco. Autentica por uma chave própria no header, e o banco guarda só o hash.
A chave também é o que diz de qual sala aquele leitor é.

**"E se cadastrarem a mesma pessoa em duas contas?"** — O servidor recusa: um
rosto pertence a uma conta só. Sem isso dava pra registrar o rosto de um
colega e receber a presença dele — uma fraude que não aparece no log, só o
nome vem trocado.

**"Por que não usa o Realtime do Supabase?"** — Exigiria abrir a Data API pro
cliente, e hoje o Row Level Security nega tudo justamente pra obrigar todo
acesso a passar pelo servidor. A tela relê de 10 em 10 segundos.

**"Onde ficam as fotos?"** — Em lugar nenhum. Vira vetor e a imagem é
descartada, no servidor e no leitor. É por isso que a lista de capturas não
tem miniatura.

---

## Plano B

| Se acontecer | Faça |
|---|---|
| **"Rosto não reconhecido" no Samuel recém-cadastrado** | O risco previsto. Ele tira **mais duas capturas** ali mesmo, no app, e passa de novo. E aproveite: "é exatamente o que eu falei do limiar — com poucas capturas a busca não tem de onde escolher". Vira demonstração do problema, não falha |
| **Se continuar não reconhecendo** | Passe o **Antonio** (5 capturas, medido, funciona). O ciclo já foi mostrado; a porta continua provada |
| **O termo de consentimento trava** | Não insista na frente do orientador. Explique a regra pelo servidor (403 antes do embedding) e siga com uma conta que já tem rosto |
| **Porta nega uma pessoa de verdade** | Passe de novo — o leitor pergunta a cada 1,2s. E aproveite: "é a vivacidade sendo conservadora, e é a troca que a gente escolheu" |
| **"Nenhuma aula acontecendo agora"** | O local da aula não é `FETIN`. Edite a aula no app e corrija o campo |
| **Totem não sobe / travado** | `systemctl --user restart totem`. Se persistir, é o endereço do servidor: `echo 'http://SEU_IP:5000/api' > ~/.fetin/api` |
| **Sem Raspberry** | `venv/Scripts/python simular_dispositivo.py --chave <CHAVE> --webcam` — mesmo caminho, câmera do PC |
| **Rede da faculdade isola os aparelhos** | Roteador próprio ou hotspot do celular. **Teste antes** |
| **Primeira requisição travou** | Não aqueceu. Fale enquanto carrega: são os pesos do Facenet512 |

---

## Uma frase pra fechar

> "O que a gente entregou não é um reconhecedor de rosto — isso é uma
> biblioteca que se baixa. É uma porta que decide, que continua decidindo sem
> internet, que sabe o que pode e o que não pode guardar sobre uma pessoa, e
> que a gente sabe exatamente onde ainda quebra."
