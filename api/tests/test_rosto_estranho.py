"""A segunda foto tem que ser da mesma cara da primeira.

POR QUE ESTES TESTES EXISTEM
Em 13/08/2026 a medição achou, entre as 5 capturas de um aluno, uma que
estava a 0,895 de todas as outras dele - não era o rosto dele. Passou pelo
cadastro porque as duas checagens que existiam não pegam esse caso: a
vivacidade só diz que era gente presente, e "um rosto pertence a uma conta
só" só recusa rosto que JÁ está em outra conta. Rosto de quem não é
cadastrado entrava calado.

Um vetor desses não atrapalha o dono - a porta compara contra a captura mais
próxima e nunca escolhe essa - mas fica no banco como uma chave a mais,
capaz de liberar a porta no nome dele pra quem se parecer com ela. E como
não existe rota pra apagar UMA captura, a entrada é o único momento barato
de barrar.

O limiar daqui (0,60) é propositalmente muito mais frouxo que o do
reconhecimento (0,30): duas fotos legítimas da mesma pessoa passam de 0,30
com facilidade, e é exatamente por isso que se guarda mais de uma. Os testes
abaixo prendem os dois lados dessa distinção - se alguém apertar este limiar
até o do reconhecimento, a segunda foto de todo mundo passa a ser recusada.

O que esta checagem NÃO cobre, de propósito: a primeira captura da conta,
que não tem irmã com que se comparar. Cadastrar o rosto de um colega ainda
não cadastrado continua possível na foto inicial, e nenhuma das barreiras
pega esse caso - a captura ao vivo garante que a foto é do momento, não de
quem. É limitação conhecida e decidida, não descuido: fechá-la exige
confirmação de fora do sistema (um professor aprovando a primeira foto), e
o porquê de não construir isso está no README da raiz, em "A limitação que
sobra: a primeira foto".

Não tocam no banco: reproduzem a aritmética de distância de cosseno do
operador `<=>` do pgvector, igual test_multiplos_rostos.py.
"""

import numpy as np

from routes.faces import (
    LIMIAR_DISTANCIA,
    LIMIAR_ROSTO_ESTRANHO,
    e_o_mesmo_rosto,
)
from services.face_service import similaridade_cosseno


def dist(a, b):
    """Distância de cosseno — o mesmo que o operador <=> do pgvector."""
    return 1 - similaridade_cosseno(a, b)


def vetor(*valores):
    v = np.zeros(512, dtype=np.float32)
    for i, x in enumerate(valores):
        v[i] = x
    return v


def mais_proxima(nova, cadastradas):
    """O que o `select min(embedding <=> nova)` devolve."""
    return min(dist(nova, c) for c in cadastradas)


# Números reais medidos em 13/08/2026 (ver medir_rostos.py), e é entre estes
# dois que o limiar tem que passar:
PAR_LEGITIMO_MAIS_DISTANTE = 0.520   # duas fotos da mesma pessoa, ambas boas
INTRUSA_REAL = 0.895                 # o vetor que não era o rosto do dono


def test_a_intrusa_medida_de_verdade_seria_barrada():
    assert not e_o_mesmo_rosto(INTRUSA_REAL)


def test_o_par_legitimo_mais_distante_medido_passa():
    # É o caso caro do outro lado: recusar isto seria recusar a segunda foto
    # de alguém que só tem uma - justamente a que existe pra cobrir outra
    # luz. Repare que ele passa MUITO do limiar do reconhecimento e mesmo
    # assim tem que ser aceito no cadastro.
    assert PAR_LEGITIMO_MAIS_DISTANTE > LIMIAR_DISTANCIA
    assert e_o_mesmo_rosto(PAR_LEGITIMO_MAIS_DISTANTE)


def test_o_limiar_fica_entre_as_duas_medidas():
    # Se alguém mexer no número, que seja pra dentro deste vão.
    assert PAR_LEGITIMO_MAIS_DISTANTE < LIMIAR_ROSTO_ESTRANHO < INTRUSA_REAL


def test_este_limiar_e_mais_frouxo_que_o_do_reconhecimento():
    # Se um dia alguém igualar os dois, o teste acima é que quebra - este
    # aqui só deixa a intenção explícita no lugar onde ela vale.
    assert LIMIAR_ROSTO_ESTRANHO > LIMIAR_DISTANCIA


def test_a_conta_compara_contra_a_captura_mais_proxima():
    # Não é "parecida com a média das suas fotos" nem "com a primeira": basta
    # UMA captura próxima, senão cadastrar em condição nova ficaria mais
    # difícil a cada foto acrescentada.
    clara = vetor(1.0, 0.0, 0.35)
    escura = vetor(0.0, 1.0, 0.35)
    nova = vetor(0.0, 1.0, 0.30)     # parecida só com a escura
    assert e_o_mesmo_rosto(mais_proxima(nova, [clara, escura]))


def test_rosto_de_outra_pessoa_nao_entra_na_conta():
    minhas = [vetor(1.0, 0.0, 0.35), vetor(0.0, 1.0, 0.35)]
    outra = vetor(-1.0, -0.2, 0.0)
    assert not e_o_mesmo_rosto(mais_proxima(outra, minhas))


