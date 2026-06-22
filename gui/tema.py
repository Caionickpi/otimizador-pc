"""Tema visual premium (paleta + folha de estilo QSS) da janela.

A paleta deriva das cores da marca (definidas em :mod:`config`) para manter a
identidade entre o modo janela e o modo terminal. O estilo é escuro, com
superfícies em camadas, realces em ciano/azul, gradientes sutis e cantos
arredondados — pensado para passar a sensação de produto pago e exclusivo.
"""

from __future__ import annotations

import config

# ---------------------------------------------------------------------------
# Paleta — fundo profundo (navy-black) com superfícies em camadas.
# ---------------------------------------------------------------------------
FUNDO = "#0a0e15"          # fundo da janela (quase preto azulado)
FUNDO_BARRA = "#0c111b"    # barra lateral / título
PAINEL = "#141a24"         # cartões / superfícies
PAINEL_ALTO = "#1b2230"    # superfícies em destaque / hover
BORDA = "#232c3b"          # bordas sutis
BORDA_FORTE = "#36415a"    # bordas em destaque / hover
TRILHO = "#1b2230"         # trilho do anel de saúde

TEXTO = "#d7dee8"          # texto comum (claro, alto contraste)
TEXTO_FRACO = "#7d8a99"    # texto apagado / dicas
TEXTO_FORTE = "#ffffff"

OK = config.COR_OK                 # #3fb950 verde
AVISO = config.COR_AVISO           # #d29922 âmbar
ERRO = config.COR_ERRO             # #f85149 vermelho
INFO = config.COR_INFO             # #58a6ff azul
ACENTO = config.COR_ACENTO         # #39d0d8 ciano
ACENTO2 = "#2f6bff"                # azul forte (seleção / primário)


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
        font-family: 'Segoe UI Variable Display', 'Segoe UI', 'Inter',
                     'Ubuntu', 'Helvetica Neue', sans-serif;
        font-size: 14px;
        color: {TEXTO};
        outline: 0;
    }}

    /* Moldura externa da janela sem bordas (cantos arredondados). */
    QFrame#frameJanela {{
        background-color: {FUNDO};
        border: 1px solid {BORDA};
        border-radius: 14px;
    }}
    QFrame#frameJanela[maximizado="true"] {{
        border-radius: 0px;
        border: 0px;
    }}

    /* ---------------- Barra de título ---------------- */
    QWidget#barraTitulo {{
        background-color: {FUNDO_BARRA};
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
        border-bottom: 1px solid {BORDA};
    }}
    QLabel#tituloJanela {{
        color: {TEXTO};
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.4px;
    }}
    QPushButton#btnJanela, QPushButton#btnFechar {{
        background: transparent;
        border: none;
        border-radius: 7px;
        color: {TEXTO_FRACO};
        font-size: 14px;
    }}
    QPushButton#btnJanela:hover {{
        background-color: {PAINEL_ALTO};
        color: {TEXTO_FORTE};
    }}
    QPushButton#btnFechar:hover {{
        background-color: {ERRO};
        color: #ffffff;
    }}

    /* ---------------- Barra lateral ---------------- */
    QWidget#barraLateral {{
        background-color: {FUNDO_BARRA};
        border-right: 1px solid {BORDA};
    }}
    QLabel#marca {{
        color: {TEXTO_FORTE};
        font-size: 17px;
        font-weight: 800;
        letter-spacing: 0.3px;
    }}
    QLabel#marcaVersao {{
        color: {TEXTO_FRACO};
        font-size: 11px;
    }}
    QLabel#tituloSecao {{
        color: {TEXTO_FRACO};
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 1.6px;
        padding: 10px 16px 4px 16px;
    }}

    /* Itens de navegação */
    QPushButton#nav {{
        background-color: transparent;
        border: none;
        border-radius: 10px;
        padding: 10px 14px;
        margin: 1px 10px;
        text-align: left;
        color: {TEXTO};
        font-size: 13.5px;
    }}
    QPushButton#nav:hover {{
        background-color: {PAINEL_ALTO};
        color: {TEXTO_FORTE};
    }}
    QPushButton#nav:checked {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(47,107,255,0.22), stop:1 rgba(57,208,216,0.06));
        color: {TEXTO_FORTE};
        font-weight: 700;
    }}

    /* ---------------- Cabeçalho da página ---------------- */
    QLabel#tituloPagina {{
        color: {TEXTO_FORTE};
        font-size: 23px;
        font-weight: 800;
        letter-spacing: 0.2px;
    }}
    QLabel#subtituloPagina {{
        color: {TEXTO_FRACO};
        font-size: 13px;
    }}
    QLabel#rotuloSim {{
        color: {TEXTO_FRACO};
        font-size: 12px;
        font-weight: 600;
    }}

    /* ---------------- Cartões ---------------- */
    QFrame#cartao {{
        background-color: {PAINEL};
        border: 1px solid {BORDA};
        border-radius: 16px;
    }}
    QFrame#cartao:hover {{ border: 1px solid {BORDA_FORTE}; }}
    QLabel#cartaoTitulo {{
        color: {TEXTO_FORTE};
        font-size: 15px;
        font-weight: 700;
    }}
    QLabel#cartaoDesc {{ color: {TEXTO_FRACO}; font-size: 13px; }}

    /* KPIs (indicadores) */
    QFrame#kpi {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {PAINEL_ALTO}, stop:1 {PAINEL});
        border: 1px solid {BORDA};
        border-radius: 14px;
    }}
    QFrame#kpi:hover {{ border: 1px solid {ACENTO}; }}
    QLabel#kpiIcone {{ font-size: 18px; }}
    QLabel#kpiValor {{ color: {TEXTO_FORTE}; font-size: 21px; font-weight: 800; }}
    QLabel#kpiRotulo {{ color: {TEXTO_FRACO}; font-size: 12px; }}

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
        padding: 10px 16px;
        color: {TEXTO_FORTE};
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: #232c3e; border: 1px solid {ACENTO}; }}
    QPushButton:pressed {{ background-color: #1a2130; }}
    QPushButton:disabled {{
        color: {TEXTO_FRACO};
        background-color: {PAINEL};
        border: 1px solid {BORDA};
    }}
    QPushButton#primario {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {ACENTO2}, stop:1 #1f9bd1);
        border: none;
        color: #ffffff;
        font-weight: 700;
    }}
    QPushButton#primario:hover {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #3f7bff, stop:1 {ACENTO});
    }}
    QPushButton#primario:disabled {{
        background: {PAINEL}; color: {TEXTO_FRACO};
    }}
    QPushButton#pill {{
        background-color: {PAINEL_ALTO};
        border: 1px solid {BORDA};
        border-radius: 14px;
        padding: 7px 14px;
        font-size: 12.5px;
        font-weight: 600;
    }}
    QPushButton#pill:hover {{ border: 1px solid {ACENTO}; }}
    QPushButton#perigo:hover {{ border: 1px solid {ERRO}; color: {ERRO}; }}

    /* ---------------- Console de atividade ---------------- */
    QLabel#consoleTitulo {{
        color: {TEXTO_FRACO}; font-size: 11px; font-weight: 800; letter-spacing: 1.4px;
    }}
    QTextEdit#console {{
        background-color: #070a10;
        border: 1px solid {BORDA};
        border-radius: 14px;
        color: {TEXTO};
        font-family: 'Cascadia Code', 'Consolas', 'JetBrains Mono', monospace;
        font-size: 13px;
        padding: 12px;
        selection-background-color: {ACENTO2};
    }}

    /* ---------------- Barra de progresso / rodapé ---------------- */
    QProgressBar {{
        background-color: {PAINEL};
        border: 1px solid {BORDA};
        border-radius: 7px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {ACENTO2}, stop:1 {ACENTO});
        border-radius: 7px;
    }}
    QWidget#rodape {{ border-top: 1px solid {BORDA}; }}
    QLabel#statusTexto {{ color: {TEXTO_FRACO}; font-size: 12px; }}

    /* ---------------- Diálogos / entradas ---------------- */
    QDialog, QMessageBox {{ background-color: {PAINEL}; }}
    QListWidget {{
        background-color: #070a10;
        border: 1px solid {BORDA};
        border-radius: 10px;
        padding: 4px;
    }}
    QListWidget::item {{ padding: 8px 8px; border-radius: 7px; }}
    QListWidget::item:hover {{ background-color: {PAINEL_ALTO}; }}
    QListWidget::item:selected {{ background-color: {ACENTO2}; color: #ffffff; }}
    QLineEdit {{
        background-color: #070a10;
        border: 1px solid {BORDA_FORTE};
        border-radius: 8px;
        padding: 9px 11px;
        color: {TEXTO_FORTE};
        selection-background-color: {ACENTO2};
    }}
    QLineEdit:focus {{ border: 1px solid {ACENTO}; }}

    /* ---------------- Barras de rolagem ---------------- */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: {BORDA_FORTE}; border-radius: 5px; min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {TEXTO_FRACO}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{
        background: {BORDA_FORTE}; border-radius: 5px; min-width: 32px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QToolTip {{
        background-color: {PAINEL_ALTO};
        color: {TEXTO_FORTE};
        border: 1px solid {ACENTO};
        border-radius: 6px;
        padding: 5px 9px;
    }}
    """
