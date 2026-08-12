# Testar cadastro facial num celular físico

O emulador nunca conseguiu gravar um rosto de verdade (câmera falsa, sem
rosto → o backend responde 422 "nenhum rosto detectado"). A tabela `faces`
está com **0 linhas**, ou seja, o núcleo do projeto nunca rodou de ponta a
ponta. Este guia é pra fechar esse buraco.

## O que já está pronto

- `AndroidManifest.xml` já tem `CAMERA`, `INTERNET` e `usesCleartextTraffic="true"`
  (esse último é obrigatório: sem ele o Android 9+ bloqueia HTTP puro).
- O Flask já sobe em `0.0.0.0`, então aceita conexão de fora da máquina.
- APK já buildado e apontando pro IP da máquina: **`fetin-celular.apk`** (53 MB).

## Passo 0 — ligar o RLS (faça isso antes de instalar em celular)

Hoje qualquer pessoa com a anon key (que sai do APK com um `unzip`) lê e
escreve o banco inteiro direto, sem login, passando por cima do Flask.
Colocar o app num aparelho que sai de casa antes de fechar isso amplia o
risco à toa.

Rode no **SQL Editor do Supabase** (Dashboard > SQL Editor):

```sql
alter table profiles enable row level security;
alter table eventos enable row level security;
alter table turmas enable row level security;
alter table turma_alunos enable row level security;
alter table evento_participantes enable row level security;
alter table faces enable row level security;
alter table access_logs enable row level security;
alter table recorrencias enable row level security;
```

Não precisa criar policy nenhuma: sem policy, o anon fica sem acesso a nada.
O Flask continua funcionando 100%, porque conecta como `postgres`, que tem
`rolbypassrls = true`.

Depois de rodar, confira que o app continua normal (login, listar eventos,
criar) — se algo quebrar, `alter table X disable row level security` desfaz.

## Passo 1 — liberar a porta 5000 no firewall (o bloqueio real)

Hoje **não existe** regra de entrada pra porta 5000, e a rede Wi-Fi está
marcada como **Pública**, o perfil mais restritivo do Windows. O celular
não vai conseguir conectar enquanto isso não mudar.

Abra o PowerShell **como Administrador** e rode:

```powershell
New-NetFirewallRule -DisplayName "Flask Fetin 5000" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow -Profile Any
```

Pra desfazer depois do teste:

```powershell
Remove-NetFirewallRule -DisplayName "Flask Fetin 5000"
```

## Passo 2 — subir o Flask

```powershell
venv\Scripts\python.exe app.py
```

(na pasta `C:\Users\anton\OneDrive\Desktop\Fetins\Controle\inatel_access_api`)

## Passo 3 — instalar o APK

Passe `fetin-celular.apk` pro celular (cabo, Drive, WhatsApp pra você mesmo)
e instale. Vai pedir pra permitir "fontes desconhecidas" — é normal, o APK
está assinado com a chave de debug.

**O celular precisa estar no mesmo Wi-Fi que o PC.**

## Passo 4 — conferir a conexão antes de testar

No navegador **do celular**, abra:

```
http://192.168.20.106:5000/api/eventos
```

- Se aparecer um JSON de erro de token (`401`) → **a conexão está boa**, pode
  seguir. O 401 é esperado, o navegador não tem login.
- Se der timeout / "não foi possível conectar" → o firewall ainda está
  bloqueando (volte ao passo 1) ou o IP mudou (veja abaixo).

## Passo 5 — o teste

Login (`antonio.vinicius@gec.inatel.br`) → aba **Rosto** → "Cadastrar meu
rosto" → permitir câmera → tirar a foto → enviar.

**Sucesso** = mensagem de rosto cadastrado, e a tabela `faces` sai de 0 pra 1.
Confirme rodando isto no backend:

```powershell
venv\Scripts\python.exe -c "from utils.db import get_conn,put_conn; c=get_conn(); cur=c.cursor(); cur.execute('select usuario_id, modelo, atualizado_em from faces'); print(cur.fetchall()); put_conn(c)"
```

Depois, num evento onde essa pessoa esteja convidada, o selo laranja de
"rosto não cadastrado" no avatar deve sumir — é a validação cruzada de que
os dois lados conversam.

## Se o IP da máquina mudar

O `192.168.20.106` é DHCP, então pode mudar ao trocar de rede ou reiniciar
o roteador. Descubra o novo com:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" }
```

E gere um APK novo apontando pra ele — o endereço agora é parâmetro de
build, não precisa editar código:

```powershell
flutter build apk --release --dart-define=API_BASE_URL=http://SEU_IP:5000/api
```

Sem o `--dart-define`, o build volta pro padrão `10.0.2.2` do emulador.

## O que pode dar errado no aparelho real (e o que fazer)

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| "Nenhum rosto detectado" (422) | Foto escura, de lado, ou rosto pequeno demais | Boa luz, rosto de frente ocupando boa parte do quadro |
| App trava/fecha ao abrir a câmera | `ResolutionPreset.high` pesado em aparelho fraco | Baixar pra `medium` em `register_face_screen.dart:100` |
| Upload demora muito e não volta | `ApiClient` não tem timeout | É a pendência #3 já identificada; por ora, espere ou reinicie |
| Erro de conexão só no celular | Firewall / IP errado | Passos 1 e 4 |
