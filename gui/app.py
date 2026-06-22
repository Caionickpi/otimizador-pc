"""Ponto de entrada da interface gráfica.

Cria o ``QApplication``, aplica o tema premium e exibe a janela principal.
Toda a inicialização "de sistema" (pastas, logging) é feita aqui, espelhando o
que o modo terminal faz em :func:`main.main`.
"""

from __future__ import annotations

import logging
import sys

import config
from modulos import seguranca


def iniciar() -> int:
    """Sobe a janela do Otimizador PC. Retorna o código de saída do processo."""
    config.garantir_pastas()
    seguranca.configurar_logging()
    seguranca.registrar(
        f"Iniciando {config.NOME_APP} v{config.VERSAO_APP} (modo janela / GUI).",
        logging.INFO,
    )

    # Importado aqui dentro para que uma ausência do PySide6 seja tratada pelo
    # chamador (main.py), que então cai no modo terminal com uma mensagem clara.
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication

    from gui import tema
    from gui.janela import JanelaPrincipal

    # Nitidez em telas de alta resolução (4K, notebooks modernos).
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.NOME_APP)
    app.setApplicationDisplayName(config.NOME_APP)
    app.setApplicationVersion(config.VERSAO_APP)
    app.setStyleSheet(tema.folha_estilo())
    app.setFont(QFont("Segoe UI", 10))

    icone = _carregar_icone()
    if icone is not None:
        app.setWindowIcon(icone)

    janela = JanelaPrincipal()
    if icone is not None:
        janela.setWindowIcon(icone)
    janela.show()

    codigo = app.exec()
    seguranca.registrar("Janela encerrada pelo usuário.", logging.INFO)
    return int(codigo)


def _carregar_icone():
    """Retorna o ícone do app, se existir um ``dados/icone.ico`` empacotado."""
    try:
        from PySide6.QtGui import QIcon

        caminho = config.caminho_recurso("dados/icone.ico")
        if caminho.exists():
            return QIcon(str(caminho))
    except Exception:  # noqa: BLE001 - ausência de ícone nunca pode quebrar a abertura
        pass
    return None
