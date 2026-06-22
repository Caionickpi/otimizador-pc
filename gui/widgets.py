"""Componentes visuais reutilizáveis da janela (acabamento premium).

Aqui ficam os elementos "autorais" que dão identidade ao programa e o tiram da
cara de app genérico: barra de título sem moldura, anel de saúde animado com
brilho, interruptor (toggle) estilo moderno, cartões com sombra e KPIs.

Tudo é desenhado com :class:`QPainter`/QSS — sem depender de imagens externas —
para manter o executável enxuto e o visual nítido em qualquer resolução.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui import tema


# ---------------------------------------------------------------------------
# Sombra (profundidade premium)
# ---------------------------------------------------------------------------
def aplicar_sombra(widget: QWidget, raio: int = 34, alpha: int = 120,
                   dy: int = 10, cor: str = "#000000") -> None:
    """Aplica uma sombra suave a um widget (dá sensação de elevação)."""
    sombra = QGraphicsDropShadowEffect(widget)
    sombra.setBlurRadius(raio)
    c = QColor(cor)
    c.setAlpha(alpha)
    sombra.setColor(c)
    sombra.setOffset(0, dy)
    widget.setGraphicsEffect(sombra)


# ---------------------------------------------------------------------------
# Cartão (superfície elevada)
# ---------------------------------------------------------------------------
class Cartao(QFrame):
    """Superfície arredondada padrão (um "card"), com sombra opcional."""

    def __init__(self, parent: Optional[QWidget] = None, sombra: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("cartao")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 18, 20, 18)
        self._lay.setSpacing(10)
        if sombra:
            aplicar_sombra(self, raio=30, alpha=90, dy=8)

    def layout_conteudo(self) -> QVBoxLayout:
        return self._lay


class Chip(QLabel):
    """Etiqueta compacta (chip) para destacar um dado curto."""

    def __init__(self, texto: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(texto, parent)
        self.setObjectName("chip")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class EstatChip(QFrame):
    """Cartão de indicador (KPI): ícone + valor em destaque + rótulo."""

    def __init__(self, rotulo: str, icone: str = "•", valor: str = "–",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("kpi")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        topo = QHBoxLayout()
        topo.setSpacing(8)
        self._icone = QLabel(icone)
        self._icone.setObjectName("kpiIcone")
        topo.addWidget(self._icone)
        topo.addStretch(1)
        lay.addLayout(topo)

        self._valor = QLabel(valor)
        self._valor.setObjectName("kpiValor")
        self._rotulo = QLabel(rotulo)
        self._rotulo.setObjectName("kpiRotulo")
        self._rotulo.setWordWrap(True)
        lay.addWidget(self._valor)
        lay.addWidget(self._rotulo)
        aplicar_sombra(self, raio=24, alpha=70, dy=6)

    def definir_valor(self, valor: str) -> None:
        self._valor.setText(valor)


# ---------------------------------------------------------------------------
# Anel de saúde (animado, com brilho)
# ---------------------------------------------------------------------------
class AnelSaude(QWidget):
    """Anel circular animado que mostra a pontuação de saúde (0–100) e a nota.

    A cor acompanha a faixa (verde/âmbar/vermelho) e o preenchimento é animado
    (sobe suavemente de 0 até o valor) com um leve brilho — visual de produto
    pago, 100% desenhado em código.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._valor = 0.0
        self._alvo = 0
        self._nota = "–"
        self.setMinimumSize(208, 208)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._anim = QPropertyAnimation(self, b"valor", self)
        self._anim.setDuration(1100)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # Propriedade animável (preenchimento do anel + número central).
    def _get_valor(self) -> float:
        return self._valor

    def _set_valor(self, v: float) -> None:
        self._valor = float(v)
        self.update()

    valor = Property(float, _get_valor, _set_valor)

    def definir(self, pontuacao: int, nota: str) -> None:
        self._alvo = max(0, min(100, int(pontuacao)))
        self._nota = nota or "–"
        self._anim.stop()
        self._anim.setStartValue(self._valor)
        self._anim.setEndValue(float(self._alvo))
        self._anim.start()

    def paintEvent(self, _evento) -> None:  # noqa: N802 - assinatura do Qt
        lado = min(self.width(), self.height())
        margem = 18
        ret = QRectF(margem, margem, lado - 2 * margem, lado - 2 * margem)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        largura = 16
        # Trilho de fundo do anel.
        p.setPen(QPen(QColor(tema.TRILHO), largura, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawArc(ret, 0, 360 * 16)

        cor = QColor(tema.cor_por_pontuacao(self._alvo))
        extensao = int(-360 * 16 * self._valor / 100)

        # Brilho (arco mais largo e translúcido por baixo).
        cor_brilho = QColor(cor)
        cor_brilho.setAlpha(70)
        p.setPen(QPen(cor_brilho, largura + 10, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawArc(ret, 90 * 16, extensao)

        # Arco principal com leve gradiente (brilho no topo).
        grad = QLinearGradient(ret.topLeft(), ret.bottomLeft())
        clara = QColor(cor).lighter(135)
        grad.setColorAt(0.0, clara)
        grad.setColorAt(1.0, cor)
        p.setPen(QPen(QBrush(grad), largura, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawArc(ret, 90 * 16, extensao)

        # Número central (conta junto com a animação).
        p.setPen(QColor(tema.TEXTO_FORTE))
        fonte_num = QFont(self.font())
        fonte_num.setPointSize(40)
        fonte_num.setBold(True)
        p.setFont(fonte_num)
        ret_num = QRectF(ret.x(), ret.y() - ret.height() * 0.04, ret.width(), ret.height())
        p.drawText(ret_num, Qt.AlignmentFlag.AlignCenter, str(int(round(self._valor))))

        # "/100" discreto, logo abaixo do número.
        p.setPen(QColor(tema.TEXTO_FRACO))
        fonte_cem = QFont(self.font())
        fonte_cem.setPointSize(11)
        p.setFont(fonte_cem)
        ret_cem = QRectF(ret.x(), ret.y() + ret.height() * 0.585, ret.width(), 20)
        p.drawText(ret_cem, Qt.AlignmentFlag.AlignCenter, "de 100")

        # Nota (A–F).
        p.setPen(cor)
        fonte_nota = QFont(self.font())
        fonte_nota.setPointSize(13)
        fonte_nota.setBold(True)
        p.setFont(fonte_nota)
        ret_nota = QRectF(ret.x(), ret.y() + ret.height() * 0.70, ret.width(), 26)
        p.drawText(ret_nota, Qt.AlignmentFlag.AlignCenter, f"NOTA {self._nota}")
        p.end()


# ---------------------------------------------------------------------------
# Interruptor (toggle) estilo moderno
# ---------------------------------------------------------------------------
class ToggleSwitch(QAbstractButton):
    """Interruptor liga/desliga animado (detalhe que dá acabamento)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 0.0
        self.setFixedSize(50, 28)
        self._anim = QPropertyAnimation(self, b"posicao", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._ao_alternar)

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, v: float) -> None:
        self._pos = float(v)
        self.update()

    posicao = Property(float, _get_pos, _set_pos)

    def _ao_alternar(self, ligado: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if ligado else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(50, 28)

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)

        desligado = QColor(tema.BORDA_FORTE)
        ligado = QColor(tema.ACENTO)
        trilho = QColor(
            int(desligado.red() + (ligado.red() - desligado.red()) * self._pos),
            int(desligado.green() + (ligado.green() - desligado.green()) * self._pos),
            int(desligado.blue() + (ligado.blue() - desligado.blue()) * self._pos),
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(trilho)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        # Botão deslizante (knob).
        d = r.height() - 6
        x = r.x() + 3 + (r.width() - d - 6) * self._pos
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, r.y() + 3, d, d))
        p.end()


# ---------------------------------------------------------------------------
# Barra de título própria (janela sem moldura)
# ---------------------------------------------------------------------------
class BotaoJanela(QPushButton):
    """Botão de controle da janela (minimizar/maximizar/fechar)."""

    def __init__(self, simbolo: str, objeto: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(simbolo, parent)
        self.setObjectName(objeto)
        self.setFixedSize(44, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class BarraTitulo(QWidget):
    """Barra de título personalizada: logo + nome + controles da janela.

    Move a janela com arraste nativo (``startSystemMove`` — preserva o "snap"
    do Windows) e maximiza/restaura com duplo-clique.
    """

    def __init__(self, janela: QWidget, titulo: str, pixmap: Optional[QPixmap] = None) -> None:
        super().__init__(janela)
        self._janela = janela
        self.setObjectName("barraTitulo")
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 8, 0)
        lay.setSpacing(10)

        if pixmap is not None and not pixmap.isNull():
            logo = QLabel()
            logo.setPixmap(pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
            lay.addWidget(logo)

        nome = QLabel(titulo)
        nome.setObjectName("tituloJanela")
        lay.addWidget(nome)
        lay.addStretch(1)

        self.btn_min = BotaoJanela("–", "btnJanela")      # –
        self.btn_max = BotaoJanela("☐", "btnJanela")      # ☐
        self.btn_fechar = BotaoJanela("✕", "btnFechar")   # ✕
        for b in (self.btn_min, self.btn_max, self.btn_fechar):
            lay.addWidget(b)

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            try:
                alca = self._janela.windowHandle()
                if alca is not None:
                    alca.startSystemMove()
                    return
            except Exception:  # noqa: BLE001 - arraste nunca pode quebrar a janela
                pass
        super().mousePressEvent(evento)

    def mouseDoubleClickEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton and hasattr(self._janela, "alternar_maximizar"):
            self._janela.alternar_maximizar()


def linha(rotulo: str, valor_obj: QWidget) -> QWidget:
    """Monta uma linha 'rótulo  ........  valor' para usar dentro de cartões."""
    caixa = QWidget()
    lay = QHBoxLayout(caixa)
    lay.setContentsMargins(0, 0, 0, 0)
    lab = QLabel(rotulo)
    lab.setObjectName("cartaoDesc")
    lay.addWidget(lab)
    lay.addStretch(1)
    lay.addWidget(valor_obj)
    return caixa
