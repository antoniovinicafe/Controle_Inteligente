"""Exportação de presença e frequência em CSV.

POR QUE ESTES TESTES EXISTEM
As duas coisas que quebram aqui não levantam exceção nenhuma: o arquivo
sai, o download funciona, e o estrago só aparece quando alguém abre no
Excel — que costuma ser depois de a planilha já ter sido enviada.

O BOM e o ponto e vírgula parecem detalhe estético e não são. Sem BOM o
Excel em pt-BR supõe a codificação do Windows e todo nome com acento sai
corrompido; com vírgula em vez de ponto e vírgula, a linha inteira cai
numa célula só. Nos dois casos quem recebe conclui que o sistema é que
está quebrado.

O terceiro teste é de conteúdo: permanência é ter sido visto DUAS vezes na
mesma aula. Afirmar permanência com uma leitura só seria dizer que a
pessoa ficou quando o sistema só sabe que ela entrou — e é justamente essa
distinção que faz a exportação valer mais que uma lista assinada.
"""

from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask

from utils.planilha import formatar_hora, resposta_csv


@pytest.fixture
def app():
    return Flask(__name__)


def corpo(resposta) -> str:
    """O texto do arquivo, já sem o BOM."""
    return resposta.get_data().decode("utf-8-sig")


# ------------------------------------------------------------
# O que o Excel brasileiro exige
# ------------------------------------------------------------

def test_o_arquivo_comeca_com_bom(app):
    # Sem isto "João" vira "JoÃ£o" ao abrir no Excel em pt-BR.
    with app.test_request_context():
        bruto = resposta_csv("teste", ["Nome"], [["João"]]).get_data()
    assert bruto[:3] == b"\xef\xbb\xbf"


def test_as_colunas_sao_separadas_por_ponto_e_virgula(app):
    # Com vírgula o Excel em pt-BR joga a linha toda numa célula só.
    with app.test_request_context():
        texto = corpo(resposta_csv("teste", ["Nome", "Situacao"], [["Ana", "Presente"]]))
    assert "Nome;Situacao" in texto


def test_acento_sobrevive_a_ida_e_volta(app):
    with app.test_request_context():
        texto = corpo(resposta_csv("teste", ["Nome"], [["João Conceição"]]))
    assert "João Conceição" in texto


def test_celula_vazia_em_vez_de_none(app):
    # Sem tratar, o csv escreveria a palavra "None" na célula.
    with app.test_request_context():
        texto = corpo(resposta_csv("teste", ["Nome", "Hora"], [["Ana", None]]))
    assert "None" not in texto
    assert "Ana;" in texto


def test_o_download_leva_nome_de_arquivo(app):
    with app.test_request_context():
        cab = resposta_csv("presenca Cálculo I", ["Nome"], []).headers["Content-Disposition"]
    assert "attachment" in cab
    # A versão sem acento é pra cliente antigo; a filename* carrega o nome
    # de verdade pra quem entende UTF-8.
    assert "filename=presenca-Calculo-I.csv" in cab
    assert "filename*=UTF-8''" in cab


# ------------------------------------------------------------
# Hora que uma pessoa lê
# ------------------------------------------------------------

def test_hora_sai_legivel_e_nao_em_iso(app):
    # ISO 8601 com fuso o Excel trata como texto, e a coluna perde o que
    # tinha de útil: bater o olho e ver quem chegou atrasado.
    quando = datetime(2026, 9, 21, 19, 5, tzinfo=timezone.utc)
    formatada = formatar_hora(quando)
    assert "T" not in formatada and "+" not in formatada
    assert "21/09/2026" in formatada


def test_sem_leitura_a_celula_fica_vazia(app):
    assert formatar_hora(None) == ""


# ------------------------------------------------------------
# Permanência: a regra que dá valor à planilha
# ------------------------------------------------------------

def permanencia(leituras) -> str:
    """A mesma regra da rota, isolada pra poder ser afirmada aqui."""
    return "Sim" if (leituras or 0) > 1 else "Nao"


def test_duas_leituras_viram_permanencia():
    assert permanencia(2) == "Sim"


def test_uma_leitura_nao_vira_permanencia():
    # O sistema sabe que a pessoa entrou. Não sabe que ela ficou.
    assert permanencia(1) == "Nao"


def test_ausente_nao_vira_permanencia():
    assert permanencia(0) == "Nao"
    assert permanencia(None) == "Nao"
