"""
Popula o banco com um semestre de mentira, pra demonstrar o app.

    venv/Scripts/python semear_demo.py             cria
    venv/Scripts/python semear_demo.py --sem-aula  cria so o historico
    venv/Scripts/python semear_demo.py --limpar    remove

Existe porque as telas mais interessantes do app - frequência por
disciplina, quantas faltas ainda cabem, permanência na lista de presença -
não mostram nada num banco recém-criado, e numa feira um app vazio parece
um app que não funciona.

Monta 8 aulas na turma Fetin: 6 já encerradas e 2 marcadas pra frente. Com
8 previstas o limite é 2 faltas, e os três alunos ficam em situações
diferentes de propósito - um tranquilo, um no limite, um estourado. Um
deles tem duas leituras na mesma aula, que é o que vira permanência.

Cria TAMBÉM uma aula acontecendo agora, e ela é o que faz a porta liberar
alguém durante a demonstração: sem aula em andamento naquela sala, todo
rosto reconhecido é negado por "não há aula agora". Ela entra com
turma_id nulo de propósito - a frequência conta as previstas pela turma,
e uma aula que acabou de começar contaria como falta de todo mundo e
estragaria justamente o quadro que as outras 8 montaram.

Use --sem-aula quando a aula for criada à mão pelo app na frente de
alguém. Duas aulas em andamento na MESMA sala se atrapalham: a porta
procura "aula acontecendo agora aqui" e fica com a que começou primeiro,
que seria esta - e não a que a pessoa acabou de ver ser criada.

TUDO que este script cria tem o título começando com "[TESTE]", e o
--limpar apaga exatamente isso e mais nada. Os ids de pessoa e turma são
os do banco de desenvolvimento; num banco novo, ajuste as constantes
abaixo.
"""
import sys
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras

from config import Config

MARCA = "[TESTE]"
TURMA = 3            # Fetin
PROFESSOR = "edb99959-706f-4b12-8194-c6cf58c66ff6"   # Antonio Teste
# A sala é lida do leitor cadastrado, não fixada aqui: a porta procura a
# aula pela sala do DISPOSITIVO, então um nome digitado à mão neste script
# precisa acertar o que está no banco. Já errou - o leitor foi renomeado
# de QUADRA pra FETIN e as aulas continuaram sendo criadas em QUADRA, o
# que faz a porta negar todo mundo por "nenhuma aula acontecendo agora".
SALA_PADRAO = "FETIN"

SAMUEL = "805dca65-7eb4-48af-ad2d-27c84f9fe089"
GABRIEL = "08db29cd-f48d-4f9a-966e-fdcbd72369b1"
PEDRO = "900a1757-5712-424c-8010-d57333f8ed5b"

# Quem esteve em cada uma das 6 aulas encerradas.
PRESENCAS = {
    SAMUEL: [0, 1, 2, 3, 4, 5],     # 6/6 - tranquilo
    GABRIEL: [0, 1, 2, 3],          # 4/6 - 2 faltas, no limite
    PEDRO: [0, 1, 2],               # 3/6 - 3 faltas, estourou
}


def sala_do_leitor(cur):
    """Onde o leitor da porta diz que está. É essa sala que a porta procura."""
    cur.execute("select local from dispositivos where ativo order by id limit 1")
    leitor = cur.fetchone()
    return leitor["local"] if leitor else SALA_PADRAO


def limpar(cur):
    cur.execute("select id from eventos where titulo like %s", (MARCA + "%",))
    ids = [r["id"] for r in cur.fetchall()]
    if not ids:
        print("nada pra limpar")
        return
    cur.execute("delete from access_logs where evento_id = any(%s)", (ids,))
    cur.execute("delete from evento_participantes where evento_id = any(%s)", (ids,))
    cur.execute("delete from eventos where id = any(%s)", (ids,))
    print(f"apagados {len(ids)} eventos de teste (e seus logs e presenças)")


def semear(cur, sala):
    agora = datetime.now(timezone.utc)
    criados = []

    for i in range(8):
        passada = i < 6
        # As encerradas ficam nas semanas anteriores; as futuras, nas
        # próximas. Sempre das 19h às 21h.
        dia = agora + timedelta(days=(i - 6) * 7 if passada else (i - 5) * 7)
        inicio = dia.replace(hour=19, minute=0, second=0, microsecond=0)
        fim = inicio + timedelta(hours=2)

        cur.execute(
            """
            insert into eventos (titulo, descricao, local, criador_id,
                                 data_inicio, data_fim, status)
            values (%s, %s, %s, %s, %s, %s, 'agendado')
            returning id
            """,
            (f"{MARCA} Cálculo I - aula {i + 1}",
             "Dados de teste. Apague com semear_teste.py --limpar",
             sala, PROFESSOR, inicio, fim),
        )
        evento_id = cur.fetchone()["id"]
        criados.append((evento_id, inicio, passada))

        for aluno, aulas in PRESENCAS.items():
            veio = passada and i in aulas
            cur.execute(
                """
                insert into evento_participantes
                    (evento_id, usuario_id, status, origem, turma_id, liberado_em)
                values (%s, %s, %s, 'turma', %s, %s)
                """,
                (evento_id, aluno,
                 "liberado" if veio else "convidado",
                 TURMA,
                 inicio + timedelta(minutes=5) if veio else None),
            )

            if not veio:
                continue

            # Uma leitura na chegada. Pro Samuel, mais uma perto do fim da
            # aula: é o par que vira permanência na tela.
            leituras = [inicio + timedelta(minutes=5)]
            if aluno == SAMUEL:
                leituras.append(fim - timedelta(minutes=7))

            for quando in leituras:
                cur.execute(
                    """
                    insert into access_logs (evento_id, usuario_id, tipo, status,
                                             dispositivo, motivo, criado_em)
                    values (%s, %s, 'facial', 'liberado', %s, %s, %s)
                    """,
                    (evento_id, aluno, "leitor-quadra",
                     'Acesso liberado para "Cálculo I"', quando),
                )

    print(f"criados {len(criados)} eventos ({sum(1 for c in criados if c[2])} encerrados)")


def aula_agora(cur, sala):
    """A aula em andamento que a porta procura durante a demonstração.

    Começa meia hora atrás pra já estar valendo no instante em que o
    script roda, e dura 4h pra cobrir a banca inteira sem ninguém ter que
    lembrar de recriá-la no meio.
    """
    agora = datetime.now(timezone.utc)
    cur.execute(
        """
        insert into eventos (titulo, descricao, local, criador_id,
                             data_inicio, data_fim, status)
        values (%s, %s, %s, %s, %s, %s, 'em_andamento')
        returning id
        """,
        (f"{MARCA} Aula de demonstracao",
         "Aula em andamento pra demonstrar a porta. Apague com --limpar",
         sala, PROFESSOR, agora - timedelta(minutes=30), agora + timedelta(hours=4)),
    )
    evento_id = cur.fetchone()["id"]

    # Só o professor e o Samuel entram na lista, e a escolha é o roteiro
    # da demonstração: são os dois com rosto cadastrado, então os dois
    # abrem a porta. Quem tiver rosto e NÃO estiver aqui é recusado por
    # "não está na lista" - a checagem mais difícil de mostrar, porque
    # exige alguém reconhecido e ainda assim negado.
    for pessoa in (PROFESSOR, SAMUEL):
        cur.execute(
            """
            insert into evento_participantes
                (evento_id, usuario_id, status, origem)
            values (%s, %s, 'convidado', 'manual')
            """,
            (evento_id, pessoa),
        )
    print(f"aula em andamento ate {(agora + timedelta(hours=4)).astimezone().strftime('%H:%M')}"
          f" na sala {sala} (evento {evento_id})")


def main():
    conn = psycopg2.connect(
        Config.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        with conn.cursor() as cur:
            limpar(cur)                      # sempre limpa antes: roda quantas vezes quiser
            if "--limpar" not in sys.argv:
                sala = sala_do_leitor(cur)
                semear(cur, sala)
                if "--sem-aula" not in sys.argv:
                    aula_agora(cur, sala)
                else:
                    print("sem aula em andamento: crie a sua pelo app, "
                          f"com o local {sala}")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
