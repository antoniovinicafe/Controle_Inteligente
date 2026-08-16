"""
Cópia local do que a porta precisa pra decidir sem internet.

O PROBLEMA
O desenho parece local - a Raspberry fala com o Flask no PC, os dois na
mesma rede - mas todo veredito da porta é uma consulta ao Postgres do
Supabase, que fica na AWS em São Paulo. Cai a internet do prédio e a porta
para, mesmo com a Pi e o servidor lado a lado, funcionando, olhando um pro
outro.

POR QUE O CACHE FICA AQUI, E NÃO NA PI
A ideia anterior era a Pi guardar os rostos. Isso obriga a Pi a calcular o
embedding sozinha - Facenet512 mais o anti-spoofing rodando nela - que é
exatamente o que ela não faz, e o motivo de ela ser burra: só tira foto e
pergunta. Como o elo que quebra é a internet, e não a rede local, basta o
FLASK conseguir responder sem sair do prédio. A Pi não muda em nada.

O QUE ENTRA NA CÓPIA
Só o que as três perguntas da porta consultam: os rostos cadastrados, os
eventos da janela de hoje com seus participantes, e os dispositivos (pra
autenticar o leitor, que também é uma consulta ao banco). Nada de histórico,
nada de turmas - o que não decide acesso não precisa estar aqui.

O arquivo tem hash de chave de dispositivo e vetores faciais: fica fora do
git (ver .gitignore) e não sai da máquina do servidor.

ESTADO: as funções de leitura abaixo já respondem às três perguntas, e os
testes prendem a lógica. Falta ligar no `/faces/recognize` e no
`device_auth` como plano B, e enfileirar presença e log gerados offline pra
subirem quando a rede voltar. Enquanto isso não existir, isto aqui não
decide nada - é peça pronta, não sistema pronto.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Fica ao lado do app.py por padrão. Vale um caminho absoluto no .env se o
# servidor rodar de outro diretório.
ARQUIVO = Path(os.environ.get("CACHE_LOCAL", "cache_local.json"))

# Quanto tempo pra frente os eventos entram na cópia. Dois dias cobre "a
# rede caiu de manhã e a aula é de tarde" e o dia seguinte inteiro, sem
# fazer o arquivo crescer com o semestre.
DIAS_ADIANTE = 2


# ------------------------------------------------------------
# Gerar
# ------------------------------------------------------------

def gerar(cur) -> dict:
    """
    Monta a cópia a partir do Postgres. Recebe um cursor já aberto pra
    quem chama decidir sobre transação e conexão.

    O `normaliza_local` é calculado AQUI, pelo Postgres, e guardado pronto.
    É a mesma função que a consulta online usa nos dois lados da comparação
    - reescrevê-la em Python seria criar uma segunda definição de "mesma
    sala" pra divergir da primeira em algum acento.
    """
    cur.execute(
        """
        select f.usuario_id::text as usuario_id, p.nome, f.embedding::text as embedding
        from faces f join profiles p on p.id = f.usuario_id
        """
    )
    faces = [
        {
            "usuario_id": r["usuario_id"],
            "nome": r["nome"],
            # pgvector devolve '[0.1,0.2,...]', que é JSON válido.
            "embedding": json.loads(r["embedding"]),
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        """
        select id, nome, local, normaliza_local(local) as local_norm,
               chave_hash, ativo
        from dispositivos
        """
    )
    dispositivos = [dict(r) for r in cur.fetchall()]

    cur.execute(
        f"""
        select id, titulo, local, normaliza_local(local) as local_norm,
               data_inicio, data_fim
        from eventos
        where status in ('agendado', 'em_andamento')
          and data_fim >= now()
          and data_inicio <= now() + interval '{DIAS_ADIANTE} days'
        order by data_inicio
        """
    )
    eventos = [dict(r) for r in cur.fetchall()]

    if eventos:
        cur.execute(
            "select evento_id, usuario_id::text as usuario_id "
            "from evento_participantes where evento_id = any(%s)",
            ([e["id"] for e in eventos],),
        )
        convidados = {}
        for r in cur.fetchall():
            convidados.setdefault(r["evento_id"], []).append(r["usuario_id"])
        for e in eventos:
            e["participantes"] = convidados.get(e["id"], [])
            e["data_inicio"] = e["data_inicio"].isoformat()
            e["data_fim"] = e["data_fim"].isoformat()

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "faces": faces,
        "dispositivos": dispositivos,
        "eventos": eventos,
    }


def salvar(copia: dict, caminho: Path = None) -> Path:
    caminho = caminho or ARQUIVO
    # Grava em outro arquivo e só então renomeia: se a energia cair no meio
    # da escrita, o cache antigo continua íntegro. Um JSON pela metade seria
    # pior que um desatualizado - a porta não abriria de jeito nenhum.
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(copia), encoding="utf-8")
    temporario.replace(caminho)
    return caminho


def carregar(caminho: Path = None) -> dict | None:
    caminho = caminho or ARQUIVO
    if not caminho.exists():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def idade_em_horas(copia: dict, agora: datetime = None) -> float:
    agora = agora or datetime.now(timezone.utc)
    return (agora - datetime.fromisoformat(copia["gerado_em"])).total_seconds() / 3600


# ------------------------------------------------------------
# Ler - as mesmas três perguntas que o /faces/recognize faz em SQL
# ------------------------------------------------------------

def vizinho_mais_proximo(copia: dict, embedding) -> tuple[dict, float] | None:
    """
    O equivalente ao `order by embedding <=> alvo limit 1` do pgvector.

    ponytail: varredura de todos os vetores em numpy. É o que o Postgres já
    faz hoje (o índice ivfflat foi removido de propósito, ver schema.sql) e
    com dezenas de rostos custa microssegundos. Se um dia forem milhares,
    o caminho é guardar a matriz pronta em .npy, não um índice aproximado.
    """
    if not copia["faces"]:
        return None

    alvo = np.asarray(embedding, dtype=np.float32)
    matriz = np.array([f["embedding"] for f in copia["faces"]], dtype=np.float32)

    # Distância de cosseno, igual ao operador <=>: 1 - (a·b)/(|a||b|).
    normas = np.linalg.norm(matriz, axis=1) * np.linalg.norm(alvo)
    distancias = 1 - (matriz @ alvo) / normas

    i = int(np.argmin(distancias))
    return copia["faces"][i], float(distancias[i])


def evento_agora(copia: dict, local_norm: str, agora: datetime = None) -> dict | None:
    """Aula acontecendo neste instante naquela sala, a mais antiga primeiro."""
    agora = agora or datetime.now(timezone.utc)
    for e in copia["eventos"]:
        if e["local_norm"] != local_norm:
            continue
        if datetime.fromisoformat(e["data_inicio"]) <= agora <= datetime.fromisoformat(e["data_fim"]):
            return e
    return None


def esta_na_lista(evento: dict, usuario_id: str) -> bool:
    return str(usuario_id) in evento.get("participantes", [])


def dispositivo_por_hash(copia: dict, chave_hash: str) -> dict | None:
    for d in copia["dispositivos"]:
        if d["chave_hash"] == chave_hash:
            return d
    return None


# ------------------------------------------------------------
# Decidir - a mesma sequência do /faces/recognize, sem banco
# ------------------------------------------------------------

def decidir(copia: dict, embedding, dispositivo: dict, agora: datetime = None) -> dict:
    """
    Quem é, tem aula aqui agora, foi convidado - nesta ordem, e qualquer não
    encerra. É a mesma sequência que a rota faz em SQL, com as mesmas
    mensagens: o totem da porta mostra esse texto, e ele não pode mudar de
    forma dependendo de a internet estar de pé.

    `e_a_mesma_pessoa` vem do face_service justamente pra que o limiar da
    decisão offline não possa divergir do online.
    """
    from services.face_service import e_a_mesma_pessoa

    vizinho = vizinho_mais_proximo(copia, embedding)
    if not vizinho:
        print("[identidade] cópia local sem nenhum rosto", flush=True)
        return {"liberado": False, "motivo": "Rosto não reconhecido", "etapa": "identidade"}

    # Igual ao caminho online: a distância sai no console tenha batido ou
    # não, senão calibrar o limiar seria chute.
    print(f"[identidade] {'bateu' if e_a_mesma_pessoa(vizinho[1]) else 'LONGE'} "
          f"{vizinho[1]:.3f} com {vizinho[0]['nome']} (cópia local)", flush=True)

    if not e_a_mesma_pessoa(vizinho[1]):
        return {"liberado": False, "motivo": "Rosto não reconhecido", "etapa": "identidade"}

    face, _ = vizinho
    evento = evento_agora(copia, dispositivo["local_norm"], agora)
    if not evento:
        return {
            "liberado": False,
            "motivo": f"Nenhuma aula acontecendo agora em {dispositivo['local']}",
            "etapa": "aula",
            "nome": face["nome"],
            "usuario_id": face["usuario_id"],
        }

    if not esta_na_lista(evento, face["usuario_id"]):
        return {
            "liberado": False,
            "motivo": f"Não está na lista de \"{evento['titulo']}\"",
            "etapa": "lista",
            "nome": face["nome"],
            "usuario_id": face["usuario_id"],
            "evento_id": evento["id"],
        }

    return {
        "liberado": True,
        "motivo": f"Acesso liberado para \"{evento['titulo']}\"",
        "etapa": None,
        "nome": face["nome"],
        "usuario_id": face["usuario_id"],
        "evento_id": evento["id"],
        "evento": evento["titulo"],
    }


# ------------------------------------------------------------
# Manter em dia
# ------------------------------------------------------------

# De quanto em quanto tempo vale regerar a cópia. Meia hora é o atraso
# máximo aceitável pra uma aula criada agora aparecer na porta se a rede
# cair logo em seguida - e é barato: são poucos KB e uma consulta.
MINUTOS_ENTRE_ATUALIZACOES = 30


def atualizar_se_velho(cur, minutos: int = MINUTOS_ENTRE_ATUALIZACOES) -> bool:
    """
    Regera a cópia se ela não existe ou está velha. Devolve se regerou.

    Chamada de carona numa leitura que já deu certo, em vez de por uma
    thread de fundo: se a porta está sendo usada, a cópia se mantém quente
    sozinha; se ninguém passa na porta, não há o que manter atualizado.
    """
    copia = carregar()
    if copia and idade_em_horas(copia) * 60 < minutos:
        return False
    salvar(gerar(cur))
    return True


# ------------------------------------------------------------
# CLI: gerar e conferir
# ------------------------------------------------------------

def main():
    import psycopg2
    import psycopg2.extras

    from config import Config

    conn = psycopg2.connect(
        Config.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        with conn.cursor() as cur:
            copia = gerar(cur)
    finally:
        conn.close()

    caminho = salvar(copia)
    print(f"{caminho.resolve()}  ({caminho.stat().st_size / 1024:.0f} KB)")
    print(f"  {len(copia['faces'])} rostos")
    print(f"  {len(copia['dispositivos'])} dispositivos")
    print(f"  {len(copia['eventos'])} eventos até {DIAS_ADIANTE} dias à frente")
    for e in copia["eventos"]:
        print(f"    {e['data_inicio'][:16]}  {e['local']:<14} "
              f"{len(e['participantes'])} convidados  {e['titulo']}")


if __name__ == "__main__":
    main()
