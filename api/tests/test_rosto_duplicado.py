"""Um rosto pertence a uma conta só.

POR QUE ESTES TESTES EXISTEM
Sem a checagem no cadastro dá pra registrar o rosto de um colega na própria
conta. Ele chega na porta, o leitor procura o vetor mais próximo, acha a linha
de quem cadastrou e marca a pessoa errada como presente - o "assina a lista por
mim" de sempre, agora feito pelo sistema que existia pra impedi-lo. E é uma
fraude silenciosa: ninguém é barrado, o log parece normal, só o nome está
trocado.

A garantia que os testes prendem é a invariante, não a mensagem de erro: depois
de qualquer sequência de cadastros aceitos, não existem duas contas com rostos
que a porta confundiria. Vale porque cadastro e porta usam a MESMA função
`e_a_mesma_pessoa` - o dia em que alguém afrouxar só um dos lados, o último
teste quebra.

Não tocam no banco: reproduzem a aritmética de distância de cosseno do operador
`<=>` do pgvector, igual test_multiplos_rostos.py.
"""

import itertools
import math

import numpy as np

from routes.faces import LIMIAR_DISTANCIA, e_a_mesma_pessoa
from services.face_service import similaridade_cosseno


def dist(a, b):
    """Distância de cosseno — o mesmo que o operador <=> do pgvector."""
    return 1 - similaridade_cosseno(a, b)


def vetor(*valores):
    v = np.zeros(512, dtype=np.float32)
    for i, x in enumerate(valores):
        v[i] = x
    return v


def angulo(distancia):
    """Vetor a exatamente `distancia` de ROSTO_A — pra testar perto do limiar."""
    cos = 1 - distancia
    return vetor(cos, math.sqrt(1 - cos**2))


ROSTO_A = vetor(1.0, 0.0)
ROSTO_A_OUTRA_LUZ = vetor(1.0, 0.1)      # mesma pessoa, outra captura
ROSTO_B = vetor(0.0, 1.0)                # outra pessoa, bem diferente

ANA, BRUNO, CARLA = "ana", "bruno", "carla"


def tentar_cadastrar(banco, usuario, embedding):
    """
    Reproduz a regra de `cadastrar_rosto`: recusa se o rosto mais próximo entre
    os de OUTRAS contas for próximo demais. As capturas da própria pessoa ficam
    de fora — senão a segunda foto de alguém seria recusada por parecer com a
    primeira, que é exatamente o que se quer permitir.
    """
    de_outros = [e for u, e in banco if u != usuario]
    if de_outros and e_a_mesma_pessoa(min(dist(embedding, e) for e in de_outros)):
        return False
    banco.append((usuario, embedding))
    return True


def test_segunda_foto_da_mesma_pessoa_e_aceita():
    # O caso que a checagem NÃO pode atrapalhar: várias capturas por pessoa é
    # justamente o recurso que melhora o reconhecimento.
    banco = [(ANA, ROSTO_A)]
    assert tentar_cadastrar(banco, ANA, ROSTO_A_OUTRA_LUZ) is True
    assert len(banco) == 2


def test_outra_conta_nao_pode_reivindicar_o_mesmo_rosto():
    # A fraude: Bruno cadastra o rosto da Ana pra receber a presença dela.
    banco = [(ANA, ROSTO_A)]
    assert tentar_cadastrar(banco, BRUNO, ROSTO_A_OUTRA_LUZ) is False
    assert len(banco) == 1


def test_pessoa_diferente_entra_normalmente():
    banco = [(ANA, ROSTO_A)]
    assert tentar_cadastrar(banco, BRUNO, ROSTO_B) is True


def test_nao_da_pra_escapar_pela_segunda_foto():
    # Bruno cadastra o rosto dele, depois tenta acrescentar o da Ana como
    # "outra captura sua". A checagem olha cada foto nova, não só a primeira.
    banco = [(ANA, ROSTO_A), (BRUNO, ROSTO_B)]
    assert tentar_cadastrar(banco, BRUNO, ROSTO_A_OUTRA_LUZ) is False


def test_quase_no_limiar():
    # Dentro do limiar recusa, fora aceita. Prende o sentido da comparação:
    # trocar <= por >= inverteria tudo sem quebrar nenhum teste acima.
    banco = [(ANA, ROSTO_A)]
    assert tentar_cadastrar(banco, BRUNO, angulo(LIMIAR_DISTANCIA - 0.01)) is False
    assert tentar_cadastrar(banco, CARLA, angulo(LIMIAR_DISTANCIA + 0.01)) is True


def test_invariante_contas_distintas_nunca_ficam_confundiveis():
    # A garantia de verdade, e a única que interessa: qualquer que seja a
    # ordem das tentativas, o que sobra no banco não tem par de contas
    # diferentes que a porta trocaria.
    banco = []
    tentativas = [
        (ANA, ROSTO_A),
        (BRUNO, ROSTO_A_OUTRA_LUZ),   # recusada
        (BRUNO, ROSTO_B),
        (ANA, ROSTO_A_OUTRA_LUZ),     # segunda foto da Ana, aceita
        (CARLA, angulo(0.1)),         # parecida demais com a Ana, recusada
        (CARLA, angulo(0.9)),
    ]
    for usuario, rosto in tentativas:
        tentar_cadastrar(banco, usuario, rosto)

    for (u1, e1), (u2, e2) in itertools.combinations(banco, 2):
        if u1 != u2:
            assert not e_a_mesma_pessoa(dist(e1, e2)), (
                f"{u1} e {u2} ficaram a uma distância que a porta confundiria"
            )


def test_o_que_o_cadastro_recusa_e_o_que_a_porta_liberaria():
    # A simetria que sustenta a invariante. Se o cadastro passar a usar um
    # limiar próprio, um par recusado aqui poderia ser um par que a porta
    # distingue bem (chateação à toa) - ou, pior, um par aceito aqui poderia
    # ser um que a porta confunde.
    d = dist(ROSTO_A, ROSTO_A_OUTRA_LUZ)
    assert e_a_mesma_pessoa(d), "cadastro recusaria"
    assert d <= LIMIAR_DISTANCIA, "porta liberaria como sendo a mesma pessoa"
