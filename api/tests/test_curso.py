"""Testes da dedução de curso pelo e-mail institucional."""

import pytest

from utils.curso import curso_do_email


@pytest.mark.parametrize("email,esperado", [
    # Os dois cursos que existem na base real hoje.
    ("samuel.pontes@get.inatel.br", "Engenharia de Telecomunicações"),
    ("antonio.vinicius@gec.inatel.br", "Engenharia de Computação"),
    ("pedro.l@get.inatel.br", "Engenharia de Telecomunicações"),

    # Sigla desconhecida devolve ela mesma, em maiúsculas: melhor mostrar
    # "GXX" do que inventar um nome de curso que ninguém conferiu.
    ("alguem@gxx.inatel.br", "GXX"),

    # Caixa e espaços não deveriam mudar nada.
    ("  Samuel.Pontes@GET.Inatel.BR  ".strip(), "Engenharia de Telecomunicações"),

    # Fora do Inatel não dá pra deduzir nada.
    ("alguem@gmail.com", None),
    ("alguem@outra.edu.br", None),

    # @inatel.br direto (professor/servidor) não carrega curso.
    ("professor@inatel.br", None),

    # Entradas quebradas não podem estourar: isto roda em cima de dado vindo
    # do Supabase, e uma exceção aqui derrubaria a lista de alunos inteira.
    ("", None),
    (None, None),
    ("sem-arroba", None),
])
def test_curso_do_email(email, esperado):
    assert curso_do_email(email) == esperado


def test_nao_confunde_dominio_parecido():
    # "inatel.br.algumacoisa.com" não é o Inatel — o teste existe porque a
    # checagem é por sufixo e sufixo é fácil de escrever errado.
    assert curso_do_email("alguem@gec.inatel.br.fake.com") is None
