"""Componentes visuais reutilizáveis da janela (cartões, anel de saúde...)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui import tema


class Cartao(QFrame):
    """Superfície arredondada padrão (um "card") com sombra sutil via borda."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("cartao")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(18, 16, 18, 16)
        self._lay.setSpacing(10)

    def layout_conteudo(self) -> QVBoxLayout:
        return self._lay


class Chip(QLabel):
    """Etiqueta compacta (chip) para destacar um dado curto."""

    def __init__(self, texto: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(texto, parent)
        self.setObjectName("chip")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class AnelSaude(QWidget):
    """Anel circular que mostra a pontuação de saúde (0–100) e a nota A–F.

    Desenhado com :class:`QPainter` para um visual premium independente de
    imagens externas. A cor acompanha a faixa da pontuação (verde/âmbar/vermelho).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pontuacao = 0
        self._nota = "–"
        self.setMinimumSize(190, 190)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def definir(self, pontuacao: int, nota: str) -> None:
        self._pontuacao = max(0, min(100, int(pontuacao)))
        self._nota = nota or "–"
        self.update()

    def paintEvent(self, _evento) -> None:  # noqa: N802 - assinatura do Qt
        lado = min(self.width(), self.height())
        margem = 14
        ret = QRectF(margem, margem, lado - 2 * margem, lado - 2 * margem)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Trilho de fundo do anel.
        caneta_fundo = QPen(QColor(tema.BORDA), 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(caneta_fundo)
        p.drawArc(ret, 0, 360 * 16)

        # Arco proporcional à pontuação (começa no topo, sentido horário).
        cor = QColor(tema.cor_por_pontuacao(self._pontuacao))
        caneta = QPen(cor, 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(caneta)
        extensao = int(-360 * 16 * self._pontuacao / 100)
        p.drawArc(ret, 90 * 16, extensao)

        # Número central.
        p.setPen(QColor(tema.TEXTO_FORTE))
        fonte_num = QFont(self.font())
        fonte_num.setPointSize(34)
        fonte_num.setBold(True)
        p.setFont(fonte_num)
        p.drawText(ret, Qt.AlignmentFlag.AlignCenter, str(self._pontuacao))

        # Nota (A–F) logo abaixo do número.
        p.setPen(cor)
        fonte_nota = QFont(self.font())
        fonte_nota.setPointSize(13)
        fonte_nota.setBold(True)
        p.setFont(fonte_nota)
        ret_nota = QRectF(ret.x(), ret.y() + ret.height() * 0.60, ret.width(), 28)
        p.drawText(ret_nota, Qt.AlignmentFlag.AlignCenter, f"Nota {self._nota}")
        p.end()


class EstatChip(Cartao):
    """Cartão pequeno com um rótulo e um valor em destaque (KPI)."""

    def __init__(self, rotulo: str, valor: str = "–", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.layout_conteudo().setContentsMargins(16, 12, 16, 12)
        self.layout_conteudo().setSpacing(2)
        self._rotulo = QLabel(rotulo)
        self._rotulo.setObjectName("cartaoDesc")
        self._valor = QLabel(valor)
        self._valor.setObjectName("cartaoTitulo")
        f = QFont(self._valor.font())
        f.setPointSize(16)
        self._valor.setFont(f)
        self.layout_conteudo().addWidget(self._valor)
        self.layout_conteudo().addWidget(self._rotulo)

    def definir_valor(self, valor: str) -> None:
        self._valor.setText(valor)


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
