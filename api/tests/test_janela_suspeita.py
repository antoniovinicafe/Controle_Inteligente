"""Uma suspeita forte de fraude vale pelos segundos seguintes.

POR QUE ISTO EXISTE
Em 15/08/2026, na porta, a MESMA foto erguida na frente da câmera marcou
100% de certeza de fraude numa leitura e "pessoa" nas duas seguintes. E
"pessoa" é veredito que nenhum limiar barra: o limiar só decide quando
NEGAR. Como o leitor pergunta de segundo em segundo, bastava insistir com a
foto até cair uma leitura favorável — foi exatamente o que aconteceu, e a
porta abriu.

Uma pessoa de verdade, no mesmo dia e na mesma câmera, nunca passou de 58%
de suspeita. Então uma leitura acima de 90% não é ruído: é sinal de que tem
uma foto ali AGORA, e vale pelos próximos segundos.

Isto não fecha o buraco, fecha a janela — quem insistir muito ainda pode
pegar uma sequência limpa. O que some é o "ergue a foto e espera".

O outro lado, que estes testes prendem junto: a suspeita NÃO pode valer
pra sempre nem ser fácil de disparar, senão a porta trava sozinha e todo
mundo fica de fora por causa de um quadro estranho.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from flask import Flask

from routes import faces
from services import cache_local, fila_offline
from services.face_service import RostoFalsoError
from utils import device_auth

CHAVE = "chave-do-leitor-de-teste"
CHAVE_HASH = hashlib.sha256(CHAVE.encode()).hexdigest()
ANA = "11111111-1111-1111-1111-111111111111"


def vetor(*valores):
    v = [0.0] * 512
    for i, x in enumerate(valores):
        v[i] = x
    return v


@pytest.fixture
def copia():
    inicio = datetime.now(timezone.utc) - timedelta(minutes=10)
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "faces": [{"usuario_id": ANA, "nome": "Ana", "embedding": vetor(1.0, 0.0)}],
        "dispositivos": [{
            "id": 1, "nome": "leitor-quadra", "local": "Quadra",
            "local_norm": "quadra", "chave_hash": CHAVE_HASH, "ativo": True,
        }],
        "eventos": [{
            "id": 77, "titulo": "Cálculo I", "local": "Quadra", "local_norm": "quadra",
            "data_inicio": inicio.isoformat(),
            "data_fim": (inicio + timedelta(hours=2)).isoformat(),
            "participantes": [ANA],
        }],
    }


@pytest.fixture
def porta(monkeypatch, tmp_path, copia):
    """Cliente da porta, sem banco, com a vivacidade sob controle do teste."""
    app = Flask(__name__)
    app.register_blueprint(faces.bp)

    monkeypatch.setattr(faces, "sem_banco", lambda: True)
    monkeypatch.setattr(device_auth, "sem_banco", lambda: True)
    monkeypatch.setattr(cache_local, "carregar", lambda *a, **k: copia)
    monkeypatch.setattr(fila_offline, "ARQUIVO", tmp_path / "pendentes.jsonl")
    # Cada teste começa sem memória de suspeita: o dicionário é global.
    monkeypatch.setattr(faces, "_suspeitas", {})

    cliente = app.test_client()

    def ler(erro=None):
        """Uma leitura da porta. `erro` finge o veredito da vivacidade."""
        def embedding(*a, **k):
            if erro:
                raise erro
            return np.array(vetor(1.0, 0.0), dtype=np.float32)

        monkeypatch.setattr(faces, "calcular_embedding", embedding)
        return cliente.post(
            "/api/faces/recognize",
            headers={"X-Device-Key": CHAVE},
            data={"foto": (open(__file__, "rb"), "captura.jpg")},
            content_type="multipart/form-data",
        ).json

    return ler


def foto_cravada():
    return RostoFalsoError("Isso parece uma foto (100% de certeza)", certeza=1.0)


def suspeita_fraca():
    # O tipo de leitura que uma pessoa de verdade gera em luz ruim.
    return RostoFalsoError("Isso parece uma foto (58% de certeza)", certeza=0.58)


# ------------------------------------------------------------
# A janela fecha
# ------------------------------------------------------------

def test_sem_suspeita_a_porta_libera(porta):
    assert porta()["liberado"] is True


def test_depois_de_uma_foto_cravada_a_leitura_seguinte_nao_libera(porta):
    # É o ataque real: 100% de fraude, e a leitura seguinte diz "pessoa".
    assert porta(erro=foto_cravada())["liberado"] is False
    seguinte = porta()
    assert seguinte["liberado"] is False
    assert seguinte["etapa"] == "vivacidade"


def test_a_recusa_explica_o_que_fazer(porta):
    porta(erro=foto_cravada())
    assert "afaste" in porta()["motivo"].lower()


def test_a_janela_expira(porta, monkeypatch):
    porta(erro=foto_cravada())
    assert porta()["liberado"] is False

    # Passado o tempo, a porta volta a confiar na leitura de agora - senão
    # uma tentativa de burla deixaria a sala trancada pra sempre.
    agora = faces.time.monotonic()
    monkeypatch.setattr(
        faces.time, "monotonic",
        lambda: agora + faces.SEGUNDOS_APOS_SUSPEITA + 1,
    )
    assert porta()["liberado"] is True


# ------------------------------------------------------------
# E não fecha demais
# ------------------------------------------------------------

def test_suspeita_fraca_nao_tranca_a_porta(porta):
    # 58% foi o pior que uma pessoa de verdade produziu na medição. Se isso
    # armasse a janela, quem passa em luz ruim trancaria a porta pra si
    # mesmo e pra quem viesse atrás.
    assert porta(erro=suspeita_fraca())["liberado"] is False   # nega a leitura
    assert porta()["liberado"] is True                          # mas não a próxima


def test_a_suspeita_e_por_dispositivo(porta, copia, monkeypatch):
    # Uma foto erguida na porta da quadra não pode trancar a porta do
    # laboratório: são leitores diferentes, salas diferentes.
    porta(erro=foto_cravada())
    faces._suspeitas.clear()
    faces._suspeitas[999] = faces.time.monotonic()   # outro dispositivo
    assert porta()["liberado"] is True
