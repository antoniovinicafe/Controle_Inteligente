"""
Cálculo do vetor facial (embedding) a partir de uma imagem.

A imagem NUNCA é salva em disco/storage - só passa pela memória o
tempo suficiente pra extrair o vetor, que é o que vai pro banco.
"""

import numpy as np
from deepface import DeepFace

MODELO = "Facenet512"  # gera vetor de 512 posições (bate com o schema.sql)


class RostoFalsoError(ValueError):
    """
    Achou um rosto, mas ele veio de uma foto impressa ou de uma tela.

    Precisa ser um erro DIFERENTE de "nenhum rosto detectado" porque os dois
    significam coisas opostas pra auditoria: um corredor vazio é rotina, uma
    foto erguida na frente da câmera é tentativa de burlar. Uma vira ruído
    que a gente descarta; a outra é exatamente o que o log existe pra guardar.
    """


def calcular_embedding(imagem_bytes: bytes, checar_vivacidade: bool = True) -> np.ndarray:
    """
    Recebe os bytes de uma foto (rosto único, de preferência) e
    retorna o embedding facial como np.array de 512 floats.

    Levanta ValueError se nenhum rosto for detectado, e RostoFalsoError se o
    rosto encontrado for de foto/tela em vez de pessoa presente.

    A checagem de vivacidade usa o modelo anti-spoofing que já vem no
    DeepFace (MiniFASNet): ele olha textura e reflexo pra distinguir pele de
    papel ou de LCD. Sem isso, levantar o celular com a foto de alguém
    cadastrado abre a porta - que é a primeira coisa que um avaliador tenta.
    """
    import cv2

    arr = np.frombuffer(imagem_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Não foi possível ler a imagem enviada")

    try:
        resultado = DeepFace.represent(
            img_path=img,
            model_name=MODELO,
            enforce_detection=True,  # falha se não achar rosto (evita cadastro vazio)
            anti_spoofing=checar_vivacidade,
        )
    except ValueError as e:
        msg = str(e).lower()

        # Falta o torch: o DeepFace avisa com "...to use face anti spoofing
        # module", que contém "spoof". Procurar só por "spoof" fazia esta
        # falha de instalação virar veredito de burla - a porta negaria TODA
        # pessoa dizendo "isso parece uma foto", sem pista da causa real.
        # Por isso vira RuntimeError: é defeito de servidor, não decisão
        # sobre quem está na frente da câmera, e tem que estourar 500 em vez
        # de virar um NEGADO plausível.
        if "install torch" in msg or "anti spoofing module" in msg:
            raise RuntimeError(
                "Anti-spoofing indisponível no servidor: falta a dependência "
                "torch (pip install -r requirements.txt)"
            ) from e

        # O DeepFace usa ValueError pros dois casos e só o texto distingue.
        # Frágil por natureza, então o teste em tests/ prende esta tradução:
        # se a mensagem mudar numa atualização, o teste quebra em vez de a
        # porta passar a aceitar foto silenciosamente.
        if "spoof detected" in msg:
            raise RostoFalsoError(
                "Isso parece uma foto ou uma tela, não uma pessoa"
            ) from e

        raise ValueError("Nenhum rosto detectado na imagem enviada") from e

    if len(resultado) > 1:
        raise ValueError(
            "Mais de um rosto detectado na imagem. Envie uma foto com apenas o seu rosto."
        )

    embedding = np.array(resultado[0]["embedding"], dtype=np.float32)
    return embedding


def similaridade_cosseno(a: np.ndarray, b: np.ndarray) -> float:
    """
    Útil mais pra frente, quando a Raspberry for comparar um rosto
    capturado contra os embeddings cadastrados no banco.
    1.0 = idêntico, 0.0 = totalmente diferente.
    """
    a, b = np.asarray(a), np.asarray(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
