"""Testes da checagem de vivacidade (anti-spoofing).

POR QUE ESTES TESTES EXISTEM
A vivacidade tem dois jeitos de dar errado, e eles puxam pra lados opostos:
negar quem tem direito de entrar (pessoa parada na porta que não abre) e
aceitar uma foto erguida na frente da câmera. O que decide entre os dois é um
número só - LIMIAR_FALSIDADE - e é fácil mexer nele sem perceber que o outro
lado desandou. Os testes abaixo prendem os dois extremos: dúvida do modelo
libera, certeza barra.

Prendem também a tradução por TEXTO da exceção do DeepFace: a biblioteca usa
ValueError pra "não vi rosto", pra "isso é foto" e pra "falta torch", e só a
mensagem distingue. Se numa atualização o texto mudar, a tradução falha em
silêncio - e a falha aparece aqui, não na frente da banca.

Rodar:  cd api && venv/Scripts/python -m pytest tests -v
"""

import numpy as np
import pytest

from services import face_service
from services.face_service import RostoFalsoError, calcular_embedding


class _FakeDeepFace:
    """Substitui o DeepFace pra não carregar TensorFlow nem precisar de foto.

    `is_real=None` imita a resposta de quando a vivacidade não foi pedida: a
    chave simplesmente não vem.
    """

    def __init__(self, erro=None, faces=1, is_real=None, certeza=0.0):
        self.erro = erro
        self.faces = faces
        self.is_real = is_real
        self.certeza = certeza

    def extract_faces(self, **kwargs):
        self.kwargs = kwargs
        if self.erro:
            raise ValueError(self.erro)
        rosto = {"face": np.zeros((8, 8, 3)), "facial_area": {}, "confidence": 1}
        if self.is_real is not None:
            rosto["is_real"] = self.is_real
            rosto["antispoof_score"] = self.certeza
        return [dict(rosto) for _ in range(self.faces)]

    def represent(self, **kwargs):
        self.represent_kwargs = kwargs
        return [{"embedding": [0.1] * 512}]


@pytest.fixture
def jpeg_valido():
    """Um JPEG 8x8 de verdade, só pra passar pelo cv2.imdecode."""
    import cv2

    ok, buf = cv2.imencode(".jpg", np.zeros((8, 8, 3), dtype=np.uint8))
    assert ok
    return buf.tobytes()


def _usar(monkeypatch, fake):
    monkeypatch.setattr(face_service, "DeepFace", fake)
    return fake


# ------------------------------------------------------------
# O limiar: onde a dúvida vira recusa
# ------------------------------------------------------------

def test_certeza_alta_barra(monkeypatch, jpeg_valido):
    # Foto/tela de verdade: o MiniFASNet crava. Isso tem que barrar.
    _usar(monkeypatch, _FakeDeepFace(is_real=False, certeza=0.95))
    with pytest.raises(RostoFalsoError):
        calcular_embedding(jpeg_valido)


def test_duvida_do_modelo_libera(monkeypatch, jpeg_valido):
    # 40% é o empate técnico: "real" perdeu por pouco pras duas suspeitas
    # somadas. É o que acontece com pessoa de verdade em luz ruim, e o
    # DeepFace sozinho negaria. Aqui passa - é a razão de o limiar existir.
    _usar(monkeypatch, _FakeDeepFace(is_real=False, certeza=0.40))
    emb = calcular_embedding(jpeg_valido)
    assert emb.shape == (512,)


def test_limiar_e_ajustavel(monkeypatch, jpeg_valido):
    # Mesmo quadro de cima, com a porta configurada pra ser severa.
    monkeypatch.setattr(face_service, "LIMIAR_FALSIDADE", 0.35)
    _usar(monkeypatch, _FakeDeepFace(is_real=False, certeza=0.40))
    with pytest.raises(RostoFalsoError):
        calcular_embedding(jpeg_valido)


def test_recusa_diz_a_certeza(monkeypatch, jpeg_valido):
    # O número vai no texto porque é ele que se ajusta no .env, e este texto
    # é o que aparece no terminal do leitor e no access_logs. Sem ele, mexer
    # no limiar é chute.
    _usar(monkeypatch, _FakeDeepFace(is_real=False, certeza=0.93))
    with pytest.raises(RostoFalsoError, match="93%"):
        calcular_embedding(jpeg_valido)


def test_pessoa_real_passa(monkeypatch, jpeg_valido):
    _usar(monkeypatch, _FakeDeepFace(is_real=True, certeza=0.99))
    assert calcular_embedding(jpeg_valido).shape == (512,)


# ------------------------------------------------------------
# Tradução das exceções do DeepFace
# ------------------------------------------------------------

def test_spoof_no_texto_ainda_vira_erro_proprio(monkeypatch, jpeg_valido):
    # Hoje quem estoura isto é o represent, não o extract_faces. A rede de
    # segurança existe pro dia em que o veredito subir pro extract_faces:
    # sem ela viraria "nenhum rosto detectado", a etapa que o reconhecimento
    # NÃO registra - a tentativa de burla sumiria do log.
    _usar(monkeypatch, _FakeDeepFace(erro="Spoof detected in the given image."))
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


# ------------------------------------------------------------
# Contrato com o DeepFace
# ------------------------------------------------------------

def test_vivacidade_vai_ligada_por_padrao(monkeypatch, jpeg_valido):
    fake = _usar(monkeypatch, _FakeDeepFace())
    calcular_embedding(jpeg_valido)
    assert fake.kwargs["anti_spoofing"] is True


def test_da_pra_desligar_a_vivacidade(monkeypatch, jpeg_valido):
    fake = _usar(monkeypatch, _FakeDeepFace())
    calcular_embedding(jpeg_valido, checar_vivacidade=False)
    assert fake.kwargs["anti_spoofing"] is False


def test_detector_roda_uma_vez_so(monkeypatch, jpeg_valido):
    # O embedding sai do recorte que o extract_faces já devolveu. Se este
    # "skip" cair, o detector roda duas vezes por leitura da porta - e a
    # segunda pode recortar diferente da que passou pela vivacidade.
    fake = _usar(monkeypatch, _FakeDeepFace())
    calcular_embedding(jpeg_valido)
    assert fake.represent_kwargs["detector_backend"] == "skip"


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
