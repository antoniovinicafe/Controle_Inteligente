"""Testes da expansão de aula recorrente.

POR QUE ESTES TESTES EXISTEM
A tela de criar aula recorrente mostra "VAI CRIAR — 15 aulas" antes de o
professor tocar no botão. Esse número é calculado no aplicativo
(`contarOcorrencias`, em app/lib/models/recorrencia.dart, com 10 testes
próprios). Quem cria de verdade é `expandir_ocorrencias`, aqui no servidor.

São duas implementações da mesma regra, em duas linguagens. Se elas
discordarem, o app promete um número e o servidor faz outro — e a criação é
em lote, enquanto desfazer é de um em um. Por isso os casos abaixo são
propositalmente OS MESMOS do lado Dart: os dois arquivos precisam continuar
concordando.

Rodar:  cd api && venv/Scripts/python -m pytest tests -v
"""

from datetime import date
from zoneinfo import ZoneInfo

from routes.recorrencias import expandir_ocorrencias

SEG = date(2026, 8, 10)   # uma segunda-feira


def qtd(dias, inicio, fim):
    return len(expandir_ocorrencias(dias, inicio, fim))


def test_seg_e_qua_em_oito_dias_da_tres():
    # O caso que foi conferido por curl contra o banco quando a recorrência
    # foi construída: 10/08 seg, 12/08 qua, 17/08 seg.
    assert qtd([1, 3], SEG, date(2026, 8, 17)) == 3


def test_conta_as_duas_pontas_do_intervalo():
    # Segunda a segunda, só segundas: a de abertura e a de fechamento.
    assert qtd([1], SEG, date(2026, 8, 17)) == 2


def test_um_dia_so_que_bate():
    assert qtd([1], SEG, SEG) == 1


def test_um_dia_so_que_nao_bate():
    assert qtd([3], SEG, SEG) == 0


def test_sem_dia_escolhido_nao_gera_nada():
    assert qtd([], SEG, date(2026, 12, 31)) == 0


def test_intervalo_invertido_nao_gera_nada():
    assert qtd([1], date(2026, 8, 17), SEG) == 0


def test_semestre_de_seg_qua_sex():
    # 10/08 (seg) a 11/12 (sex): 17 semanas cheias = 51, mais 07, 09 e 11/12.
    assert qtd([1, 3, 5], SEG, date(2026, 12, 11)) == 54


def test_atravessa_a_virada_do_mes():
    # 28/08 (sex) a 04/09 (sex), só sextas.
    assert qtd([5], date(2026, 8, 28), date(2026, 9, 4)) == 2


def test_todos_os_dias_conta_o_intervalo_inteiro():
    assert qtd([1, 2, 3, 4, 5, 6, 7], SEG, date(2026, 8, 16)) == 7


def test_devolve_as_datas_certas_e_em_ordem():
    datas = expandir_ocorrencias([1, 3], SEG, date(2026, 8, 17))
    assert datas == [date(2026, 8, 10), date(2026, 8, 12), date(2026, 8, 17)]


def test_isoweekday_bate_com_o_rotulo_da_interface():
    # nomesDiasSemana no Dart é {1:'Seg', ..., 7:'Dom'}. Se esta correspondência
    # quebrar, o professor marca "Seg" e a aula cai na terça.
    assert date(2026, 8, 10).isoweekday() == 1   # segunda
    assert date(2026, 8, 16).isoweekday() == 7   # domingo


def test_caso_da_tela_quinze_aulas():
    # Exatamente o que a interface mostrou ao ser testada no emulador:
    # Seg+Qua, de 12/08 a 30/09 -> "VAI CRIAR 15 aulas".
    assert qtd([1, 3], date(2026, 8, 12), date(2026, 9, 30)) == 15


# ------------------------------------------------------------
# O fuso da hora marcada
# ------------------------------------------------------------

def test_a_hora_marcada_carrega_o_fuso():
    """A hora que o professor digita é local, e precisa dizer isso.

    `eventos.data_inicio` é timestamptz. Um datetime sem fuso entregue a ele
    é lido pelo fuso da sessão do Postgres, que no Supabase é UTC - e a aula
    marcada pras 20:47 nascia às 17:47, três horas no passado, já encerrada.
    Todo mundo da turma levava falta de uma aula que nunca aconteceu.
    Aconteceu de verdade em 17/08/2026, com a turma t06.

    Este teste falha se alguém tirar o tzinfo de volta.
    """
    from datetime import datetime, time
    from routes.recorrencias import FUSO

    marcado = datetime.combine(date(2026, 8, 17), time(20, 47), tzinfo=FUSO)

    assert marcado.utcoffset() is not None, "hora sem fuso: o Postgres vai supor UTC"
    assert marcado.astimezone(ZoneInfo("UTC")).hour == 23, "20:47 em Brasília são 23:47 UTC"
