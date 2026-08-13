"""A cópia local responde às mesmas três perguntas que o banco.

POR QUE ESTES TESTES EXISTEM
Quando a internet cair, quem vai decidir quem entra é o cache - e ele
responde por conta própria, em Python, o que hoje o Postgres responde em
SQL. São duas implementações da mesma regra, e é exatamente aí que sistemas
offline apodrecem: a de reserva diverge da principal em silêncio e ninguém
percebe até o dia em que ela é a única que está rodando.

Os testes abaixo prendem as três respostas contra os casos que importam - o
vizinho mais próximo é o MÍNIMO (não o primeiro), a aula é a que está
acontecendo AGORA naquela sala, e a lista de convidados é consultada por
identidade e não por posição.

Não tocam no banco nem em arquivo: montam a cópia à mão.
"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from services import cache_local

AGORA = datetime(2026, 8, 14, 10, 30, tzinfo=timezone.utc)


def vetor(*valores):
    v = [0.0] * 512
    for i, x in enumerate(valores):
        v[i] = x
    return v


def evento(id, local_norm, comeca_em_min, dura_min=60, participantes=()):
    inicio = AGORA + timedelta(minutes=comeca_em_min)
    return {
        "id": id,
        "titulo": f"Aula {id}",
        "local": local_norm.upper(),
        "local_norm": local_norm,
        "data_inicio": inicio.isoformat(),
        "data_fim": (inicio + timedelta(minutes=dura_min)).isoformat(),
        "participantes": list(participantes),
    }


@pytest.fixture
def copia():
    return {
        "gerado_em": (AGORA - timedelta(hours=3)).isoformat(),
        "faces": [
            {"usuario_id": "ana", "nome": "Ana", "embedding": vetor(1.0, 0.0)},
            {"usuario_id": "beto", "nome": "Beto", "embedding": vetor(0.0, 1.0)},
            {"usuario_id": "ana", "nome": "Ana", "embedding": vetor(0.9, 0.1)},
        ],
        "dispositivos": [
            {"id": 1, "nome": "leitor-quadra", "local": "Quadra",
             "local_norm": "quadra", "chave_hash": "abc123", "ativo": True},
        ],
        "eventos": [
            evento(10, "quadra", comeca_em_min=-30, participantes=["ana"]),
            evento(11, "sala201", comeca_em_min=-30, participantes=["beto"]),
            evento(12, "quadra", comeca_em_min=+120, participantes=["beto"]),
        ],
    }


# ------------------------------------------------------------
# Quem é
# ------------------------------------------------------------

def test_acha_o_rosto_mais_proximo(copia):
    face, distancia = cache_local.vizinho_mais_proximo(copia, vetor(1.0, 0.0))
    assert face["nome"] == "Ana"
    assert distancia == pytest.approx(0.0, abs=1e-6)


def test_pega_o_minimo_e_nao_a_primeira_linha_da_pessoa(copia):
    # Ana tem duas capturas; a segunda é a próxima deste alvo. Se isto virar
    # "a primeira linha dela", o ganho das várias fotos some no modo offline
    # sem quebrar nada visível.
    alvo = vetor(0.9, 0.1)
    face, distancia = cache_local.vizinho_mais_proximo(copia, alvo)
    assert face["usuario_id"] == "ana"
    assert distancia == pytest.approx(0.0, abs=1e-6)


def test_estranho_fica_longe(copia):
    _, distancia = cache_local.vizinho_mais_proximo(copia, vetor(-1.0, -0.2))
    assert distancia > 0.30


def test_a_distancia_e_a_mesma_do_pgvector(copia):
    # O <=> do pgvector é distância de cosseno. Se esta conta virar
    # euclidiana, o limiar de 0,30 passa a significar outra coisa e a porta
    # offline decide diferente da online com os mesmos dados.
    from services.face_service import similaridade_cosseno

    alvo = vetor(0.5, 0.5)
    _, distancia = cache_local.vizinho_mais_proximo(copia, alvo)
    esperado = min(
        1 - similaridade_cosseno(np.array(alvo), np.array(f["embedding"]))
        for f in copia["faces"]
    )
    assert distancia == pytest.approx(esperado, abs=1e-6)


def test_cache_sem_rostos_nao_estoura(copia):
    copia["faces"] = []
    assert cache_local.vizinho_mais_proximo(copia, vetor(1.0)) is None


# ------------------------------------------------------------
# Tem aula agora
# ------------------------------------------------------------

def test_acha_a_aula_em_andamento_naquela_sala(copia):
    e = cache_local.evento_agora(copia, "quadra", AGORA)
    assert e["id"] == 10


def test_aula_de_outra_sala_nao_serve(copia):
    # O evento 11 está rolando agora, mas na sala 201.
    assert cache_local.evento_agora(copia, "laboratorio", AGORA) is None


def test_aula_que_ainda_vai_comecar_nao_abre_a_porta(copia):
    # 12:00: a aula das 10h já acabou e a das 12h30 ainda não começou. A
    # porta tem que ficar fechada no intervalo, mesmo com a sala certa e a
    # pessoa certa na frente da câmera.
    assert cache_local.evento_agora(copia, "quadra", AGORA + timedelta(minutes=90)) is None


def test_aula_futura_abre_quando_chega_a_hora(copia):
    # A outra metade do teste acima: o evento 12 existe e vale, só não vale
    # ainda. Sem isto, "nunca devolver nada" passaria nos dois.
    e = cache_local.evento_agora(copia, "quadra", AGORA + timedelta(minutes=150))
    assert e["id"] == 12


def test_aula_ja_encerrada_nao_abre_a_porta(copia):
    assert cache_local.evento_agora(copia, "quadra", AGORA + timedelta(minutes=45)) is None


# ------------------------------------------------------------
# Foi convidado
# ------------------------------------------------------------

def test_convidado_esta_na_lista(copia):
    assert cache_local.esta_na_lista(copia["eventos"][0], "ana")


def test_reconhecido_mas_nao_convidado(copia):
    # O caso mais sutil da porta, e o que mais confunde quem assiste:
    # o sistema sabe quem é a pessoa e ainda assim nega.
    assert not cache_local.esta_na_lista(copia["eventos"][0], "beto")


# ------------------------------------------------------------
# Dispositivo e arquivo
# ------------------------------------------------------------

def test_dispositivo_pelo_hash_da_chave(copia):
    d = cache_local.dispositivo_por_hash(copia, "abc123")
    assert d["local_norm"] == "quadra"


def test_chave_desconhecida_nao_vira_dispositivo(copia):
    assert cache_local.dispositivo_por_hash(copia, "chave-que-nao-existe") is None


def test_salvar_e_carregar_preserva_tudo(copia, tmp_path):
    caminho = tmp_path / "cache.json"
    cache_local.salvar(copia, caminho)
    assert cache_local.carregar(caminho) == copia


def test_carregar_sem_arquivo_devolve_none(tmp_path):
    assert cache_local.carregar(tmp_path / "nao-existe.json") is None


def test_escrita_nao_deixa_arquivo_pela_metade(copia, tmp_path):
    # Grava em .tmp e renomeia: um JSON truncado por queda de energia
    # deixaria a porta sem plano B justamente na hora em que ele é o único.
    caminho = tmp_path / "cache.json"
    cache_local.salvar(copia, caminho)
    assert json.loads(caminho.read_text(encoding="utf-8"))["faces"]
    assert not (tmp_path / "cache.tmp").exists()


def test_idade_da_copia(copia):
    assert cache_local.idade_em_horas(copia, AGORA) == pytest.approx(3.0, abs=0.01)
