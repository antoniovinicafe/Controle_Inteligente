"""
O texto do consentimento e as regras de quando ele vale.

POR QUE ISTO É CÓDIGO, E NÃO TEXTO NUMA TELA DO APP
A LGPD pede consentimento **específico e destacado** pra dado sensível, e
pede que ele seja demonstrável. Duas consequências práticas:

- o texto precisa ser versionado. Se ele mudar, quem aceitou o anterior não
  consentiu com o novo, e tem que ser perguntado de novo. Versão no código,
  ao lado do texto, é o jeito de as duas coisas não se separarem.
- o servidor precisa ser dono da regra. Se quem decide "já consentiu" for o
  app, basta um APK antigo, ou um cliente escrito à mão, pra o rosto entrar
  sem consentimento nenhum - e aí o registro no banco vira decoração.

O texto abaixo evita as duas fugas comuns: não promete o que o sistema não
faz (não diz "a imagem é criptografada", porque ela simplesmente não é
guardada), e diz o que a pessoa perde ao revogar, porque consentimento que
esconde a consequência não é informado.
"""

# Muda junto com o texto, SEMPRE. É o que faz alguém que aceitou a versão
# antiga ser perguntado de novo em vez de ser tratado como se tivesse lido.
VERSAO = "2026-08-16"

TITULO = "Uso do seu rosto"

TEXTO = """\
Pra reconhecer você na porta, o Fetin precisa transformar uma foto do seu \
rosto em um código numérico e guardar esse código.

O que é guardado: um vetor de 512 números, do qual não dá pra reconstruir \
a sua foto.
O que NÃO é guardado: a imagem. Ela é usada pra gerar o código e \
descartada em seguida — nem o servidor nem o leitor da porta ficam com ela.

Pra que serve: exclusivamente pra identificar você nas portas das salas e \
registrar sua presença nas aulas em que você foi convidado. Não é usado \
pra mais nada, e não é compartilhado com ninguém fora do sistema.

Você pode cancelar quando quiser, pelo próprio aplicativo, e os códigos são \
apagados na hora. A partir daí a porta deixa de reconhecer você, e sua \
presença passa a depender de liberação manual do professor.

Seu rosto é um dado pessoal sensível, e por isso este consentimento é \
pedido separado dos demais. Sem ele, nenhum rosto é cadastrado."""


def precisa_consentir(registro: dict | None) -> bool:
    """
    True quando ainda falta consentir - por nunca ter consentido, por ter
    revogado, ou por ter aceitado uma versão anterior do texto.

    `registro` é a linha mais recente de `consentimentos` da pessoa, ou
    None.
    """
    if not registro:
        return True
    if registro.get("revogado_em"):
        return True
    return registro.get("versao") != VERSAO
