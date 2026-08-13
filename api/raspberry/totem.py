"""
Totem de acesso - a tela cheia que fica na porta da sala.

Mostra o rosto de quem chega ao vivo e responde LIBERADO ou NEGADO.
Igual ao leitor_porta.py, quem decide é o servidor: aqui só entra
câmera, tela e a regra de quando vale a pena perguntar.

Rodar (na sessão gráfica do Pi):

    python3 totem.py --api http://192.168.66.57:5000/api --sala QUADRA

Sai com Esc.

--------------------------------------------------------------------
Três decisões que explicam o código:

1. Só pergunta quando alguém se mexe. Um totem que envia foto sem
   parar transformaria uma sala vazia num NEGADO piscando pra sempre e
   encheria o access_logs de "nenhum rosto detectado". A detecção de
   movimento é uma diferença de quadros em numpy - não precisa de
   OpenCV (que nem está instalado no Pi, e instalar exigiria sudo).

2. A rede roda numa thread separada. O POST leva de 0,2s a 1s; se
   fosse no laço de desenho, a imagem congelaria a cada tentativa e a
   tela pareceria travada. A thread envia, o laço principal só desenha.

3. O preview é duotone enquanto procura e vira cor real quando libera.
   Além de ser o momento visual da tela, isso resolve um problema
   concreto: a luz de LED verde da quadra tinge tudo de verde, e a
   rampa petróleo->menta normaliza isso.
"""

import argparse
import io
import os
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pygame
import requests
from PIL import Image

import descobrir_api

ARQUIVO_CHAVE = Path.home() / ".fetin_chave"

# ------------------------------------------------------------
# Identidade visual
# ------------------------------------------------------------

CAMPO = (12, 26, 30)        # fundo, petróleo tão escuro que lê como preto
PLACA = (20, 40, 46)        # superfície elevada
PETROLEO = (21, 97, 109)    # cor de marca, mesma semente do app
MENTA = (53, 214, 160)      # liberado
CORAL = (240, 101, 90)      # negado
TEXTO = (232, 241, 242)
APAGADO = (110, 143, 152)

# Rampas do duotone: (sombra, luz). O olho lê a imagem inteira como
# "máquina olhando" em vez de "foto ruim com dominante verde".
RAMPA_PROCURA = (np.array([8, 24, 30]), np.array([176, 238, 228]))
RAMPA_NEGADO = (np.array([32, 12, 14]), np.array([250, 176, 166]))

FONTE_DISPLAY = "/usr/share/fonts/opentype/urw-base35/URWGothic-Demi.otf"
FONTE_TEXTO = "/usr/share/fonts/truetype/nunito-sans/NunitoSans-VariableFont_YTLC,opsz,wdth,wght.ttf"
FONTE_DADOS = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

# Tamanho de PROJETO, não da tela. Todo o layout abaixo é escrito nestas
# coordenadas e a classe Tela encaixa o resultado na resolução real (ver
# _apresentar), então um mini display de 7" - 1024x600, 800x480 - mostra o
# mesmo desenho sem que nenhum número aqui mude.
LARGURA, ALTURA = 1920, 1080
VP_L, VP_A = 456, 608                 # retrato 3:4, proporção de foto 3x4
VP_X, VP_Y = (LARGURA - VP_L) // 2, 128

# Alturas do bloco de texto. O veredito e o nome da sala dividem a mesma
# linha de base: parado a tela diz de que porta se trata, e na hora do
# resultado a palavra troca no lugar exato, sem a página "pular".
Y_VEREDITO, Y_NOME, Y_DETALHE, Y_AVISO = 868, 946, 990, 1046

# As quatro checagens do servidor, na ordem. `etapa` na resposta diz
# em qual delas parou.
ETAPAS = ("rosto", "vivacidade", "identidade", "aula", "lista")
ROTULOS = ("ROSTO", "VIVACIDADE", "IDENTIDADE", "AULA", "LISTA")

# Texto de cada negativa, escrito pra quem está na porta - não pro log.
EXPLICACAO = {
    "vivacidade": "Foto ou tela não abre a porta",
    "identidade": "Cadastre seu rosto no aplicativo",
    "aula": "Nenhuma aula acontecendo aqui agora",
    "lista": "Você não foi convidado para esta aula",
}

SEGUNDOS_RESULTADO = 5.0    # quanto tempo o veredito fica na tela
JANELA_TENTATIVA = 8.0      # depois de detectar movimento, insiste por até isso
INTERVALO_ENVIO = 1.2
LIMIAR_MOVIMENTO = 5.0      # diferença média de brilho que conta como "alguém chegou"


# ------------------------------------------------------------
# Imagem
# ------------------------------------------------------------

_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def recortar_retrato(quadro: np.ndarray) -> np.ndarray:
    """
    Da imagem 640x480 da câmera tira um 3:4 central e corrige a ordem
    dos canais.

    O picamera2 entrega "RGB888" em ordem BGR (o nome vem do libcamera,
    não do numpy) - sem o ::-1 no último eixo a pele sai azulada.

    Repare que aqui NÃO se espelha: esta é a imagem que vai pro
    reconhecimento, e o cadastro foi feito na orientação real da câmera.
    Embedding facial não é invariante a espelho, então mandar a imagem
    invertida gasta margem de semelhança à toa.
    """
    altura, largura = quadro.shape[:2]
    alvo = int(altura * 3 / 4)
    x0 = (largura - alvo) // 2
    return np.ascontiguousarray(quadro[:, x0:x0 + alvo, ::-1])


def espelhar(rgb: np.ndarray) -> np.ndarray:
    """
    Só pra exibir. Sem isso a pessoa anda pra um lado e a imagem vai
    pro outro, o que faz a tela parecer quebrada.
    """
    return np.ascontiguousarray(rgb[:, ::-1, :])


def duotone(rgb: np.ndarray, rampa) -> np.ndarray:
    """
    Mapeia o brilho da imagem entre duas cores.

    O ganho de contraste no meio não é enfeite: a quadra é escura e a
    imagem crua ocupa uma faixa estreita de brilho, o que na tela vira
    um borrão sem relevo. Puxar as pontas devolve o desenho do rosto.
    """
    sombra, luz = rampa
    lum = (rgb.astype(np.float32) @ _LUMA) / 255.0
    lum = np.clip((lum - 0.45) * 1.35 + 0.5, 0.0, 1.0)[..., None]
    return (sombra + (luz - sombra) * lum).astype(np.uint8)


def para_superficie(rgb: np.ndarray) -> pygame.Surface:
    """numpy (altura, largura, 3) -> Surface no tamanho do retrato."""
    sup = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
    return pygame.transform.smoothscale(sup, (VP_L, VP_A))


def brilho_reduzido(quadro: np.ndarray) -> np.ndarray:
    """Miniatura de luminância, base barata da detecção de movimento."""
    pequeno = quadro[::8, ::8, :]
    return (pequeno.astype(np.float32) @ _LUMA)


# ------------------------------------------------------------
# Conversa com o servidor
# ------------------------------------------------------------

class Reconhecedor(threading.Thread):
    """
    Envia quadros e devolve vereditos por uma fila.

    Fica dormindo até `pedir()` ser chamado - assim a sala vazia não
    gera tráfego nem log.
    """

    daemon = True

    def __init__(self, api: str, chave: str):
        super().__init__()
        self.api = api
        self.chave = chave
        self.resultados = queue.Queue()
        self._quadro = None
        self._trava = threading.Lock()
        self._tem_trabalho = threading.Event()
        self._ativo = True

    def pedir(self, quadro: np.ndarray):
        with self._trava:
            self._quadro = quadro
        self._tem_trabalho.set()

    def parar(self):
        self._ativo = False
        self._tem_trabalho.set()

    def run(self):
        while self._ativo:
            self._tem_trabalho.wait()
            self._tem_trabalho.clear()
            if not self._ativo:
                return

            with self._trava:
                quadro = self._quadro
                self._quadro = None
            if quadro is None:
                continue

            buf = io.BytesIO()
            Image.fromarray(quadro).save(buf, format="JPEG", quality=85)

            try:
                r = requests.post(
                    f"{self.api}/faces/recognize",
                    headers={"X-Device-Key": self.chave},
                    files={"foto": ("captura.jpg", buf.getvalue(), "image/jpeg")},
                    timeout=20,
                )
                r.raise_for_status()
                self.resultados.put(r.json())
            except requests.RequestException as e:
                # Rede caindo não pode derrubar a porta: vira um aviso
                # discreto no rodapé e a tela continua viva.
                self.resultados.put({"erro_rede": str(e)})


# ------------------------------------------------------------
# Desenho
# ------------------------------------------------------------

class Tela:
    def __init__(self, sala: str, tela_cheia: bool = True):
        self.sala = sala.upper()
        pygame.init()
        pygame.mouse.set_visible(tela_cheia is False)
        # O layout é escrito em coordenadas de 1920x1080 e só no último
        # passo encaixa na tela real. Assim o mini display de 7" (1024x600
        # ou 800x480) e um monitor grande recebem o mesmo desenho, sem uma
        # coordenada sair do lugar. Antes o modo de vídeo era pedido em
        # 1080p fixo: numa tela menor o veredito caía fora da área visível.
        self.superficie = pygame.display.set_mode(
            (0, 0) if tela_cheia else (LARGURA // 2, ALTURA // 2),
            pygame.FULLSCREEN if tela_cheia else 0,
        )
        pygame.display.set_caption("Fetin - Controle de acesso")

        # Tudo é desenhado aqui, no tamanho de projeto.
        self.tela = pygame.Surface((LARGURA, ALTURA))

        # Encaixe proporcional, com sobra preta quando a tela tem outro
        # formato. Esticar deformaria o rosto no preview - que é justamente
        # o que a pessoa usa pra se enquadrar na câmera.
        larg_real, alt_real = self.superficie.get_size()
        escala = min(larg_real / LARGURA, alt_real / ALTURA)
        self._destino = pygame.Rect(0, 0, int(LARGURA * escala), int(ALTURA * escala))
        self._destino.center = (larg_real // 2, alt_real // 2)
        self._escalar = self._destino.size != (LARGURA, ALTURA)

        self.f_display = pygame.font.Font(FONTE_DISPLAY, 96)
        self.f_nome = pygame.font.Font(FONTE_TEXTO, 38)
        self.f_detalhe = pygame.font.Font(FONTE_TEXTO, 24)
        self.f_dados = pygame.font.Font(FONTE_DADOS, 17)
        self.f_micro = pygame.font.Font(FONTE_DADOS, 13)

    def _apresentar(self):
        """Joga o desenho de 1920x1080 na tela real, seja ela qual for."""
        if self._escalar:
            self.superficie.fill((0, 0, 0))
            self.superficie.blit(
                # ponytail: reescala o quadro inteiro toda vez. Num display
                # de 7" custa alguns milissegundos por quadro e o totem
                # desenha devagar de propósito - se um dia pesar, o caminho
                # é desenhar direto na escala, não voltar pro tamanho fixo.
                pygame.transform.smoothscale(self.tela, self._destino.size),
                self._destino,
            )
        else:
            self.superficie.blit(self.tela, (0, 0))
        pygame.display.flip()

    def _centralizado(self, texto, fonte, cor, y):
        img = fonte.render(texto, True, cor)
        self.tela.blit(img, img.get_rect(center=(LARGURA // 2, y)))

    def _cantoneiras(self, cor):
        """
        Moldura do retrato feita só de cantos. Diz "enquadre aqui" sem
        fechar uma caixa em volta do rosto da pessoa.
        """
        braco, esp, folga = 34, 3, 14
        x0, y0 = VP_X - folga, VP_Y - folga
        x1, y1 = VP_X + VP_L + folga, VP_Y + VP_A + folga
        for cx, cy, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1),
                               (x0, y1, 1, -1), (x1, y1, -1, -1)):
            pygame.draw.line(self.tela, cor, (cx, cy), (cx + dx * braco, cy), esp)
            pygame.draw.line(self.tela, cor, (cx, cy), (cx, cy + dy * braco), esp)

    def _trilha(self, etapa_falha, liberado):
        """
        Os quatro testes do servidor, em ordem. Verde o que passou,
        coral onde parou, apagado o que nem chegou a ser perguntado.
        """
        larg, gap, alt = 104, 14, 5
        total = 4 * larg + 3 * gap
        x = (LARGURA - total) // 2
        y = VP_Y + VP_A + 32

        indice = ETAPAS.index(etapa_falha) if etapa_falha in ETAPAS else None

        for i, rotulo in enumerate(ROTULOS):
            if liberado:
                cor, cor_txt = MENTA, MENTA
            elif indice is None:
                cor, cor_txt = PLACA, APAGADO
            elif i < indice:
                cor, cor_txt = MENTA, APAGADO
            elif i == indice:
                cor, cor_txt = CORAL, CORAL
            else:
                cor, cor_txt = PLACA, APAGADO

            pygame.draw.rect(self.tela, cor, (x, y, larg, alt), border_radius=3)
            img = self.f_micro.render(rotulo, True, cor_txt)
            self.tela.blit(img, img.get_rect(midtop=(x + larg // 2, y + 14)))
            x += larg + gap

    def desenhar(self, retrato, estado, resultado, aviso_rede):
        s = self.tela
        s.fill(CAMPO)

        # Cabeçalho: quem é esta porta, e que horas são. Mono porque é
        # dado de máquina, não texto pra ler.
        s.blit(self.f_dados.render("INATEL · CONTROLE DE ACESSO", True, APAGADO), (64, 44))
        hora = time.strftime("%H:%M:%S")
        img = self.f_dados.render(hora, True, APAGADO)
        s.blit(img, img.get_rect(topright=(LARGURA - 64, 44)))

        liberado = bool(resultado and resultado.get("liberado"))
        etapa = resultado.get("etapa") if resultado else None

        if retrato is not None:
            s.blit(retrato, (VP_X, VP_Y))
        else:
            pygame.draw.rect(s, PLACA, (VP_X, VP_Y, VP_L, VP_A))

        if liberado:
            self._cantoneiras(MENTA)
        elif estado == "resultado":
            self._cantoneiras(CORAL)
        elif estado == "verificando":
            self._cantoneiras(PETROLEO)
        else:
            self._cantoneiras(PLACA)

        self._trilha(etapa, liberado)

        if estado == "resultado" and resultado:
            if liberado:
                self._centralizado("LIBERADO", self.f_display, MENTA, Y_VEREDITO)
                self._centralizado(resultado.get("nome", ""), self.f_nome, TEXTO, Y_NOME)
                evento = resultado.get("evento")
                if evento:
                    self._centralizado(evento, self.f_detalhe, APAGADO, Y_DETALHE)
            else:
                self._centralizado("NEGADO", self.f_display, CORAL, Y_VEREDITO)
                nome = resultado.get("nome")
                if nome:
                    self._centralizado(nome, self.f_nome, TEXTO, Y_NOME)
                explicacao = EXPLICACAO.get(etapa) or resultado.get("motivo", "")
                # Sem nome (não reconhecido) a linha sobe pro lugar do nome,
                # senão fica uma lacuna no meio do bloco.
                self._centralizado(
                    explicacao, self.f_detalhe, APAGADO, Y_DETALHE if nome else Y_NOME
                )
        else:
            self._centralizado(self.sala, self.f_display, PETROLEO, Y_VEREDITO)
            instrucao = "Verificando…" if estado == "verificando" else "Olhe para a câmera"
            self._centralizado(instrucao, self.f_detalhe, APAGADO, Y_NOME)

        if aviso_rede:
            img = self.f_dados.render("Sem conexão com o servidor", True, CORAL)
            s.blit(img, img.get_rect(center=(LARGURA // 2, Y_AVISO)))

        self._apresentar()


# ------------------------------------------------------------
# Principal
# ------------------------------------------------------------

def carregar_chave(informada):
    if informada:
        return informada.strip()
    if os.environ.get("FETIN_CHAVE"):
        return os.environ["FETIN_CHAVE"].strip()
    if ARQUIVO_CHAVE.exists():
        return ARQUIVO_CHAVE.read_text().strip()
    sys.exit(f"Sem chave. Passe --chave ou grave em {ARQUIVO_CHAVE}")


def main():
    p = argparse.ArgumentParser(description="Totem de acesso facial")
    # Sem --api o endereço é descoberto sozinho (FETIN_API, ~/.fetin/api, ou
    # varredura da rede). Passar --api continua vencendo tudo.
    p.add_argument("--api", help="ex: http://192.168.66.57:5000/api (opcional)")
    p.add_argument("--chave")
    p.add_argument("--sala", default="QUADRA", help="nome exibido na tela")
    p.add_argument("--janela", action="store_true", help="não abre em tela cheia (teste)")
    args = p.parse_args()

    chave = carregar_chave(args.chave)

    # Antes de abrir a câmera e a tela cheia: sem servidor o totem não tem o
    # que fazer, e a mensagem de erro precisa aparecer num terminal legível e
    # não atrás de uma janela fullscreen.
    api = descobrir_api.resolver(args.api)
    if not api:
        sys.exit(
            "Não achei o servidor Fetin.\n"
            "  Passe --api http://IP:5000/api, ou defina FETIN_API,\n"
            "  ou escreva o endereço em ~/.fetin/api"
        )

    from picamera2 import Picamera2

    camera = Picamera2()
    camera.configure(camera.create_preview_configuration(
        main={"size": (640, 480), "format": "RGB888"}))
    camera.start()
    time.sleep(1.5)

    tela = Tela(args.sala, tela_cheia=not args.janela)

    rede = Reconhecedor(api, chave)
    rede.start()

    estado = "parado"           # parado | verificando | resultado
    resultado = None
    referencia = None           # quadro base da detecção de movimento
    aviso_rede = False
    ultimo_envio = 0.0
    fim_janela = 0.0
    fim_resultado = 0.0

    relogio = pygame.time.Clock()
    rodando = True

    while rodando:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                rodando = False
            elif evento.type == pygame.KEYDOWN and evento.key in (pygame.K_ESCAPE, pygame.K_q):
                rodando = False

        quadro = recortar_retrato(camera.capture_array())
        agora = time.time()

        # --- movimento: só acorda a rede quando alguém chega ---
        atual = brilho_reduzido(quadro)
        if referencia is None:
            referencia = atual
        movimento = float(np.abs(atual - referencia).mean())
        referencia = referencia * 0.8 + atual * 0.2

        if estado == "resultado" and agora >= fim_resultado:
            estado, resultado = "parado", None
            referencia = atual  # evita reagir à saída da pessoa

        if estado == "parado" and movimento > LIMIAR_MOVIMENTO:
            estado = "verificando"
            fim_janela = agora + JANELA_TENTATIVA

        if estado == "verificando":
            if agora >= fim_janela:
                estado = "parado"
            elif agora - ultimo_envio >= INTERVALO_ENVIO:
                ultimo_envio = agora
                rede.pedir(quadro)

        # --- vereditos que chegaram ---
        try:
            while True:
                corpo = rede.resultados.get_nowait()
                if "erro_rede" in corpo:
                    aviso_rede = True
                    continue
                aviso_rede = False

                # "Não vi rosto nenhum" não é uma negativa pra mostrar:
                # é o totem ainda procurando. Continua tentando dentro
                # da janela em vez de piscar NEGADO pra uma sala vazia.
                if not corpo.get("liberado") and corpo.get("etapa") == "rosto":
                    continue

                resultado = corpo
                estado = "resultado"
                fim_resultado = agora + SEGUNDOS_RESULTADO
        except queue.Empty:
            pass

        # --- imagem: sempre ao vivo, só a cor muda ---
        if estado == "resultado" and resultado.get("liberado"):
            base = quadro
        elif estado == "resultado":
            base = duotone(quadro, RAMPA_NEGADO)
        else:
            base = duotone(quadro, RAMPA_PROCURA)

        tela.desenhar(para_superficie(espelhar(base)), estado, resultado, aviso_rede)
        relogio.tick(20)

    rede.parar()
    camera.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
