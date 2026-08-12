"""Testes da checagem de vivacidade (anti-spoofing).

POR QUE ESTES TESTES EXISTEM
`calcular_embedding` distingue "não vi rosto nenhum" de "vi um rosto, mas era
uma foto" olhando o TEXTO da exceção do DeepFace — a biblioteca usa
ValueError pros dois casos. Isso é frágil de propósito assumido: se numa
atualização a mensagem deixar de conter "spoof", a tradução falha em silêncio
e a porta volta a aceitar foto de tela, sem ninguém perceber.

O teste abaixo quebra nesse cenário, que é o ponto: a falha aparece no CI e
não na frente da banca.

Rodar:  cd api && venv/Scripts/python -m pytest tests -v
"""

import numpy as np
import pytest

from services import face_service
from services.face_service import RostoFalsoError, calcular_embedding


class _FakeDeepFace:
    """Substitui o DeepFace pra não carregar TensorFlow nem precisar de foto."""

    def __init__(self, erro=None, faces=1):
        self.erro = erro
        self.faces = faces

    def represent(self, **kwargs):
        self.kwargs = kwargs
        if self.erro:
            raise ValueError(self.erro)
        return [{"embedding": [0.1] * 512} for _ in range(self.faces)]


@pytest.fixture
def jpeg_valido():
    """Um JPEG 8x8 de verdade, só pra passar pelo cv2.imdecode."""
    import cv2

    ok, buf = cv2.imencode(".jpg", np.zeros((8, 8, 3), dtype=np.uint8))
    assert ok
    return buf.tobytes()


def _usar(monkeypatch, fake):
    monkeypatch.setattr(face_service, "DeepFace", fake)


def test_spoof_vira_erro_proprio(monkeypatch, jpeg_valido):
    # Mensagem real do DeepFace 0.0.93 quando detecta apresentação falsa.
    _usar(monkeypatch, _FakeDeepFace(erro="Spoof detected in the given image."))
    with pytest.raises(RostoFalsoError):
        calcular_embedding(jpeg_valido)


def test_spoof_e_reconhecido_em_qualquer_caixa(monkeypatch, jpeg_valido):
    _usar(monkeypatch, _FakeDeepFace(erro="SPOOF DETECTED"))
    with pytest.raises(RostoFalsoError):
        calcular_embedding(jpeg_valido)


def test_falta_de_torch_nao_vira_veredito_de_burla(monkeypatch, jpeg_valido):
    # Mensagem real do DeepFace quando o torch não está instalado. Ela contém
    # "spoofing", então um casamento frouxo por "spoof" a transformava em
    # "isso parece uma foto" e a porta negava todo mundo sem explicar por quê.
    # Defeito de servidor tem que estourar, não virar NEGADO plausível.
    _usar(monkeypatch, _FakeDeepFace(
        erro="You must install torch with `pip install pytorch` command to "
             "use face anti spoofing module"
    ))
    with pytest.raises(RuntimeError, match="Anti-spoofing indisponível"):
        calcular_embedding(jpeg_valido)


def test_sem_rosto_continua_valueerror_comum(monkeypatch, jpeg_valido):
    _usar(monkeypatch, _FakeDeepFace(erro="Face could not be detected."))
    with pytest.raises(ValueError) as exc:
        calcular_embedding(jpeg_valido)
    # Não pode ser confundido com burla: corredor vazio é rotina.
    assert not isinstance(exc.value, RostoFalsoError)


def test_rosto_falso_e_subclasse_de_valueerror(monkeypatch, jpeg_valido):
    # A rota de cadastro captura ValueError e devolve 422 — se a herança
    # sumir, cadastrar por foto de tela passa a estourar 500.
    assert issubclass(RostoFalsoError, ValueError)


def test_vivacidade_vai_ligada_por_padrao(monkeypatch, jpeg_valido):
    fake = _FakeDeepFace()
    _usar(monkeypatch, fake)
    calcular_embedding(jpeg_valido)
    assert fake.kwargs["anti_spoofing"] is True


def test_da_pra_desligar_a_vivacidade(monkeypatch, jpeg_valido):
    fake = _FakeDeepFace()
    _usar(monkeypatch, fake)
    calcular_embedding(jpeg_valido, checar_vivacidade=False)
    assert fake.kwargs["anti_spoofing"] is False


def test_mais_de_um_rosto_e_recusado(monkeypatch, jpeg_valido):
    _usar(monkeypatch, _FakeDeepFace(faces=2))
    with pytest.raises(ValueError, match="Mais de um rosto"):
        calcular_embedding(jpeg_valido)


def test_imagem_ilegivel(monkeypatch):
    with pytest.raises(ValueError, match="Não foi possível ler"):
        calcular_embedding(b"isto nao e uma imagem")


def test_devolve_512_floats(monkeypatch, jpeg_valido):
    _usar(monkeypatch, _FakeDeepFace())
    emb = calcular_embedding(jpeg_valido)
    assert emb.shape == (512,)          # bate com o vector(512) do schema.sql
    assert emb.dtype == np.float32
