"""Núcleo da ponte GUI ⇄ backend.

A ideia central: rodar os fluxos interativos do backend (``modulos.*.menu(estado)``)
exatamente como são, mas trocar *em tempo de execução* as primitivas do módulo
:mod:`modulos.interface` por versões que falam com a janela:

    * a saída do ``rich`` (cores, tabelas, painéis) é exportada como HTML e
      enviada para um console estilizado;
    * confirmações, menus e entradas de texto viram diálogos nativos do Qt;
    * as barras de progresso viram atualizações da barra/rótulo de status.

Como tudo no backend acessa essas funções via ``interface.<nome>`` (atributo do
módulo, resolvido na hora da chamada), basta reatribuir esses atributos durante
a execução e restaurá-los ao final — sem tocar em uma linha de lógica.

Concorrência: o backend roda numa :class:`Trabalhador` (QThread); a janela só
permite UMA tarefa por vez. Os diálogos são exibidos na thread principal e o
worker fica bloqueado, com segurança, até o usuário responder.
"""

from __future__ import annotations

import io
import logging
import traceback
from typing import Any, Callable, Optional, Sequence

from PySide6.QtCore import QMutex, QObject, QThread, QWaitCondition, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from rich.console import Console

import config
from modulos import interface, seguranca

# Sentinela para distinguir "ainda sem resposta" de uma resposta legítima None.
_SEM_RESPOSTA = object()


# ===========================================================================
# Console GUI: captura a saída do rich e a emite como HTML colorido.
# ===========================================================================
class _ConsoleGUI(Console):
    """Console do ``rich`` que, a cada ``print``, emite o trecho como HTML.

    Substitui ``interface.console``. Como TODAS as funções de saída da TUI
    (``sucesso``, ``aviso``, ``info``, ``texto``, ``cabecalho``, tabelas,
    painéis...) imprimem através desse console, trocar apenas este objeto já
    redireciona toda a saída para a janela — preservando as cores do tema.
    """

    def __init__(self, emitir: Callable[[str], None]) -> None:
        super().__init__(
            record=True,
            file=io.StringIO(),       # descarta a saída textual; usamos o record
            force_terminal=True,
            color_system="truecolor",
            width=110,
            highlight=False,
            soft_wrap=False,
        )
        self._emitir = emitir

    def print(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        super().print(*args, **kwargs)
        try:
            html = self.export_html(
                inline_styles=True,
                code_format="{code}",  # só o conteúdo, sem <html>/<pre> externos
                clear=True,            # zera o buffer p/ a próxima impressão
            )
        except Exception:  # noqa: BLE001 - exportação nunca pode derrubar a ação
            return
        if html.strip():
            self._emitir(html)


# ===========================================================================
# Progresso "falso": converte a API do rich.Progress em sinais de status.
# ===========================================================================
class _Progresso:
    """Imita a interface mínima de ``rich.Progress`` usada pelo backend.

    Suporta ``add_task``, ``update`` e ``advance`` (uso via ``with``). Em vez de
    desenhar no terminal, emite o texto e o percentual para a barra de status.
    """

    def __init__(self, ponte: "Ponte") -> None:
        self._ponte = ponte
        self._tarefas: dict[int, dict[str, Any]] = {}
        self._proximo = 0

    def __enter__(self) -> "_Progresso":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self._ponte.sig_status.emit("", -1)

    def add_task(self, description: str, total: Optional[float] = None, **_k: Any) -> int:
        tid = self._proximo
        self._proximo += 1
        self._tarefas[tid] = {"desc": description, "total": total, "feito": 0.0}
        self._emitir(tid)
        return tid

    def update(
        self,
        tid: int,
        *,
        completed: Optional[float] = None,
        advance: Optional[float] = None,
        description: Optional[str] = None,
        total: Optional[float] = None,
        **_k: Any,
    ) -> None:
        t = self._tarefas.get(tid)
        if t is None:
            return
        if description is not None:
            t["desc"] = description
        if total is not None:
            t["total"] = total
        if completed is not None:
            t["feito"] = completed
        if advance is not None:
            t["feito"] += advance
        self._emitir(tid)

    def advance(self, tid: int, passo: float = 1) -> None:
        t = self._tarefas.get(tid)
        if t is not None:
            t["feito"] += passo
            self._emitir(tid)

    def _emitir(self, tid: int) -> None:
        t = self._tarefas[tid]
        total = t["total"] or 0
        pct = int(max(0.0, min(1.0, t["feito"] / total)) * 100) if total else -1
        self._ponte.sig_status.emit(str(t["desc"]), pct)


# ===========================================================================
# Ponte: vive na thread PRINCIPAL e media saída + perguntas.
# ===========================================================================
class Ponte(QObject):
    """Canal thread-safe entre o worker (backend) e a janela.

    Sinais de saída (worker -> GUI) são entregues de forma assíncrona. As
    perguntas (worker -> GUI -> worker) bloqueiam o worker até a resposta,
    usando ``QWaitCondition`` — sem nunca travar a thread da interface.
    """

    sig_saida = Signal(str)          # HTML para o console
    sig_status = Signal(str, int)    # (texto, percentual | -1 p/ indeterminado)
    sig_limpar = Signal()            # limpar o console
    _sig_pergunta = Signal(dict)     # interno: pedir interação na thread da GUI

    def __init__(self, janela: QWidget) -> None:
        super().__init__()
        self._janela = janela
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._resposta: Any = _SEM_RESPOSTA
        # Conexão em fila (cross-thread): o slot roda SEMPRE na thread da GUI.
        self._sig_pergunta.connect(self._tratar_pergunta, Qt.ConnectionType.QueuedConnection)

    # ---- API de saída (chamada na thread do worker) ----
    def saida_html(self, html: str) -> None:
        self.sig_saida.emit(html)

    # ---- Perguntas: bloqueiam o worker até a thread da GUI responder ----
    def _perguntar(self, req: dict[str, Any]) -> Any:
        self._mutex.lock()
        try:
            self._resposta = _SEM_RESPOSTA
            self._sig_pergunta.emit(req)
            while self._resposta is _SEM_RESPOSTA:
                self._cond.wait(self._mutex)
            return self._resposta
        finally:
            self._mutex.unlock()

    @Slot(dict)
    def _tratar_pergunta(self, req: dict[str, Any]) -> None:
        """Executa na thread da GUI: monta o diálogo e devolve a resposta."""
        try:
            resposta = self._dispatch(req)
        except Exception:  # noqa: BLE001 - nunca deixar o worker pendurado
            resposta = req.get("padrao")
        self._mutex.lock()
        self._resposta = resposta
        self._cond.wakeAll()
        self._mutex.unlock()

    def _dispatch(self, req: dict[str, Any]) -> Any:
        tipo = req["tipo"]
        if tipo == "confirmar":
            return self._dlg_confirmar(req["pergunta"], req.get("padrao", False))
        if tipo == "texto":
            return self._dlg_texto(req["pergunta"], req.get("padrao", ""))
        if tipo == "selecao":
            return _DialogoSelecao(self._janela, req["titulo"], req["opcoes"], False).executar()
        if tipo == "multiplo":
            return _DialogoSelecao(self._janela, req["titulo"], req["opcoes"], True).executar()
        if tipo == "pausar":
            QMessageBox.information(self._janela, config.NOME_APP, req.get("mensagem", "Continuar"))
            return None
        return req.get("padrao")

    def _dlg_confirmar(self, pergunta: str, padrao: bool) -> bool:
        cx = QMessageBox(self._janela)
        cx.setWindowTitle(config.NOME_APP)
        cx.setText(_limpar_markup(pergunta))
        cx.setIcon(QMessageBox.Icon.Question)
        cx.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        cx.setDefaultButton(
            QMessageBox.StandardButton.Yes if padrao else QMessageBox.StandardButton.No
        )
        cx.button(QMessageBox.StandardButton.Yes).setText("Sim")
        cx.button(QMessageBox.StandardButton.No).setText("Não")
        return cx.exec() == QMessageBox.StandardButton.Yes

    def _dlg_texto(self, pergunta: str, padrao: str) -> str:
        dlg = QDialog(self._janela)
        dlg.setWindowTitle(config.NOME_APP)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)
        lay.addWidget(QLabel(_limpar_markup(pergunta)))
        campo = QLineEdit(padrao)
        lay.addWidget(campo)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(dlg.accept)
        botoes.rejected.connect(dlg.reject)
        lay.addWidget(botoes)
        campo.setFocus()
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return campo.text().strip()
        return ""


class _DialogoSelecao(QDialog):
    """Diálogo de seleção única (lista) ou múltipla (checkboxes)."""

    def __init__(
        self,
        pai: QWidget,
        titulo: str,
        opcoes: Sequence[tuple[str, Any]],
        multiplo: bool,
    ) -> None:
        super().__init__(pai)
        self.setWindowTitle(config.NOME_APP)
        self.setMinimumWidth(520)
        self._multiplo = multiplo
        self._valores: list[Any] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)
        rotulo = QLabel(_limpar_markup(titulo))
        rotulo.setWordWrap(True)
        lay.addWidget(rotulo)

        if multiplo:
            area = QScrollArea()
            area.setWidgetResizable(True)
            interno = QWidget()
            vint = QVBoxLayout(interno)
            vint.setSpacing(6)
            self._checks: list[tuple[QCheckBox, Any]] = []
            for texto_op, valor in opcoes:
                cb = QCheckBox(_limpar_markup(texto_op))
                vint.addWidget(cb)
                self._checks.append((cb, valor))
            vint.addStretch(1)
            area.setWidget(interno)
            area.setMinimumHeight(min(420, 80 + 34 * max(1, len(opcoes))))
            lay.addWidget(area)
        else:
            self._lista = QListWidget()
            for texto_op, valor in opcoes:
                item = QListWidgetItem(_limpar_markup(texto_op))
                item.setData(Qt.ItemDataRole.UserRole, valor)
                self._lista.addItem(item)
            if opcoes:
                self._lista.setCurrentRow(0)
            self._lista.itemDoubleClicked.connect(lambda *_: self.accept())
            lay.addWidget(self._lista)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Confirmar seleção" if multiplo else "Selecionar"
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        lay.addWidget(botoes)

    def executar(self) -> Any:
        if self.exec() != QDialog.DialogCode.Accepted:
            return [] if self._multiplo else None
        if self._multiplo:
            return [valor for cb, valor in self._checks if cb.isChecked()]
        item = self._lista.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None


# ===========================================================================
# Monkeypatch: aplica/restaura as primitivas do módulo `interface`.
# ===========================================================================
_ATRIBUTOS = (
    "console",
    "confirmar",
    "menu_selecao",
    "menu_multiplo",
    "pedir_texto",
    "pausar",
    "barra_progresso",
    "spinner",
    "limpar_tela",
)


def _limpar_markup(texto: str) -> str:
    """Renderiza marcação do ``rich`` (ex.: ``[bold]``) para texto plano.

    Usado nos diálogos nativos, que não entendem a marcação do rich.
    """
    try:
        from rich.text import Text

        return Text.from_markup(str(texto)).plain
    except Exception:  # noqa: BLE001
        return str(texto)


def aplicar_ponte(ponte: Ponte) -> dict[str, Any]:
    """Substitui as primitivas de ``interface`` pelas versões gráficas.

    Retorna um dicionário com os atributos originais, para restauração.
    """
    originais = {nome: getattr(interface, nome) for nome in _ATRIBUTOS}

    interface.console = _ConsoleGUI(ponte.saida_html)

    def _confirmar(pergunta: str, padrao: bool = False) -> bool:
        return bool(ponte._perguntar({"tipo": "confirmar", "pergunta": pergunta, "padrao": padrao}))

    def _menu_selecao(titulo: str, opcoes: Sequence[Any]) -> Any:
        return ponte._perguntar({"tipo": "selecao", "titulo": titulo, "opcoes": _so_pares(opcoes)})

    def _menu_multiplo(titulo: str, opcoes: Sequence[Any]) -> list[Any]:
        return ponte._perguntar({"tipo": "multiplo", "titulo": titulo, "opcoes": _so_pares(opcoes)})

    def _pedir_texto(pergunta: str, padrao: str = "") -> str:
        return str(ponte._perguntar({"tipo": "texto", "pergunta": pergunta, "padrao": padrao}) or "")

    def _pausar(mensagem: str = "Pressione Enter para continuar...") -> None:
        ponte._perguntar({"tipo": "pausar", "mensagem": mensagem})

    interface.confirmar = _confirmar
    interface.menu_selecao = _menu_selecao
    interface.menu_multiplo = _menu_multiplo
    interface.pedir_texto = _pedir_texto
    interface.pausar = _pausar
    interface.barra_progresso = lambda: _Progresso(ponte)
    interface.spinner = lambda _descricao="": _Progresso(ponte)
    interface.limpar_tela = lambda: None
    return originais


def restaurar_ponte(originais: dict[str, Any]) -> None:
    """Restaura as primitivas originais de ``interface``."""
    for nome, valor in originais.items():
        setattr(interface, nome, valor)


def _so_pares(opcoes: Sequence[Any]) -> list[tuple[str, Any]]:
    """Filtra separadores do menu da TUI, mantendo só pares (rótulo, valor)."""
    pares: list[tuple[str, Any]] = []
    for op in opcoes:
        if isinstance(op, tuple) and len(op) == 2:
            pares.append((str(op[0]), op[1]))
    return pares


# ===========================================================================
# Trabalhador: roda uma ação do backend numa thread separada.
# ===========================================================================
class Trabalhador(QThread):
    """Executa um ``alvo`` (callable do backend) fora da thread da interface.

    Aplica a ponte antes e a restaura depois (try/finally), de modo que uma
    falha em qualquer ação nunca deixe o ``interface`` em estado inconsistente.
    O valor de retorno do alvo é entregue via :attr:`sig_resultado`.
    """

    sig_resultado = Signal(object)
    sig_fim = Signal(str)

    def __init__(self, ponte: Ponte, alvo: Callable[[], Any], rotulo: str) -> None:
        super().__init__()
        self._ponte = ponte
        self._alvo = alvo
        self._rotulo = rotulo

    def run(self) -> None:  # noqa: D401 - executa na thread do worker
        originais = aplicar_ponte(self._ponte)
        resultado: Any = None
        try:
            resultado = self._alvo()
        except Exception as exc:  # noqa: BLE001 - blindagem total da ação
            seguranca.registrar(
                f"[gui] erro em '{self._rotulo}': {exc}\n{traceback.format_exc()}",
                logging.ERROR,
            )
            self._ponte.saida_html(
                f"<div style='color:{ '#f85149' }'>✖ Ocorreu um erro nesta ação "
                f"({_limpar_markup(self._rotulo)}), mas o programa continua "
                f"funcionando.<br>Detalhe: {_limpar_markup(str(exc))}</div>"
            )
        finally:
            restaurar_ponte(originais)
            self.sig_resultado.emit(resultado)
            self.sig_fim.emit(self._rotulo)
