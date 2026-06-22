"""Tema visual premium (paleta + folha de estilo QSS) da janela.

A paleta deriva das cores já usadas na TUI (definidas em :mod:`config`), para
que a marca do programa seja consistente entre o modo janela e o modo terminal.
O estilo é escuro, com cantos arredondados, realces em ciano/azul e tipografia
do sistema — pensado para passar a sensação de produto pago.
"""

from __future__ import annotations

import config

# ---------------------------------------------------------------------------
# Paleta (escura, viva e profissional). Fundo no estilo "GitHub dark".
# ---------------------------------------------------------------------------
FUNDO = "#0b0f14"          # fundo da janela (quase preto azulado)
FUNDO_BARRA = "#0e1420"    # barra lateral
PAINEL = "#161b22"         # cartões / superfícies
PAINEL_ALTO = "#1c2230"    # superfícies em destaque / hover
BORDA = "#283041"          # bordas sutis
BORDA_FORTE = "#3a4150"     # bordas em destaque / hover

TEXTO = config.COR_NEUTRA          # #c9d1d9
TEXTO_FRACO = config.COR_DIM       # #6e7681
TEXTO_FORTE = "#ffffff"

OK = config.COR_OK                 # #3fb950 verde
AVISO = config.COR_AVISO           # #d29922 âmbar
ERRO = config.COR_ERRO             # #f85149 vermelho
INFO = config.COR_INFO             # #58a6ff azul
ACENTO = config.COR_ACENTO         # #39d0d8 ciano
ACENTO2 = "#1f6feb"                # azul forte (seleção)


def cor_por_pontuacao(p: int) -> str:
    """Cor do anel/nota conforme a pontuação de saúde (0–100)."""
    if p >= 80:
        return OK
    if p >= 60:
        return AVISO
    return ERRO


# ---------------------------------------------------------------------------
# Folha de estilo (QSS) aplicada ao QApplication inteiro.
# ---------------------------------------------------------------------------
def folha_estilo() -> str:
    """Retorna o QSS completo da aplicação."""
    return f"""
    * {{
        font-family: 'Segoe UI', 'Inter', 'Ubuntu', 'Helvetica Neue', sans-serif;
        font-size: 14px;
        color: {TEXTO};
        outline: 0;
    }}

    QWidget#raiz {{
        background-color: {FUNDO};
    }}

    /* ---------------- Barra lateral ---------------- */
    QWidget#barraLateral {{
        background-color: {FUNDO_BARRA};
        border-right: 1px solid {BORDA};
    }}
    QLabel#marca {{
        color: {TEXTO_FORTE};
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 0.5px;
    }}
    QLabel#marcaVersao {{
        color: {TEXTO_FRACO};
        font-size: 12px;
    }}
    QLabel#tituloSecao {{
        color: {AVISO};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.2px;
        padding: 4px 14px 2px 14px;
    }}

    /* Itens de navegação (botões "planos") */
    QPushButton#nav {{
        background-color: transparent;
        border: none;
        border-radius: 10px;
        padding: 10px 14px;
        margin: 1px 8px;
        text-align: left;
        color: {TEXTO};
        font-size: 14px;
    }}
    QPushButton#nav:hover {{
        background-color: {PAINEL_ALTO};
        color: {TEXTO_FORTE};
    }}
    QPushButton#nav:checked {{
        background-color: {PAINEL_ALTO};
        color: {TEXTO_FORTE};
        border-left: 3px solid {ACENTO};
        font-weight: 700;
    }}

    /* ---------------- Cabeçalho ---------------- */
    QLabel#tituloPagina {{
        color: {TEXTO_FORTE};
        font-size: 22px;
        font-weight: 800;
    }}
    QLabel#subtituloPagina {{
        color: {TEXTO_FRACO};
        font-size: 13px;
    }}

    /* ---------------- Cartões ---------------- */
    QFrame#cartao {{
        background-color: {PAINEL};
        border: 1px solid {BORDA};
        border-radius: 16px;
    }}
    QFrame#cartao:hover {{
        border: 1px solid {BORDA_FORTE};
    }}
    QLabel#cartaoTitulo {{
        color: {TEXTO_FORTE};
        font-size: 15px;
        font-weight: 700;
    }}
    QLabel#cartaoDesc {{
        color: {TEXTO_FRACO};
        font-size: 13px;
    }}
    QLabel#chip {{
        background-color: {PAINEL_ALTO};
        border: 1px solid {BORDA};
        border-radius: 12px;
        padding: 4px 10px;
        color: {TEXTO};
        font-size: 12px;
    }}

    /* ---------------- Botões ---------------- */
    QPushButton {{
        background-color: {PAINEL_ALTO};
        border: 1px solid {BORDA_FORTE};
        border-radius: 10px;
        padding: 9px 16px;
        color: {TEXTO_FORTE};
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: #232b3a;
        border: 1px solid {ACENTO};
    }}
    QPushButton:disabled {{
        color: {TEXTO_FRACO};
        background-color: {PAINEL};
        border: 1px solid {BORDA};
    }}
    QPushButton#primario {{
        background-color: {ACENTO2};
        border: 1px solid {ACENTO2};
        color: #ffffff;
    }}
    QPushButton#primario:hover {{
        background-color: #2a7bff;
        border: 1px solid {ACENTO};
    }}
    QPushButton#perigo:hover {{
        border: 1px solid {ERRO};
        color: {ERRO};
    }}

    /* ---------------- Console de atividade ---------------- */
    QTextEdit#console {{
        background-color: #06090d;
        border: 1px solid {BORDA};
        border-radius: 12px;
        color: {TEXTO};
        font-family: 'Cascadia Code', 'Consolas', 'JetBrains Mono', monospace;
        font-size: 13px;
        padding: 10px;
    }}

    /* ---------------- Barra de progresso ---------------- */
    QProgressBar {{
        background-color: {PAINEL};
        border: 1px solid {BORDA};
        border-radius: 8px;
        height: 10px;
        text-align: center;
        color: {TEXTO_FRACO};
        font-size: 11px;
    }}
    QProgressBar::chunk {{
        background-color: {ACENTO};
        border-radius: 8px;
    }}

    /* ---------------- Diálogos ---------------- */
    QDialog, QMessageBox {{
        background-color: {PAINEL};
    }}
    QListWidget {{
        background-color: #06090d;
        border: 1px solid {BORDA};
        border-radius: 10px;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 7px 8px;
        border-radius: 6px;
    }}
    QListWidget::item:hover {{
        background-color: {PAINEL_ALTO};
    }}
    QListWidget::item:selected {{
        background-color: {ACENTO2};
        color: #ffffff;
    }}
    QLineEdit {{
        background-color: #06090d;
        border: 1px solid {BORDA_FORTE};
        border-radius: 8px;
        padding: 8px 10px;
        color: {TEXTO_FORTE};
    }}
    QLineEdit:focus {{
        border: 1px solid {ACENTO};
    }}

    /* ---------------- Barras de rolagem ---------------- */
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDA_FORTE};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {TEXTO_FRACO}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QStatusBar {{
        color: {TEXTO_FRACO};
        border-top: 1px solid {BORDA};
    }}
    QToolTip {{
        background-color: {PAINEL_ALTO};
        color: {TEXTO_FORTE};
        border: 1px solid {ACENTO};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    """
