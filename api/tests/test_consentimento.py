"""Consentimento pro uso do rosto (LGPD).

POR QUE ESTES TESTES EXISTEM
Vetor facial é dado pessoal sensível, e tratar dado sensível exige
consentimento específico e demonstrável. "Demonstrável" é a palavra que
importa: o ônus da prova é de quem trata o dado. Um consentimento que o
sistema não consegue provar depois vale o mesmo que consentimento nenhum.

Três coisas quebram calado aqui:

- **Versão.** Se o texto mudar e ninguém for perguntado de novo, o sistema
  passa a alegar um consentimento que a pessoa não deu — ela leu outro
  texto. É o erro mais fácil de cometer, porque nada falha quando acontece.
- **Revogação que apaga a prova.** Quando alguém revoga, o rosto tem que
  sumir, mas o registro do consentimento anterior não: ele é a defesa de
  que o tratamento passado era legítimo. Apagar os dois é destruir a
  própria defesa.
- **Checagem só no cliente.** Se quem decide "já consentiu" for o app,
  qualquer POST fora dele grava biometria sem consentimento. Por isso a
  regra é do servidor, e existe teste separado disso em test_capturas.

Aqui vai a lógica pura; a rota está exercitada em test_capturas.py.
"""

from datetime import datetime, timezone

from services.consentimento import TEXTO, VERSAO, precisa_consentir

AGORA = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def aceito(versao=VERSAO, revogado_em=None):
    return {"versao": versao, "aceito_em": AGORA, "revogado_em": revogado_em}


# ------------------------------------------------------------
# Quando ainda falta consentir
# ------------------------------------------------------------

def test_quem_nunca_consentiu_precisa():
    assert precisa_consentir(None) is True


def test_quem_consentiu_a_versao_atual_nao_precisa():
    assert precisa_consentir(aceito()) is False


def test_texto_novo_pede_consentimento_de_novo():
    # O erro que não falha sozinho: mudar o texto e continuar tratando
    # quem leu o anterior como se tivesse lido o novo.
    assert precisa_consentir(aceito(versao="2020-01-01")) is True


def test_quem_revogou_precisa_consentir_outra_vez():
    assert precisa_consentir(aceito(revogado_em=AGORA)) is True


def test_revogado_pede_de_novo_mesmo_na_versao_atual():
    # A revogação vence a versão: não adianta a versão bater se a pessoa
    # disse não depois.
    assert precisa_consentir(
        {"versao": VERSAO, "aceito_em": AGORA, "revogado_em": AGORA}
    ) is True


def test_o_implicito_da_migracao_nao_conta_como_consentimento():
    # Quem já tinha rosto antes de o texto existir consentiu de fato, mas
    # com algo que ninguém escreveu. A migração registra isso como
    # "0-implicito" justamente pra que a diferença apareça e a pessoa seja
    # perguntada - e não pra fingir que ela leu.
    assert precisa_consentir(aceito(versao="0-implicito")) is True


# ------------------------------------------------------------
# O texto
# ------------------------------------------------------------

def test_o_texto_diz_o_que_e_guardado_e_o_que_nao_e():
    # Consentimento informado é o que descreve o tratamento de verdade. Se
    # alguém reescrever isto prometendo guardar a imagem "com segurança", o
    # texto passa a descrever um sistema que não é este.
    assert "não é guardada" in TEXTO or "descartada" in TEXTO
    assert "512" in TEXTO


def test_o_texto_diz_a_consequencia_de_revogar():
    # Consentimento que esconde o custo de sair não é informado.
    assert "manual" in TEXTO


def test_a_versao_acompanha_o_texto():
    # Não dá pra testar que alguém lembrou de trocar a versão ao editar o
    # texto, mas dá pra prender o formato: data ISO, que ordena sozinha e
    # deixa óbvio quando o texto é antigo.
    assert len(VERSAO) == 10 and VERSAO.count("-") == 2
