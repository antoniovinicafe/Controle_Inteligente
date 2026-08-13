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
| [`app/`](app/) | Aplicativo Flutter. Professor cria turmas e aulas e acompanha quem entrou; aluno vê suas aulas e sua presença. |
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
convicto: `ANTISPOOF_LIMIAR` no `.env` da API, 0.75 por padrão. Baixar
aperta, subir afrouxa. Medido na porta em 13/08/2026: pessoa presente
99–100%, foto erguida 99% — sobra bastante espaço dos dois lados da linha.
Toda leitura sai no console do servidor (`[vivacidade] pessoa (99% de
certeza, limiar 75%)`), então recalibrar é olhar os números, não chutar.

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
com o que se comparar.

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

Em 13/08/2026 a **vivacidade** foi medida na porta pela primeira vez, com
a câmera da Raspberry: pessoa presente saiu entre 99% e 100% de certeza de
"real", e uma foto erguida na frente da câmera foi negada com 99% de
certeza de "falso". Contra um limiar de 75%, os dois lados ficam longe da
linha — não é um empate resolvido por pouco.

No mesmo dia o totem passou a se encaixar em qualquer resolução, e isso
foi conferido rodando no mini monitor de 7" da porta: o layout continua
desenhado em 1080p e é ajustado à tela real na hora de exibir.

O que falta:

- **Sem internet, nada funciona.** O desenho parece local — a Raspberry
  fala com o Flask no PC, os dois na mesma rede — mas o Flask guarda tudo
  no Postgres do Supabase, que fica na AWS em São Paulo. Toda decisão da
  porta é uma consulta que atravessa a internet, e o login é no Supabase
  Auth. Cair a rede do prédio derruba o sistema inteiro, não só o app.
  A saída é a Pi manter uma cópia local dos rostos e dos convites do dia e
  sincronizar quando a rede volta; é o item grande ainda não começado.
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

- **Não dá pra apagar UMA captura.** O `DELETE /faces` apaga todas as da
  pessoa — não existe rota nem botão pra remover uma só. Depois de 13/08 o
  cadastro barra na entrada a captura que não parece o rosto de quem a
  envia (ver "O que impede a burla"), então o caso que motivou isto não
  deve se repetir; mas se entrar alguma por outro motivo, a única saída
  continua sendo apagar todas e cadastrar de novo.
