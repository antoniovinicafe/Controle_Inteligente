"""
Mede as distâncias entre os rostos cadastrados.

    cd api && venv/Scripts/python medir_rostos.py

Existe porque o limiar de 0,30 (LIMIAR_DISTANCIA em routes/faces.py) só faz
sentido no vão entre duas medidas, e o README cita as duas:

  - entre PESSOAS diferentes: o menor par é o quanto o sistema chega perto de
    confundir gente. Tem que ficar BEM acima do limiar.
  - de cada captura até a IRMÃ MAIS PRÓXIMA (outra captura da mesma pessoa):
    é esta que diz se a pessoa vai ser reconhecida, porque o reconhecimento
    faz `order by distância limit 1` - basta UMA captura dela ficar perto.

Não confunda a segunda com "a maior distância entre duas fotos da mesma
pessoa": essa pode passar do limiar sem problema nenhum, e passa mesmo - é o
motivo de guardar até 5 capturas em condições diferentes. O que não pode é
uma captura ficar longe de TODAS as irmãs: aí ela não é aquele rosto. Foi
assim que se descobriu um vetor estranho na conta do Samuel, a 0,9 das
outras quatro - alguém ou alguma coisa que virou "rosto do Samuel" no banco
e podia liberar a porta no nome dele.

Não escreve nada no banco. Demora uns 20s pra começar: pega o limiar de
routes/faces.py pra não ter duas verdades, e esse import arrasta o DeepFace
(TensorFlow) junto.
"""

import psycopg2
import psycopg2.extras

from config import Config
from routes.faces import LIMIAR_DISTANCIA


def main():
    conn = psycopg2.connect(
        Config.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.nome, count(*) as capturas
                from faces f join profiles p on p.id = f.usuario_id
                group by p.nome order by 2 desc, 1
                """
            )
            pessoas = cur.fetchall()
            total = sum(p["capturas"] for p in pessoas)
            print(f"{total} capturas de {len(pessoas)} pessoas")
            for p in pessoas:
                print(f"  {p['capturas']}x  {p['nome']}")

            # O par mais próximo entre pessoas DIFERENTES: é o quanto o
            # sistema chega perto de trocar uma pela outra.
            cur.execute(
                """
                select count(*) as pares, min(a.embedding <=> b.embedding) as menor
                from faces a join faces b on a.id < b.id
                where a.usuario_id <> b.usuario_id
                """
            )
            entre = cur.fetchone()

            # Pra cada captura, a distância até a irmã mais próxima - a
            # mesma conta que o reconhecimento faz na porta.
            cur.execute(
                """
                select f.id, p.nome, f.atualizado_em,
                       (select min(o.embedding <=> f.embedding)
                        from faces o
                        where o.usuario_id = f.usuario_id and o.id <> f.id) as irma
                from faces f join profiles p on p.id = f.usuario_id
                where exists (select 1 from faces o
                              where o.usuario_id = f.usuario_id and o.id <> f.id)
                order by irma desc
                """
            )
            irmas = cur.fetchall()
    finally:
        conn.close()

    print(f"\nlimiar em uso: {LIMIAR_DISTANCIA}\n")

    if entre["pares"]:
        folga = entre["menor"] - LIMIAR_DISTANCIA
        print(f"pessoas diferentes  {entre['pares']:>4} pares   "
              f"mais próximo {entre['menor']:.3f}   (folga {folga:+.3f})")
    else:
        print("pessoas diferentes  - precisa de duas pessoas cadastradas")

    if not irmas:
        print("capturas irmãs      - ninguém tem duas capturas ainda, "
              "esta metade do limiar segue sem medida")
        return

    # ponytail: "longe de todas as irmãs" é o dobro do limiar, escolhido no
    # olho. O caso real que motivou isto estava em 0,9 - bem acima de
    # qualquer discussão de onde exatamente cortar.
    SUSPEITA = LIMIAR_DISTANCIA * 2

    print("\ncada captura e a irmã mais próxima:")
    for r in irmas:
        marca = "  <-- longe de todas as outras" if r["irma"] > SUSPEITA else ""
        print(f"  #{r['id']:<4} {r['irma']:.3f}  {r['nome']}"
              f"  ({r['atualizado_em']:%d/%m %H:%M}){marca}")

    estranhas = [r for r in irmas if r["irma"] > SUSPEITA]
    if estranhas:
        print(f"\n{len(estranhas)} captura(s) marcadas acima não parecem ser o rosto "
              "de quem as cadastrou.\nUm vetor assim só serve pra liberar a porta "
              "no nome errado - convém apagar\ne cadastrar de novo.")


if __name__ == "__main__":
    main()
