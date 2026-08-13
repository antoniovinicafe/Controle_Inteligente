"""Nada do que a porta decidiu offline pode se perder.

POR QUE ESTES TESTES EXISTEM
Porta que libera sem registrar é pior que porta que nega. Negar é visível —
a pessoa reclama na hora. Liberar sem gravar é silencioso: o aluno entrou,
assistiu à aula, e a frequência dele no fim do mês diz que faltou. E não dá
pra reconstruir depois, porque a imagem não é guardada e o veredito só
existiu na memória do processo.

O outro erro, mais sutil, é subir os registros com a hora do ENVIO. Uma
turma que entrou às 14h03 apareceria presente às 19h40, quando a internet
voltou — dado errado com cara de dado certo, que é o pior tipo. O teste do
carimbo de hora prende isso.

Não tocam no banco: o cursor é um dublê que guarda os SQLs que receberia.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from services import fila_offline

QUANDO = datetime(2026, 8, 14, 14, 3, tzinfo=timezone.utc)
VOLTOU_A_REDE = datetime(2026, 8, 14, 19, 40, tzinfo=timezone.utc)


class CursorFalso:
    """Guarda (sql, parâmetros) de cada execute, sem banco nenhum."""

    def __init__(self):
        self.comandos = []

    def execute(self, sql, params=None):
        self.comandos.append((" ".join(sql.split()), params))

    def de(self, trecho):
        """Os comandos que contêm um trecho de SQL."""
        return [c for c in self.comandos if trecho in c[0]]


@pytest.fixture
def arquivo(tmp_path):
    return tmp_path / "pendentes.jsonl"


def test_veredito_offline_vira_linha_no_arquivo(arquivo):
    fila_offline.enfileirar(
        True, "Acesso liberado", "leitor-quadra",
        evento_id=10, usuario_id="ana", quando=QUANDO, caminho=arquivo,
    )
    assert len(fila_offline.pendentes(arquivo)) == 1


def test_a_ordem_dos_acontecimentos_e_preservada(arquivo):
    for i in range(3):
        fila_offline.enfileirar(
            True, f"veredito {i}", "leitor-quadra",
            quando=QUANDO + timedelta(minutes=i), caminho=arquivo,
        )
    motivos = [r["motivo"] for r in fila_offline.pendentes(arquivo)]
    assert motivos == ["veredito 0", "veredito 1", "veredito 2"]


def test_negativas_tambem_sobem(arquivo):
    # A auditoria de um controle de acesso vive das recusas; sumir com elas
    # no período offline esconderia justamente as tentativas.
    fila_offline.enfileirar(
        False, "Rosto não reconhecido", "leitor-quadra",
        quando=QUANDO, caminho=arquivo,
    )
    cur = CursorFalso()
    fila_offline.enviar(cur, arquivo)
    (_, params), = cur.de("insert into access_logs")
    assert "negado" in params


def test_a_hora_gravada_e_a_da_porta_e_nao_a_do_envio(arquivo):
    fila_offline.enfileirar(
        True, "Acesso liberado", "leitor-quadra",
        evento_id=10, usuario_id="ana", quando=QUANDO, caminho=arquivo,
    )
    cur = CursorFalso()
    fila_offline.enviar(cur, arquivo)

    for _, params in cur.comandos:
        assert QUANDO.isoformat() in params
        assert VOLTOU_A_REDE.isoformat() not in params


def test_liberacao_vira_log_e_presenca(arquivo):
    fila_offline.enfileirar(
        True, "Acesso liberado", "leitor-quadra",
        evento_id=10, usuario_id="ana", quando=QUANDO, caminho=arquivo,
    )
    cur = CursorFalso()
    assert fila_offline.enviar(cur, arquivo) == 1
    assert len(cur.de("insert into access_logs")) == 1
    assert len(cur.de("update evento_participantes")) == 1


def test_negativa_nao_marca_presenca(arquivo):
    fila_offline.enfileirar(
        False, "Não está na lista", "leitor-quadra",
        evento_id=10, usuario_id="ana", quando=QUANDO, caminho=arquivo,
    )
    cur = CursorFalso()
    fila_offline.enviar(cur, arquivo)
    assert cur.de("update evento_participantes") == []


def test_liberacao_sem_aula_identificada_nao_marca_presenca(arquivo):
    # Não deve acontecer pela lógica da porta, mas se acontecer o update
    # iria pra `evento_id = None` e marcaria presença em lugar nenhum.
    fila_offline.enfileirar(
        True, "estranho", "leitor-quadra",
        evento_id=None, usuario_id="ana", quando=QUANDO, caminho=arquivo,
    )
    cur = CursorFalso()
    fila_offline.enviar(cur, arquivo)
    assert cur.de("update evento_participantes") == []


def test_depois_de_subir_a_fila_fica_vazia(arquivo):
    fila_offline.enfileirar(True, "ok", "leitor-quadra", quando=QUANDO, caminho=arquivo)
    fila_offline.enviar(CursorFalso(), arquivo)
    assert fila_offline.pendentes(arquivo) == []
    assert not arquivo.exists()


def test_enviar_fila_vazia_nao_faz_nada(arquivo):
    cur = CursorFalso()
    assert fila_offline.enviar(cur, arquivo) == 0
    assert cur.comandos == []


def test_linha_truncada_nao_derruba_o_resto(arquivo):
    # Queda de energia no meio da escrita corrompe a ÚLTIMA linha. Perder
    # uma é ruim; deixar de subir as outras 200 seria muito pior.
    fila_offline.enfileirar(True, "boa", "leitor-quadra", quando=QUANDO, caminho=arquivo)
    with arquivo.open("a", encoding="utf-8") as f:
        f.write('{"quando": "2026-08-14T14:0')

    registros = fila_offline.pendentes(arquivo)
    assert len(registros) == 1
    assert registros[0]["motivo"] == "boa"


def test_o_arquivo_e_legivel_a_olho_nu(arquivo):
    # É o que alguém vai abrir no meio de uma demonstração pra responder
    # "e o que aconteceu enquanto a rede estava fora?".
    fila_offline.enfileirar(
        True, "Acesso liberado", "leitor-quadra",
        evento_id=10, usuario_id="ana", quando=QUANDO, caminho=arquivo,
    )
    linha = json.loads(arquivo.read_text(encoding="utf-8").strip())
    assert linha["motivo"] == "Acesso liberado"
    assert linha["quando"].startswith("2026-08-14T14:03")
