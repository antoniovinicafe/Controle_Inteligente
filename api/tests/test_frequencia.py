"""A conta que decide se alguém reprova por falta.

POR QUE ESTES TESTES EXISTEM
Até 13/08/2026 o app mostrava um percentual só, somando todas as turmas. É
academicamente sem sentido: reprovação por falta é POR disciplina. Um aluno
com 80% no agregado pode estar com 50% em Cálculo I, e o app dizia que
estava tudo bem — o tipo de erro que só aparece no fim do semestre, quando
não dá mais pra corrigir.

E há uma segunda armadilha, mais sutil, na hora de dizer "quantas faltas
ainda cabem": a conta tem que sair das aulas PREVISTAS do semestre, não das
já dadas. Faltar 1 de 2 aulas dadas é 50% de presença e não é reprovação
nenhuma se o semestre tem 30 aulas. Calcular sobre as encerradas faz o app
gritar em março com quem está bem — e app que grita à toa é app que se
aprende a ignorar.

São contas puras: nada de banco.
"""

import pytest

from routes.usuarios import MINIMO_FREQUENCIA, resumo_frequencia


# ------------------------------------------------------------
# O retrato do passado
# ------------------------------------------------------------

def test_percentual_das_aulas_ja_dadas():
    r = resumo_frequencia(total=10, presencas=8, previstas=30)
    assert r["percentual"] == 80
    assert r["faltas"] == 2


def test_sem_aula_encerrada_o_percentual_e_nulo():
    # 0% mentiria: quem não teve aula nenhuma não faltou a nada.
    r = resumo_frequencia(total=0, presencas=0, previstas=30)
    assert r["percentual"] is None


# ------------------------------------------------------------
# O número que dá pra agir em cima
# ------------------------------------------------------------

def test_quantas_faltas_ainda_cabem():
    # 30 aulas previstas, 75% de piso -> cabem 7 faltas no semestre. Com 2
    # gastas, sobram 5.
    r = resumo_frequencia(total=10, presencas=8, previstas=30)
    assert r["limite_faltas"] == 7
    assert r["faltas_restantes"] == 5


def test_o_limite_trunca_pra_baixo():
    # 30 * 0,25 = 7,5. Sete faltas e meia não existe, e arredondar pra cima
    # daria uma falta de brinde contra a regra.
    assert resumo_frequencia(0, 0, 30)["limite_faltas"] == 7


def test_meia_duzia_de_faltas_cedo_nao_e_reprovacao():
    # A armadilha: 1 falta em 2 aulas dadas é 50% de presença. Se a conta
    # saísse das aulas encerradas, este aluno estaria "reprovado" em março.
    r = resumo_frequencia(total=2, presencas=1, previstas=30)
    assert r["percentual"] == 50
    assert r["reprovado_por_falta"] is False
    assert r["faltas_restantes"] == 6


def test_passar_do_limite_e_reprovacao():
    r = resumo_frequencia(total=30, presencas=22, previstas=30)
    assert r["faltas"] == 8          # cabiam 7
    assert r["reprovado_por_falta"] is True
    assert r["faltas_restantes"] == 0


def test_exatamente_no_limite_ainda_passa():
    # 7 faltas em 30 previstas = 76,7% de presença, acima do piso. O erro
    # de sinal aqui reprovaria quem tem direito.
    r = resumo_frequencia(total=30, presencas=23, previstas=30)
    assert r["faltas"] == 7
    assert r["reprovado_por_falta"] is False
    assert r["percentual"] >= MINIMO_FREQUENCIA * 100


def test_faltas_restantes_nunca_e_negativo():
    # Vira texto na tela ("você ainda pode faltar -3 vezes" seria ridículo).
    assert resumo_frequencia(total=30, presencas=10, previstas=30)["faltas_restantes"] == 0


# ------------------------------------------------------------
# Semestre mal começado: o caso que os testes acima não pegavam
# ------------------------------------------------------------

def test_sem_aulas_previstas_ninguem_reprova():
    # Turma recém-criada, nenhuma aula agendada: limite 0, e faltas 0 não
    # podem virar reprovação.
    r = resumo_frequencia(total=0, presencas=0, previstas=0)
    assert r["limite_faltas"] == 0
    assert r["reprovado_por_falta"] is False


def test_faltar_a_unica_aula_marcada_nao_e_reprovacao():
    # ISTO ACONTECEU DE VERDADE. Rodando a consulta contra o banco em
    # 13/08/2026, as três pessoas cadastradas tinham 1 aula e 1 falta cada,
    # e todas saíram "reprovadas por falta".
    #
    # A causa: `previstas` são as aulas JÁ CRIADAS, não o tamanho do
    # semestre - o sistema não tem como saber quantas aulas a disciplina vai
    # ter. Com 1 aula marcada o limite é zero, e qualquer falta estoura.
    # Formalmente é verdade (0% de presença); na prática, é acusar de
    # reprovado quem perdeu a primeira aula de fevereiro.
    r = resumo_frequencia(total=1, presencas=0, previstas=1)
    assert r["percentual"] == 0
    assert r["reprovado_por_falta"] is False


def test_so_afirma_reprovacao_quando_cabia_alguma_falta():
    # A regra que sustenta o teste acima: enquanto o professor não marcar
    # aulas o bastante pra caber UMA falta, não há o que afirmar.
    for previstas in range(0, 4):          # limite 0
        assert resumo_frequencia(previstas, 0, previstas)["reprovado_por_falta"] is False
    # Com 8 aulas cabem 2 faltas; 3 estouram e aí sim vale dizer.
    assert resumo_frequencia(8, 5, 8)["reprovado_por_falta"] is True
