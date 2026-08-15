"""
Popula o banco com um semestre de mentira, pra demonstrar o app.

    venv/Scripts/python semear_demo.py            cria
    venv/Scripts/python semear_demo.py --limpar   remove

Existe porque as telas mais interessantes do app - frequência por
disciplina, quantas faltas ainda cabem, permanência na lista de presença -
não mostram nada num banco recém-criado, e numa feira um app vazio parece
um app que não funciona.

Monta 8 aulas na turma Fetin: 6 já encerradas e 2 marcadas pra frente. Com
8 previstas o limite é 2 faltas, e os três alunos ficam em situações
diferentes de propósito - um tranquilo, um no limite, um estourado. Um
deles tem duas leituras na mesma aula, que é o que vira permanência.

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
SALA = "QUADRA"      # mesma sala do leitor cadastrado

SAMUEL = "805dca65-7eb4-48af-ad2d-27c84f9fe089"
GABRIEL = "08db29cd-f48d-4f9a-966e-fdcbd72369b1"
PEDRO = "900a1757-5712-424c-8010-d57333f8ed5b"

# Quem esteve em cada uma das 6 aulas encerradas.
PRESENCAS = {
    SAMUEL: [0, 1, 2, 3, 4, 5],     # 6/6 - tranquilo
    GABRIEL: [0, 1, 2, 3],          # 4/6 - 2 faltas, no limite
    PEDRO: [0, 1, 2],               # 3/6 - 3 faltas, estourou
}


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


def semear(cur):
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
             SALA, PROFESSOR, inicio, fim),
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


def main():
    conn = psycopg2.connect(
        Config.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        with conn.cursor() as cur:
            limpar(cur)                      # sempre limpa antes: roda quantas vezes quiser
            if "--limpar" not in sys.argv:
                semear(cur)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
