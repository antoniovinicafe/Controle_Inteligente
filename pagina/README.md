# A estação da feira

`index.html` é a página interativa que roda num notebook na bancada da
FETIN. Uma página só, sem backend e sem build.

Publicada como Artifact em
<https://claude.ai/artifact/JhwQqg9MkqiNNgQMnq2VqQ> (privada: só abre para
quem tiver acesso na conta que publicou).

## O que ela tem

- **O simulador da porta.** Cinco cenários, e a trilha das cinco checagens
  acende pela mesma regra do totem de verdade: menta no que passou, coral
  onde parou, apagado no que nem foi perguntado. As mensagens de recusa são
  as mesmas que o servidor devolve.
- **A caixa em 3D.** As três peças de `../caixa/`, com vista explodida e
  três pontos de interesse que contam o que cada detalhe físico causou no
  software.
- As distâncias medidas, as três medições de vivacidade, o teste offline com
  os horários originais, as cinco telas do aplicativo e o termo de
  consentimento.

## Decisões que não são óbvias no arquivo

- **Os STL estão embutidos em base64**, e não carregados de `../caixa/`.
  São 350 KB dos 404 KB do arquivo. A duplicação é deliberada: a rede de
  uma feira não é confiável, e a página precisa continuar inteira depois de
  carregada uma vez. Se as peças mudarem, regere o base64 a partir de
  `../caixa/`.
- **O leitor de STL é escrito à mão**, em vez de usar o `STLLoader`. São
  vinte linhas, e evita depender de um arquivo de `examples/` que não é
  servido de forma confiável por CDN.
- **A rotação é feita à mão também**, sem `OrbitControls`, porque assim dá
  pra garantir que o gesto vertical continue rolando a página. Visitante
  preso num canvas 3D sem conseguir sair é falha garantida numa feira.
- **A área do 3D recorta o que passa da borda.** Os marcadores são
  posicionados a cada quadro pela projeção do modelo, e quando ele gira um
  deles sai da lona e esticaria a página na horizontal.
- **Tudo volta ao repouso depois de 30 segundos sem toque.** Quem mexeu já
  foi embora, e o próximo visitante tem que encontrar a estação pronta.
- **A página não pede a câmera de ninguém.** Numa página sobre privacidade
  biométrica, pedir a câmera de quem passa seria a contradição que alguém
  vai notar.

## O que vem de fora

Três.js e as duas fontes vêm de CDN **no carregamento**. Depois disso a
página funciona sem rede.

Na feira: abra cedo, com internet boa, e **não recarregue a aba** durante o
dia.

## Como atualizar

Edite o arquivo e publique de novo como nova versão do mesmo Artifact. O
briefing que originou a página, com a especificação completa de cada seção,
está em [`../HANDOFF_PAGINA.md`](../HANDOFF_PAGINA.md).
