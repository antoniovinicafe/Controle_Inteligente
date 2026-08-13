"""
Fila do que a porta decidiu enquanto o banco estava fora de alcance.

POR QUE ISTO É A PARTE QUE NÃO PODE FALTAR
Uma porta que libera sem registrar é pior do que uma porta que nega. Negar
é visível: a pessoa reclama na hora e alguém abre na mão. Liberar sem
gravar é silencioso — o aluno entrou, assistiu à aula, e no fim do mês a
frequência dele diz que faltou. Não há como reconstruir isso depois: a
imagem não é guardada e o veredito só existiu na memória do processo.

Por isso todo veredito tomado offline vira uma linha aqui, em arquivo, e
sobe pro Postgres quando a rede voltar.

O RELÓGIO É DO MOMENTO DA PORTA, NÃO DO ENVIO
O caminho online usa `now()` do Postgres nos dois lados — `criado_em` do
log e `liberado_em` da presença. Reaproveitar isso ao enviar carimbaria
todo mundo com a hora em que a internet voltou: uma turma inteira entrando
às 14h03 apareceria como presente às 19h40. Cada registro carrega o
instante em que a porta decidiu, e é esse que vai pro banco.

FORMATO
Uma linha JSON por veredito (JSONL), acrescentada no fim. Sem banco local,
sem esquema pra migrar: o arquivo é legível a olho nu no meio de uma
demonstração, que é exatamente quando alguém vai perguntar "e o que
aconteceu enquanto caiu?".
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ARQUIVO = Path(os.environ.get("FILA_OFFLINE", "pendentes.jsonl"))


def enfileirar(
    liberado: bool,
    motivo: str,
    dispositivo: str,
    evento_id=None,
    usuario_id=None,
    quando: datetime = None,
    caminho: Path = None,
) -> dict:
    """
    Guarda um veredito pra subir depois. Devolve o registro gravado.

    Mesma assinatura de decisão do `_resposta` do routes/faces.py, de
    propósito: quem chama não precisa pensar em dois formatos.
    """
    caminho = caminho or ARQUIVO
    registro = {
        "quando": (quando or datetime.now(timezone.utc)).isoformat(),
        "liberado": liberado,
        "motivo": motivo,
        "dispositivo": dispositivo,
        "evento_id": evento_id,
        "usuario_id": str(usuario_id) if usuario_id else None,
    }
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro) + "\n")
        # Sem o flush a linha pode ficar no buffer do processo. Queda de
        # energia é justamente um dos motivos de a rede ter caído.
        f.flush()
    return registro


def pendentes(caminho: Path = None) -> list[dict]:
    """O que ainda não subiu, na ordem em que aconteceu."""
    caminho = caminho or ARQUIVO
    if not caminho.exists():
        return []
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    # Linha quebrada (queda no meio da escrita) não pode impedir as outras
    # de subir: a última é a única que corre esse risco, e perdê-la é menos
    # grave do que perder o arquivo inteiro.
    registros = []
    for linha in linhas:
        if not linha.strip():
            continue
        try:
            registros.append(json.loads(linha))
        except json.JSONDecodeError:
            continue
    return registros


def enviar(cur, caminho: Path = None) -> int:
    """
    Sobe a fila pro Postgres, numa transação só. Devolve quantos subiram.

    Quem chama é dono do commit — se ele falhar, o arquivo continua onde
    está e a próxima tentativa manda tudo de novo.

    ponytail: entre o commit e o apagar do arquivo existe uma janela em que
    uma queda duplicaria os logs no reenvio. A presença é idempotente (é um
    update pro mesmo estado), e log repetido é ruído que se enxerga; perder
    presença, não. Se um dia incomodar, o caminho é um id por registro e um
    unique no banco.
    """
    caminho = caminho or ARQUIVO
    fila = pendentes(caminho)
    if not fila:
        return 0

    for r in fila:
        cur.execute(
            """
            insert into access_logs
                (evento_id, usuario_id, tipo, status, dispositivo, motivo, criado_em)
            values (%s, %s, 'facial', %s, %s, %s, %s)
            """,
            (
                r["evento_id"],
                r["usuario_id"],
                "liberado" if r["liberado"] else "negado",
                r["dispositivo"],
                r["motivo"],
                r["quando"],
            ),
        )

        # Presença só existe quando houve liberação numa aula identificada.
        if r["liberado"] and r["evento_id"] and r["usuario_id"]:
            cur.execute(
                """
                update evento_participantes
                set status = 'liberado', liberado_em = %s
                where evento_id = %s and usuario_id = %s
                """,
                (r["quando"], r["evento_id"], r["usuario_id"]),
            )

    caminho.unlink()
    return len(fila)
