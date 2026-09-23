"""
Apaga o rosto de uma conta, pra ela ser reusada pelo próximo visitante.

    venv/Scripts/python limpar_visitante.py                  apaga o padrão
    venv/Scripts/python limpar_visitante.py outro@email.com  apaga outra conta
    venv/Scripts/python limpar_visitante.py --ver            só mostra, não apaga

EXISTE PORQUE NUMA FEIRA O CELULAR ESTÁ NA MÃO DO VISITANTE
O aplicativo já faz isto em "Cadastro facial → Remover todas", e essa é a
forma normal. Mas entre um visitante e o próximo o telefone está com outra
pessoa, e pedir de volta pra navegar num menu quebra o ritmo da bancada.
Daqui é um comando, sem tocar no aparelho.

FAZ EXATAMENTE O QUE A ROTA DELETE /faces FAZ, e isso não é coincidência:
apagar o rosto É a revogação do consentimento, não uma ação separada. Se
este script só apagasse `faces`, a conta ficaria consentida sem rosto - um
estado que o resto do sistema não sabe representar, e que faria o próximo
visitante cadastrar biometria sem ver o termo.

O registro antigo do consentimento NÃO é apagado, só carimbado com a data
de revogação. Ele é a prova de que o tratamento anterior era legítimo, e
sumir com ele junto com o dado seria destruir a própria defesa.
"""
import sys

import psycopg2
import psycopg2.extras

from config import Config

PADRAO = "visitante@fetin.local"


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    email = argumentos[0] if argumentos else PADRAO
    so_ver = "--ver" in sys.argv

    conn = psycopg2.connect(
        Config.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.id, p.nome,
                       (select count(*) from faces f where f.usuario_id = p.id) rostos,
                       (select count(*) from consentimentos c
                         where c.usuario_id = p.id and c.revogado_em is null) consentido
                from profiles p join auth.users u on u.id = p.id
                where u.email = %s
                """,
                (email,),
            )
            pessoa = cur.fetchone()

            if not pessoa:
                sys.exit(f"Não achei conta com o e-mail {email}")

            print(f"{pessoa['nome']}  <{email}>")
            print(f"  capturas:     {pessoa['rostos']}")
            print(f"  consentimento: {'em vigor' if pessoa['consentido'] else 'revogado'}")

            if so_ver:
                return

            if not pessoa["rostos"] and not pessoa["consentido"]:
                print("\nJá estava limpa.")
                return

            cur.execute("delete from faces where usuario_id = %s", (pessoa["id"],))
            apagadas = cur.rowcount

            cur.execute(
                """
                update consentimentos set revogado_em = now()
                where usuario_id = %s and revogado_em is null
                """,
                (pessoa["id"],),
            )
            revogados = cur.rowcount

        conn.commit()
        print(f"\n{apagadas} capturas apagadas, {revogados} consentimento revogado.")
        print("A conta está pronta pro próximo, e o termo vai aparecer de novo.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
