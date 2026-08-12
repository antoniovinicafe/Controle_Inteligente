"""
Cálculo do vetor facial (embedding) a partir de uma imagem.

A imagem NUNCA é salva em disco/storage - só passa pela memória o
tempo suficiente pra extrair o vetor, que é o que vai pro banco.
"""

import numpy as np
from deepface import DeepFace

MODELO = "Facenet512"  # gera vetor de 512 posições (bate com o schema.sql)


def calcular_embedding(imagem_bytes: bytes) -> np.ndarray:
    """
    Recebe os bytes de uma foto (rosto único, de preferência) e
    retorna o embedding facial como np.array de 512 floats.

    Levanta ValueError se nenhum rosto for detectado na imagem.
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
        )
    except ValueError as e:
        # DeepFace levanta ValueError quando não detecta rosto na imagem
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
