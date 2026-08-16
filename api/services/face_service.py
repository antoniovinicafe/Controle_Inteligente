"""
Cálculo do vetor facial (embedding) a partir de uma imagem.

A imagem NUNCA é salva em disco/storage - só passa pela memória o
tempo suficiente pra extrair o vetor, que é o que vai pro banco.
"""

import os

import numpy as np
from deepface import DeepFace

MODELO = "Facenet512"  # gera vetor de 512 posições (bate com o schema.sql)

# Quanta certeza o anti-spoofing precisa ter pra NEGAR alguém.
#
# O MiniFASNet devolve três probabilidades - falso impresso, pessoa real,
# falso de tela - e o DeepFace, sozinho, recusa sempre que "real" não é a
# maior das três. Isso é decidir no voto de minerva: basta a soma das duas
# suspeitas passar da real, o que acontece direto com pouca luz, rosto de
# lado ou longe demais da câmera da porta. O resultado é negar quem tem
# direito de entrar, que é a falha cara aqui - a pessoa fica parada na
# frente da porta sem saber o que fazer.
#
# Com o limiar, a recusa só vale quando o modelo está convicto. 0.60 = "só
# nega se estiver 60% certo de que é fraude". Ajuste em ANTISPOOF_LIMIAR no
# .env: mais baixo aperta (barra mais), mais alto afrouxa, acima de 1.0
# desliga na prática.
#
# O número saiu de medição na porta, em 15/08/2026, e a história de como
# chegou aqui importa mais que ele:
#
#   com a câmera em 640x480, uma pessoa de verdade foi chamada de foto a
#   77%, 82% e 86%, e uma FOTO marcou 40% - as faixas se sobrepunham e
#   NENHUM limiar separava. Foi assim que uma foto abriu a porta com o
#   limiar em 0.90.
#
#   dobrando a captura pra 1280x720 (ver raspberry/totem.py), as faixas se
#   separaram: pessoa acusada de falsa a 43% e 58%, fotos a 68%, 99% e
#   100%. 0.60 fica no vão, encostado no limite de baixo de propósito -
#   foto entrando é falha de segurança, pessoa barrada é um segundo de
#   espera e a porta lê de novo.
#
# O que consertou não foi ajuste fino, foi resolução: o MiniFASNet decide
# por textura de pele num recorte de 80x80, e num rosto de ~100px não havia
# textura pra ver.
#
# ponytail: são poucas observações de cada lado, e o modelo é sensível ao
# ambiente. Toda leitura sai no console (`[vivacidade] ...`), então numa
# sala nova o certo é olhar os números de lá, não repetir estes.
#
# E uma assimetria que o limiar NÃO cobre: quando o modelo diz "pessoa"
# sobre uma foto, nenhum valor aqui a barra - o limiar só decide quando
# NEGAR. Contra esse caso só melhora de imagem ou de modelo.
LIMIAR_FALSIDADE = float(os.environ.get("ANTISPOOF_LIMIAR", "0.60"))


# Distância de cosseno máxima pra considerar que é a mesma pessoa.
# 0 = idêntico, 1 = sem relação. 0.30 é o limiar que o próprio DeepFace usa
# como padrão pro Facenet512 com métrica de cosseno. Subir aceita mais
# parecidos (mais falso positivo = deixa entrar quem não devia); baixar
# exige mais semelhança (mais falso negativo = barra quem devia).
#
# Mora aqui, e não na rota, porque agora são três os lugares que precisam
# da MESMA definição de "é a mesma pessoa": a porta, o cadastro e a decisão
# offline. Dois deles importam daqui justamente pra não poderem discordar.
LIMIAR_DISTANCIA = 0.30


def e_a_mesma_pessoa(distancia: float) -> bool:
    """
    Único lugar do sistema que decide "esses dois rostos são a mesma pessoa".

    A porta e o cadastro usam a MESMA definição, de propósito e em direções
    opostas: a porta libera quando é a mesma pessoa, o cadastro recusa. É essa
    simetria que sustenta a garantia de que duas contas nunca guardam rostos
    que o leitor confundiria - se as duas leituras pudessem discordar, daria
    pra cadastrar um par que a porta depois trocasse.
    """
    return distancia <= LIMIAR_DISTANCIA


# Acima disto, a suspeita é forte o bastante pra valer pros próximos
# segundos, e não só pra leitura em que apareceu (ver routes/faces.py).
#
# Começou em 0.90, com base em 15/08/2026: pessoa de verdade não passava de
# 58% e foto batia 99-100%. No dia seguinte, na mesma câmera, uma pessoa de
# verdade marcou 96% - e armou a janela, trancando quem tinha direito por
# 12 segundos. A separação de ontem era sorte de amostra pequena.
#
# 0.97 deixa só o quase-certo armar a janela. É apertado contra os 96%
# observados, e essa estreiteza é a informação importante aqui: neste
# hardware, os dois lados se sobrepõem. A janela reduz a chance da burla,
# não a elimina, e o preço de errar pra cima é trancar gente de verdade.
LIMIAR_SUSPEITA_FORTE = float(os.environ.get("ANTISPOOF_SUSPEITA_FORTE", "0.97"))


class RostoFalsoError(ValueError):
    """
    Achou um rosto, mas ele veio de uma foto impressa ou de uma tela.

    Precisa ser um erro DIFERENTE de "nenhum rosto detectado" porque os dois
    significam coisas opostas pra auditoria: um corredor vazio é rotina, uma
    foto erguida na frente da câmera é tentativa de burlar. Uma vira ruído
    que a gente descarta; a outra é exatamente o que o log existe pra guardar.

    Carrega a `certeza` do modelo porque quem chama precisa distinguir uma
    suspeita qualquer de uma certeza gritante - só a segunda vale pros
    segundos seguintes.
    """

    def __init__(self, mensagem, certeza: float = 0.0):
        super().__init__(mensagem)
        self.certeza = certeza

    @property
    def forte(self) -> bool:
        return self.certeza >= LIMIAR_SUSPEITA_FORTE


def calcular_embedding(imagem_bytes: bytes, checar_vivacidade: bool = True) -> np.ndarray:
    """
    Recebe os bytes de uma foto (rosto único, de preferência) e
    retorna o embedding facial como np.array de 512 floats.

    Levanta ValueError se nenhum rosto for detectado, e RostoFalsoError se o
    rosto encontrado for de foto/tela em vez de pessoa presente.

    São duas passadas de propósito, em vez de um `represent(anti_spoofing=True)`:
    o DeepFace, nesse atalho, só sabe estourar "spoof detected" e joga fora o
    quanto ele estava certo disso - e é esse número que decide se dá pra
    afrouxar (ver LIMIAR_FALSIDADE). Aqui o `extract_faces` acha o rosto e
    entrega o veredito com a certeza junto; o `represent` recebe o recorte
    pronto (`detector_backend="skip"`), então o detector roda uma vez só,
    igual antes.
    """
    import cv2

    arr = np.frombuffer(imagem_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Não foi possível ler a imagem enviada")

    try:
        rostos = DeepFace.extract_faces(
            img_path=img,
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

        # Rede de segurança: hoje quem estoura "spoof detected" é o
        # `represent`, não o `extract_faces` - mas se numa atualização o
        # veredito subir pra cá, ele tem que continuar sendo tratado como
        # burla. Sem isto viraria "nenhum rosto detectado", que é a etapa
        # que o reconhecimento NÃO registra: a tentativa sumiria do log.
        if "spoof detected" in msg:
            raise RostoFalsoError(
                "Isso parece uma foto ou uma tela, não uma pessoa"
            ) from e

        raise ValueError("Nenhum rosto detectado na imagem enviada") from e

    if len(rostos) > 1:
        raise ValueError(
            "Mais de um rosto detectado na imagem. Envie uma foto com apenas o seu rosto."
        )

    rosto = rostos[0]

    # `is_real` só existe quando a checagem foi pedida; ausente = não checou.
    if "is_real" in rosto:
        certeza = float(rosto.get("antispoof_score", 1.0))

        # Toda leitura sai no console do servidor, inclusive as que passam.
        # É a única janela pra calibrar: a recusa se conta sozinha (vai pro
        # access_logs), mas uma foto que ENTROU, ou uma pessoa que passou
        # raspando, não deixariam rastro nenhum. flush porque a saída do
        # waitress pode ficar presa no buffer e nunca aparecer.
        print(
            f"[vivacidade] {'pessoa' if rosto['is_real'] else 'FOTO/TELA'} "
            f"({certeza:.0%} de certeza, limiar {LIMIAR_FALSIDADE:.0%})",
            flush=True,
        )

        if rosto["is_real"] is False and certeza >= LIMIAR_FALSIDADE:
            # A certeza vai no texto porque é ela que se ajusta no .env, e
            # este texto é o que aparece no terminal do leitor e no
            # access_logs. Sem isso a calibração seria no chute.
            raise RostoFalsoError(
                f"Isso parece uma foto ou uma tela, não uma pessoa "
                f"({certeza:.0%} de certeza)",
                certeza=certeza,
            )

    # O recorte já vem do extract_faces em RGB e normalizado em [0,1], que é
    # exatamente o que o represent usaria internamente - por isso "skip".
    resultado = DeepFace.represent(
        img_path=rosto["face"],
        model_name=MODELO,
        detector_backend="skip",
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
