"""A porta inteira funcionando com o banco fora de alcance.

POR QUE ESTES TESTES EXISTEM
Os outros testes do modo offline provam as peças: a cópia responde às três
perguntas, a fila não perde presença. Nenhum deles prova o que interessa —
que uma requisição de verdade do leitor, entrando pela rota, com o Postgres
inalcançável, ainda decide, ainda responde no mesmo formato e ainda registra
o que aconteceu.

É o teste que pega a classe de erro mais provável desse tipo de mudança: as
peças certas, ligadas errado. Chave de dispositivo que só é procurada no
banco, `etapa` que muda de nome no caminho alternativo, presença que é
decidida e não é enfileirada.

Sobe uma app Flask com só o blueprint de faces e finge três coisas: que o
banco está fora (`sem_banco`), qual é a cópia local, e qual embedding a foto
gerou. Nada de banco, nada de câmera, nada de DeepFace.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from flask import Flask

from routes import faces
from services import cache_local, fila_offline
from utils import device_auth

CHAVE = "chave-do-leitor-de-teste"
CHAVE_HASH = hashlib.sha256(CHAVE.encode()).hexdigest()

ANA = "11111111-1111-1111-1111-111111111111"
BETO = "22222222-2222-2222-2222-222222222222"


def vetor(*valores):
    v = [0.0] * 512
    for i, x in enumerate(valores):
        v[i] = x
    return v


ROSTO_DA_ANA = vetor(1.0, 0.0)
ROSTO_DO_BETO = vetor(0.0, 1.0)
ROSTO_DESCONHECIDO = vetor(-1.0, -0.3)


def copia_com(participantes, minutos_ate_comecar=-30):
    inicio = datetime.now(timezone.utc) + timedelta(minutes=minutos_ate_comecar)
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "faces": [
            {"usuario_id": ANA, "nome": "Ana", "embedding": ROSTO_DA_ANA},
            {"usuario_id": BETO, "nome": "Beto", "embedding": ROSTO_DO_BETO},
        ],
        "dispositivos": [{
            "id": 1, "nome": "leitor-quadra", "local": "Quadra",
            "local_norm": "quadra", "chave_hash": CHAVE_HASH, "ativo": True,
        }],
        "eventos": [{
            "id": 77, "titulo": "Cálculo I", "local": "Quadra",
            "local_norm": "quadra",
            "data_inicio": inicio.isoformat(),
            "data_fim": (inicio + timedelta(hours=2)).isoformat(),
            "participantes": list(participantes),
        }],
    }


@pytest.fixture
def porta(monkeypatch, tmp_path):
    """Cliente HTTP da porta, com o banco fora de alcance."""
    app = Flask(__name__)
    app.register_blueprint(faces.bp)

    monkeypatch.setattr(faces, "sem_banco", lambda: True)
    monkeypatch.setattr(device_auth, "sem_banco", lambda: True)
    monkeypatch.setattr(fila_offline, "ARQUIVO", tmp_path / "pendentes.jsonl")

    def montar(copia, embedding=ROSTO_DA_ANA):
        monkeypatch.setattr(cache_local, "carregar", lambda *a, **k: copia)
        monkeypatch.setattr(
            faces, "calcular_embedding",
            lambda *a, **k: np.array(embedding, dtype=np.float32),
        )
        return app.test_client()

    montar.fila = tmp_path / "pendentes.jsonl"
    return montar


def bater_na_porta(cliente, chave=CHAVE):
    return cliente.post(
        "/api/faces/recognize",
        headers={"X-Device-Key": chave},
        data={"foto": (open(__file__, "rb"), "captura.jpg")},
        content_type="multipart/form-data",
    )


# ------------------------------------------------------------
# Decide
# ------------------------------------------------------------

def test_convidado_entra_sem_internet(porta):
    r = bater_na_porta(porta(copia_com([ANA])))
    assert r.status_code == 200
    assert r.json["liberado"] is True
    assert r.json["nome"] == "Ana"
    assert r.json["evento"] == "Cálculo I"


def test_reconhecido_mas_nao_convidado_e_negado(porta):
    # O caso mais sutil da porta: o sistema sabe quem é e ainda assim nega.
    r = bater_na_porta(porta(copia_com([BETO])))
    assert r.json["liberado"] is False
    assert r.json["etapa"] == "lista"
    assert r.json["nome"] == "Ana"


def test_rosto_de_fora_do_cadastro_e_negado(porta):
    r = bater_na_porta(porta(copia_com([ANA]), embedding=ROSTO_DESCONHECIDO))
    assert r.json["liberado"] is False
    assert r.json["etapa"] == "identidade"


def test_sem_aula_agora_ninguem_entra(porta):
    r = bater_na_porta(porta(copia_com([ANA], minutos_ate_comecar=+120)))
    assert r.json["liberado"] is False
    assert r.json["etapa"] == "aula"
    assert "Quadra" in r.json["motivo"]


def test_a_resposta_tem_o_mesmo_formato_do_modo_online(porta):
    # O totem lê estes campos. Se o caminho offline responder diferente, a
    # tela quebra justamente no dia em que a internet caiu.
    r = bater_na_porta(porta(copia_com([ANA])))
    assert set(r.json) == {"liberado", "motivo", "etapa", "nome", "evento"}
    assert r.json["etapa"] is None  # etapa só nomeia ONDE parou


def test_etapa_negada_esta_no_contrato(porta):
    r = bater_na_porta(porta(copia_com([BETO])))
    assert r.json["etapa"] in faces.ETAPAS


# ------------------------------------------------------------
# Autentica o leitor
# ------------------------------------------------------------

def test_chave_do_leitor_vale_pela_copia(porta):
    assert bater_na_porta(porta(copia_com([ANA]))).status_code == 200


def test_chave_desconhecida_continua_recusada(porta):
    r = bater_na_porta(porta(copia_com([ANA])), chave="chave-inventada")
    assert r.status_code == 401


def test_sem_banco_e_sem_copia_a_porta_admite_que_nao_sabe(porta):
    # Recusar é a única resposta honesta - e o 503 diz que o problema é o
    # servidor, não a chave do leitor.
    r = bater_na_porta(porta(None))
    assert r.status_code == 503


# ------------------------------------------------------------
# Registra
# ------------------------------------------------------------

def test_liberacao_offline_vai_pra_fila(porta):
    cliente = porta(copia_com([ANA]))
    bater_na_porta(cliente)

    (linha,) = porta.fila.read_text(encoding="utf-8").strip().splitlines()
    registro = json.loads(linha)
    assert registro["liberado"] is True
    assert registro["usuario_id"] == ANA
    assert registro["evento_id"] == 77
    assert registro["dispositivo"] == "leitor-quadra"


def test_negativa_offline_tambem_vai_pra_fila(porta):
    bater_na_porta(porta(copia_com([BETO])))
    assert json.loads(porta.fila.read_text(encoding="utf-8"))["liberado"] is False


def test_a_fila_guarda_a_hora_da_porta(porta):
    antes = datetime.now(timezone.utc)
    bater_na_porta(porta(copia_com([ANA])))
    quando = datetime.fromisoformat(
        json.loads(porta.fila.read_text(encoding="utf-8"))["quando"]
    )
    # Tem que ser agora, não a hora em que a rede voltar - é o que separa
    # "presente às 14h03" de "todo mundo presente às 19h40".
    assert antes <= quando <= datetime.now(timezone.utc)
