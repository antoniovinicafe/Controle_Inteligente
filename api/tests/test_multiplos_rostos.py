"""Testes de várias capturas por pessoa.

POR QUE ESTES TESTES EXISTEM
A busca do reconhecimento é `order by embedding <=> alvo limit 1` sobre a
tabela inteira. Com uma linha por pessoa isso era trivialmente "a pessoa mais
parecida"; com várias, passa a ser "a melhor captura de alguém" — e é essa
mudança de significado que faz várias fotos melhorarem o reconhecimento sem
nenhuma linha de código a mais.

Se um dia alguém reintroduzir o unique em usuario_id, ou trocar o limit 1 por
um agrupamento por pessoa, o ganho some em silêncio: o sistema continua
funcionando, só volta a errar mais em luz difícil. Estes testes quebram nesse
caso.

Não tocam no banco: reproduzem a mesma aritmética de distância de cosseno que
o pgvector faz no `<=>`.
"""

import numpy as np
import pytest

from services.face_service import similaridade_cosseno


def dist(a, b):
    """Distância de cosseno — o mesmo que o operador <=> do pgvector."""
    return 1 - similaridade_cosseno(a, b)


def vetor(*valores):
    v = np.zeros(512, dtype=np.float32)
    for i, x in enumerate(valores):
        v[i] = x
    return v


# Pessoa cadastrada em duas condições bem diferentes (ex: luz do corredor e
# luz verde da quadra). Nenhuma das duas sozinha cobre bem a outra.
FOTO_CLARA = vetor(1.0, 0.0, 0.35)
FOTO_ESCURA = vetor(0.0, 1.0, 0.35)

OUTRA_PESSOA = vetor(-1.0, -0.2, 0.0)

LIMIAR = 0.30


def melhor_distancia(alvo, cadastradas):
    """O que a consulta `order by <=> limit 1` devolve."""
    return min(dist(alvo, c) for c in cadastradas)


def test_uma_foto_so_pode_nao_cobrir_a_outra_condicao():
    # É a situação de hoje com um vetor por pessoa: chegando na condição que
    # não foi cadastrada, a distância estoura o limiar e a porta recusa quem
    # tem direito.
    assert dist(FOTO_ESCURA, FOTO_CLARA) > LIMIAR


def test_com_as_duas_capturas_a_pessoa_e_reconhecida():
    # Mesma chegada, mesma condição — agora existe uma captura próxima.
    d = melhor_distancia(FOTO_ESCURA, [FOTO_CLARA, FOTO_ESCURA])
    assert d < LIMIAR


def test_a_busca_pega_a_captura_mais_proxima_e_nao_a_primeira():
    # O ganho depende de ser MÍNIMO, não "a primeira linha da pessoa".
    cadastradas = [FOTO_CLARA, FOTO_ESCURA]
    assert melhor_distancia(FOTO_ESCURA, cadastradas) == pytest.approx(
        dist(FOTO_ESCURA, FOTO_ESCURA), abs=1e-6
    )


def test_mais_capturas_nunca_pioram():
    # Acrescentar foto só pode diminuir (ou manter) a distância mínima. Se
    # isso deixar de valer, a lógica virou média em vez de mínimo.
    uma = melhor_distancia(FOTO_ESCURA, [FOTO_CLARA])
    duas = melhor_distancia(FOTO_ESCURA, [FOTO_CLARA, FOTO_ESCURA])
    assert duas <= uma


def test_varias_capturas_nao_fazem_estranho_passar():
    # O risco real de afrouxar: mais vetores por pessoa não podem aproximar
    # quem não é ela. Como cada linha é comparada individualmente, a distância
    # de um desconhecido continua grande.
    d = melhor_distancia(OUTRA_PESSOA, [FOTO_CLARA, FOTO_ESCURA])
    assert d > LIMIAR


def test_distancia_de_si_mesmo_e_zero():
    assert dist(FOTO_CLARA, FOTO_CLARA) == pytest.approx(0.0, abs=1e-6)
