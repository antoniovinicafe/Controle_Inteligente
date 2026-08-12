"""Curso da pessoa, deduzido do subdomínio do e-mail institucional.

O Inatel dá e-mail no formato nome.sobrenome@<curso>.inatel.br, então o curso
já está no cadastro — não precisa ser perguntado nem digitado, e não pode
divergir da matrícula porque não é um campo separado que alguém edita.

Por isso é função e não coluna: derivar na hora significa zero migração, zero
dado duplicado e zero chance de o banco guardar um curso diferente do e-mail.
Se um dia precisar filtrar por curso no SQL, aí sim vale uma coluna gerada.
"""

# Só os dois confirmados na base real. Deliberadamente NÃO chutei os demais:
# um mapa com sigla inventada mostraria curso errado com cara de certeza, que
# é pior que mostrar a sigla crua. Acrescente conforme aparecerem.
CURSOS = {
    "gec": "Engenharia de Computação",
    "get": "Engenharia de Telecomunicações",
}


def curso_do_email(email):
    """
    Nome do curso, ou a sigla em maiúsculas quando ela não é conhecida, ou
    None quando o e-mail não é institucional do Inatel.

    >>> curso_do_email("samuel.pontes@get.inatel.br")
    'Engenharia de Telecomunicações'
    >>> curso_do_email("alguem@gxx.inatel.br")
    'GXX'
    >>> curso_do_email("alguem@gmail.com") is None
    True
    """
    if not email or "@" not in email:
        return None

    dominio = email.rsplit("@", 1)[1].strip().lower()
    if not dominio.endswith(".inatel.br"):
        return None

    sigla = dominio[: -len(".inatel.br")]
    # Um e-mail direto @inatel.br (sem curso) não tem sigla pra ler, e
    # subdomínio composto não é um curso.
    if not sigla or "." in sigla:
        return None

    return CURSOS.get(sigla, sigla.upper())
