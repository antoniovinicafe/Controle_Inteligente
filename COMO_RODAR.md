# Como rodar o Fetin inteiro

Manual de operação para o dia: o que ligar, em que ordem, como saber que
cada parte está viva, e o que fazer quando não estiver.

Não é o roteiro da apresentação — esse é o
[ROTEIRO_BANCA.md](ROTEIRO_BANCA.md). Aqui é só pôr o sistema de pé.

---

## O que precisa estar ligado

| Parte | Onde roda | Sem ela |
|---|---|---|
| **Postgres** | Supabase, na nuvem | a porta decide pela cópia local, o app não abre |
| **API Flask** | no seu PC | nada funciona |
| **Totem** | na Raspberry, na porta | sem leitor facial |
| **App** | no celular | não dá pra criar aula nem cadastrar rosto |
| **Página da bancada** | navegador do notebook | perde a parte interativa |

**PC e Raspberry precisam estar na mesma rede.** Não precisa ser a mesma
rede do celular — o celular fala com a API pelo IP, então basta alcançá-la.

---

## Ordem de ligar

A ordem importa: o totem procura a API ao subir, e desiste se não achar.

```
1. rede   →   2. API   →   3. aquecer   →   4. aula   →   5. Raspberry   →   6. celular
```

---

## 1. Rede

Ligue o PC na rede e pegue o IP:

```bash
ipconfig
```

Anote o número do adaptador Wi-Fi. **Ele muda sozinho** — mudou cinco vezes
num único dia de trabalho, e é a causa mais comum de tudo parecer quebrado.

Se a rede do local for desconhecida, vale ligar o **ponto de acesso móvel do
Windows** com o nome e a senha de uma rede que a Raspberry já conhece
(Configurações → Rede e Internet → Ponto de acesso móvel → Editar). Assim
ela entra sozinha, sem teclado, e o PC continua com internet pelo Wi-Fi.

---

## 2. A API

```bash
cd api
venv/Scripts/python app.py
```

Espere a linha:

```
Fetin API em http://0.0.0.0:5000
```

**Deixe essa janela visível.** É nela que saem as leituras:

```
[vivacidade] pessoa (91% de certeza, limiar 60%)
[identidade] bateu 0.101 com Samuel Milan de Pontes (limiar 0.3)
```

### Se aparecer "banco fora de alcance no boot"

```
[db] banco fora de alcance no boot: ... (ENOTFOUND) tenant/user ... not found
[db] servidor subindo assim mesmo - a porta decide pela cópia local
```

**Não é o projeto apagado.** O Supabase hiberna projetos sem uso, e a
primeira tentativa de conexão dá esse erro enquanto ele acorda. Espere um
minuto e confira:

```bash
curl http://127.0.0.1:5000/api/health
```

O servidor se reconecta sozinho — ele foi corrigido para subir sem banco e
tentar de novo, justamente para sobreviver a isso.

### Se aparecer "já tem alguém respondendo na porta 5000"

Tem uma API antiga de pé. Ache e encerre:

```bash
netstat -ano | findstr :5000
```

### Para gravar o log da vivacidade

Quando for medir ou calibrar, suba assim em vez do comando acima:

```bash
venv/Scripts/python -u app.py 2>&1 | Tee-Object -FilePath vivacidade.log
```

O `-u` desliga o buffer, senão as linhas ficam presas e só aparecem no fim.

---

## 3. Aqueça a API

**Não pule este passo.** A primeira requisição depois de subir demora ~30
segundos: o DeepFace baixa e carrega os pesos do Facenet512 e do
anti-spoofing na primeira chamada, não no import.

Dê uma passada de rosto na porta sozinho, antes de qualquer público.

---

## 4. A aula

Sem aula em andamento, **todo rosto reconhecido é negado** com "nenhuma aula
acontecendo agora" — reconhece o nome e não abre. É o jeito mais confuso
possível de falhar.

```bash
cd api
venv/Scripts/python semear_demo.py
```

Cria o histórico de 8 aulas (para as telas de frequência terem o que
mostrar) e **uma aula em andamento de 4 horas**, na sala lida do leitor
cadastrado.

**Se for criar a aula à mão pelo app** na frente de alguém, rode com
`--sem-aula`. Duas aulas em andamento na mesma sala se atrapalham: a porta
fica com a que começou primeiro, que seria a semeada.

```bash
venv/Scripts/python semear_demo.py --sem-aula
```

E aí o campo **local** da aula criada no app tem que ser exatamente a sala
do leitor. Para conferir qual é:

```bash
venv/Scripts/python -c "import psycopg2,psycopg2.extras;from config import Config;c=psycopg2.connect(Config.DATABASE_URL,cursor_factory=psycopg2.extras.RealDictCursor);cur=c.cursor();cur.execute('select nome,local from dispositivos where ativo');print(cur.fetchall())"
```

---

## 5. A Raspberry

O totem **sobe sozinho no boot**. Normalmente é só ligar a Pi e esperar a
tela aparecer.

### Achar a Pi na rede

`controle.local` costuma funcionar, mas **a Pi não responde a ping** nesta
configuração — então `ping` e varredura por ICMP dão vazio mesmo com ela no
ar. Procure pela porta SSH:

```powershell
$r='192.168.66'  # troque pela faixa da sua rede
$t = 1..254 | ForEach-Object { $c = New-Object System.Net.Sockets.TcpClient; [pscustomobject]@{IP="$r.$_"; C=$c; A=$c.BeginConnect("$r.$_",22,$null,$null)} }
Start-Sleep 3
$t | ForEach-Object { if ($_.C.Connected) { $_.IP }; $_.C.Close() }
```

### Entrar

```bash
ssh -4 -i ~/.ssh/fetin_pi controle@<ip>
```

**Os dois flags são obrigatórios.** Sem `-i` a chave certa não é oferecida e
dá `Permission denied`; sem `-4` o Windows resolve para IPv6 link-local e o
SSH morre em `Connection timed out`.

### Conferir o totem

```bash
systemctl --user is-active totem
```

**Se responder `activating`, ele está em loop de reinício.** Isso quase
sempre significa que não achou o servidor: o totem sai quando não acha, e o
systemd sobe de novo a cada 5 segundos. Parece quebrado, mas é o
comportamento certo. Aponte o endereço novo:

```bash
echo 'http://IP_DO_PC:5000/api' > ~/.fetin/api
systemctl --user restart totem
```

### Os ajustes físicos da caixa

Ficam em `~/.config/fetin.env` na Pi. Os valores desta caixa:

```
FETIN_SALA=FETIN
FETIN_ROTACAO=90        # câmera parafusada girada; sem isso o rosto não é detectado
FETIN_MARGEM=0.86       # a moldura impressa cobre a borda da tela
FETIN_DESLOCA_Y=-0.06   # e cobre só embaixo, então o desenho sobe
```

Mudou algum? `systemctl --user restart totem`.

Os três estão documentados em
[`api/raspberry/fetin.env.example`](api/raspberry/fetin.env.example) com o
porquê de cada um.

### Ver o que a Pi está mostrando, sem ir até lá

```bash
ssh -4 -i ~/.ssh/fetin_pi controle@<ip> "XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 grim /tmp/t.png"
scp -4 -i ~/.ssh/fetin_pi controle@<ip>:/tmp/t.png .
```

---

## 6. O celular

App instalado, logado, e **Ajustes → Servidor** apontando para o IP do PC.

Não precisa recompilar quando o IP muda — é exatamente para isso que essa
tela existe. Em instalação limpa o app volta para o padrão de fábrica
(`10.0.2.2`, que é o emulador Android) e não acha nada até você apontar.

Para reinstalar:

```bash
cd app
flutter build apk --release
flutter install --release
```

**O `flutter install` desinstala a versão antiga e apaga os dados** — depois
disso, logar de novo e reapontar o servidor.

---

## 7. A página da bancada

Abra no navegador do notebook e deixe em tela cheia (F11):

```
https://claude.ai/artifact/JhwQqg9MkqiNNgQMnq2VqQ
```

É privada: esse notebook precisa estar logado na conta que a publicou.

Depois de carregada ela funciona sem rede, mas a biblioteca 3D e as fontes
vêm de CDN **no carregamento**. Abra cedo, com internet boa, e **não
recarregue a aba** durante o dia.

---

## Está tudo de pé?

Quatro conferências, meio minuto:

```bash
curl http://127.0.0.1:5000/api/health
```
→ `{"status":"ok"}`

```bash
ssh -4 -i ~/.ssh/fetin_pi controle@<ip> "systemctl --user is-active totem"
```
→ `active` (e não `activating`)

**Olhe a tela da porta** → o preview da câmera aparecendo, com você em pé e
enquadrado.

**Passe o rosto** → LIBERADO, e o nome certo.

---

## Quando quebrar

| Sintoma | Causa provável | Conserto |
|---|---|---|
| "Nenhuma aula acontecendo agora" | não tem aula, ou o local da aula não é a sala do leitor | rode o `semear_demo.py`, ou corrija o campo local no app |
| "Rosto não reconhecido" em quem é cadastrado | enquadramento, luz, ou cadastro antigo demais | passe de novo; se insistir, a pessoa cadastra 2 fotos novas pelo app |
| Recusa por vivacidade em pessoa real | o antifraude sendo conservador | passe de novo, o leitor pergunta a cada 1,2s |
| Tela da porta apagada ou piscando | totem em loop, não achou a API | `~/.fetin/api` com o IP novo, e restart |
| Totem no ar mas nada acontece | a Pi está em outra rede | veja "achar a Pi" |
| Rosto deitado no preview | `FETIN_ROTACAO` errado | 0, 90, 180 ou 270 até ficar em pé |
| Falta pedaço embaixo da tela | a moldura da caixa | baixe o `FETIN_DESLOCA_Y` (mais negativo) |
| App não carrega nada, mas loga | servidor errado em Ajustes | aponte para o IP do PC |
| App nem loga | sem internet | o login é Supabase, na nuvem — não tem modo offline |
| Primeira leitura travou | API não foi aquecida | espere, são os pesos do Facenet512 |
| Mudei o código e não mudou nada | `app.py` não recarrega ao salvar | Ctrl+C e suba de novo |
| A rede do local isola os aparelhos | o Wi-Fi da faculdade faz isso | hotspot do PC ou roteador próprio |

---

## Sem a Raspberry

Dá para demonstrar o caminho inteiro pela webcam do PC — mesmo servidor,
mesmo reconhecimento, mesmo antifraude, mesmas cinco checagens. Muda só de
onde vem a imagem:

```bash
cd api
venv/Scripts/python simular_dispositivo.py --chave <CHAVE> --webcam
```

---

## Sem internet nenhuma

A porta continua funcionando pela cópia local, e o que for decidido offline
sobe sozinho quando a rede voltar, com o horário original de cada leitura.

O que **não** funciona sem internet: entrar no aplicativo. O login é do
Supabase Auth, na nuvem. Se for apresentar com a rede caída, **deixe o app
já logado** antes.
