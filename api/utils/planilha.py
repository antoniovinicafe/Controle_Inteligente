"""
CSV que o Excel brasileiro abre com duplo clique.

POR QUE NÃO É .xlsx
Uma planilha sem formatação, fórmula nem aba extra é uma tabela de texto -
e `csv` é biblioteca padrão. Gerar .xlsx exigiria o openpyxl, uma
dependência a mais no servidor pra entregar exatamente o mesmo conteúdo.
Se um dia a exportação precisar de coluna formatada ou várias abas, aí sim.

POR QUE NÃO É `csv.writer` E PRONTO
O padrão do módulo produz um arquivo que o Excel em português abre ERRADO,
de dois jeitos ao mesmo tempo, e os dois parecem defeito do sistema pra
quem recebe:

  - sem BOM, o Excel assume a codificação do Windows e "João" vira "JoÃ£o";
  - com vírgula, ele joga a linha inteira numa célula só, porque no
    Windows em pt-BR o separador de lista é o ponto e vírgula.

As duas correções são uma linha cada e são a diferença entre uma planilha
que abre pronta e uma que precisa de um assistente de importação.
"""

import csv
import io

from flask import Response


def resposta_csv(nome_arquivo: str, cabecalho: list, linhas: list) -> Response:
    """Monta o arquivo e devolve como download.

    `nome_arquivo` sem extensão. `linhas` é uma lista de listas, já na
    ordem do cabeçalho; None vira string vazia, que é como o Excel mostra
    célula sem valor.
    """
    buffer = io.StringIO()

    # O ponto e vírgula é o separador de lista do Windows em pt-BR.
    escritor = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow(["" if valor is None else valor for valor in linha])

    # O ﻿ é o BOM: é ele que faz o Excel reconhecer UTF-8 em vez de
    # supor a codificação local e estragar todo nome com acento.
    conteudo = "﻿" + buffer.getvalue()

    return Response(
        conteudo.encode("utf-8"),
        mimetype="text/csv; charset=utf-8",
        headers={
            # O filename sem acento é o que clientes antigos entendem; o
            # filename* carrega o nome de verdade pros que entendem UTF-8.
            "Content-Disposition": (
                f"attachment; filename={_sem_acento(nome_arquivo)}.csv; "
                f"filename*=UTF-8''{_url(nome_arquivo)}.csv"
            )
        },
    )


def formatar_hora(momento) -> str:
    """Hora local no formato que uma pessoa lê, ou vazio se não houve.

    Sem isso a célula viria em ISO 8601 com fuso, que o Excel trata como
    texto e não como hora - e o professor perde o que a coluna tinha de
    útil, que é bater o olho e ver quem chegou atrasado.
    """
    if not momento:
        return ""
    return momento.astimezone().strftime("%d/%m/%Y %H:%M")


def _sem_acento(txt: str) -> str:
    import unicodedata

    sem = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in sem)


def _url(txt: str) -> str:
    from urllib.parse import quote

    return quote(txt)
