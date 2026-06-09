"""Tweak: reduzir o INPUT LAG (latência de entrada) de mouse, teclado e monitor.

Reúne ajustes focados na resposta dos periféricos e da exibição — ótimos para
jogos e para uma sensação geral mais "instantânea". Quase tudo aqui vive em
HKCU, então NÃO exige administrador (diferente da aba Avançados).

Fiel ao projeto: cada pacote descreve o que faz, avisa os riscos, faz backup
(.reg), pede confirmação, respeita o modo simulação e registra um "desfazer"
PRECISO — tudo reaproveitando o motor seguro de :func:`avancado._aplicar_pacote`.

Efeito: a maioria dos ajustes de mouse/teclado é lida no logon do Windows;
faça logoff/login (ou reinicie) para aplicá-los 100%.
"""

from __future__ import annotations

import sys
from typing import Any

import config
from modulos import interface
from modulos.tweaks import avancado

try:  # pragma: no cover - só há registro no Windows
    import winreg  # type: ignore

    _SZ, _DWORD = winreg.REG_SZ, winreg.REG_DWORD
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore
    # Valores reais das constantes do registro do Windows, para que os pacotes
    # possam ser montados/testados mesmo fora do Windows: REG_SZ=1, REG_DWORD=4.
    _SZ, _DWORD = 1, 4

# Um valor de registro no formato esperado por avancado._aplicar_pacote:
#   (raiz, subchave, nome, tipo, dado)
Valor = tuple[str, str, str, int, Any]


# ---------------------------------------------------------------------------
# Construtores de valores (um por periférico)
# ---------------------------------------------------------------------------
def _valores_mouse() -> list[Valor]:
    """Mouse 1:1: desativa a 'precisão aprimorada do ponteiro' (aceleração) e
    fixa a sensibilidade no padrão 6/11 (movimento linear, sem aceleração)."""
    base = r"Control Panel\Mouse"
    return [
        ("HKCU", base, "MouseSpeed", _SZ, "0"),
        ("HKCU", base, "MouseThreshold1", _SZ, "0"),
        ("HKCU", base, "MouseThreshold2", _SZ, "0"),
        ("HKCU", base, "MouseSensitivity", _SZ, "10"),
    ]


def _valores_teclado() -> list[Valor]:
    """Teclado responsivo: desliga os atrasos de acessibilidade (Sticky/Filter/
    Toggle Keys) e deixa a repetição de tecla no mais rápido (delay mínimo)."""
    aces = r"Control Panel\Accessibility"
    return [
        # Flags "off" padrão de cada recurso de acessibilidade.
        ("HKCU", aces + r"\StickyKeys", "Flags", _SZ, "506"),
        ("HKCU", aces + r"\Keyboard Response", "Flags", _SZ, "122"),
        ("HKCU", aces + r"\ToggleKeys", "Flags", _SZ, "58"),
        # Repetição de tecla: menor atraso (0) e maior velocidade (31).
        ("HKCU", r"Control Panel\Keyboard", "KeyboardDelay", _SZ, "0"),
        ("HKCU", r"Control Panel\Keyboard", "KeyboardSpeed", _SZ, "31"),
    ]


def _valores_monitor() -> list[Valor]:
    """Exibição: desativa as otimizações de tela cheia (FSE) e o Game DVR, que
    inserem uma camada de composição/captura e somam latência de apresentação."""
    base = r"System\GameConfigStore"
    return [
        ("HKCU", base, "GameDVR_FSEBehaviorMode", _DWORD, 2),
        ("HKCU", base, "GameDVR_HonorUserFSEBehaviorMode", _DWORD, 1),
        ("HKCU", base, "GameDVR_FSEBehavior", _DWORD, 2),
        ("HKCU", base, "GameDVR_DXGIHonorFSEWindowsCompatible", _DWORD, 1),
        ("HKCU", base, "GameDVR_Enabled", _DWORD, 0),
    ]


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------
def _acao_mouse(estado: config.EstadoApp) -> None:
    avancado._aplicar_pacote(
        estado,
        titulo="Mouse 1:1 (sem aceleração)",
        descricao="Desativa a 'Precisão aprimorada do ponteiro' (aceleração do "
        "mouse) e fixa a sensibilidade no padrão 6/11 — o movimento vira 1:1 com "
        "a mira, como a maioria dos jogadores prefere.",
        riscos="Risco BAIXO e reversível. NÃO exige administrador (só HKCU). O "
        "ponteiro pode parecer mais 'lento' fora do jogo — compense pelo DPI do mouse.",
        valores=_valores_mouse(),
        exige_reinicio=True,
        modulo="inputlag",
        cabecalho_titulo="🖱 Input lag · Mouse",
    )


def _acao_teclado(estado: config.EstadoApp) -> None:
    avancado._aplicar_pacote(
        estado,
        titulo="Teclado responsivo (sem atrasos)",
        descricao="Desliga as Teclas de Aderência/Filtragem/Alternância (aquele "
        "atraso e o atalho do Shift 5×) e coloca a repetição de tecla no mais "
        "rápido, com o menor atraso inicial.",
        riscos="Risco BAIXO e reversível. NÃO exige administrador (só HKCU). Se "
        "você usa esses recursos de acessibilidade de propósito, pule este item.",
        valores=_valores_teclado(),
        exige_reinicio=True,
        modulo="inputlag",
        cabecalho_titulo="⌨ Input lag · Teclado",
    )


def _acao_monitor(estado: config.EstadoApp) -> None:
    avancado._aplicar_pacote(
        estado,
        titulo="Monitor/exibição (desativar otimizações de tela cheia)",
        descricao="Desativa as Otimizações de Tela Cheia (FSE) e o Game DVR no "
        "perfil do sistema, favorecendo a tela cheia exclusiva — caminho com "
        "menor latência de apresentação na maioria dos jogos.",
        riscos="Risco MÉDIO e reversível. Pode afetar Alt+Tab/HDR em alguns "
        "jogos; se algo ficar estranho, use 'Desfazer última alteração'.",
        valores=_valores_monitor(),
        modulo="inputlag",
        cabecalho_titulo="🖥 Input lag · Monitor",
    )


def _acao_tudo(estado: config.EstadoApp) -> None:
    avancado._aplicar_pacote(
        estado,
        titulo="Reduzir input lag (mouse + teclado + monitor)",
        descricao="Aplica de uma vez os três pacotes: mouse 1:1 (sem aceleração), "
        "teclado sem atrasos + repetição rápida e exibição sem otimizações de "
        "tela cheia. Pacote completo de latência de entrada.",
        riscos="Risco BAIXO–MÉDIO e totalmente reversível. A maior parte é HKCU "
        "(sem admin). Faça logoff/reinício para aplicar 100%.",
        valores=_valores_mouse() + _valores_teclado() + _valores_monitor(),
        exige_reinicio=True,
        modulo="inputlag",
        cabecalho_titulo="⚡ Reduzir input lag · Tudo",
    )


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo dos ajustes de input lag."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    acoes = {
        "mouse": _acao_mouse,
        "teclado": _acao_teclado,
        "monitor": _acao_monitor,
        "tudo": _acao_tudo,
    }

    while True:
        interface.cabecalho(
            "🖱 Reduzir input lag",
            "Resposta de mouse, teclado e monitor — quase tudo sem precisar de admin.",
        )
        interface.info(
            "Estes ajustes reduzem a latência de entrada (aquele atraso entre você "
            "mexer no periférico e a tela responder). Tudo é reversível em "
            "'Desfazer última alteração'.\n"
            "Dica: a maioria dos efeitos de mouse/teclado entra em vigor após "
            "logoff/login (ou reiniciar)."
        )

        opcoes = [
            ("🖱  Mouse 1:1 (desativar aceleração)", "mouse"),
            ("⌨  Teclado responsivo (sem atrasos + repetição rápida)", "teclado"),
            ("🖥  Monitor/exibição (desativar otimizações de tela cheia)", "monitor"),
            interface.separador("Tudo de uma vez"),
            ("⚡  Aplicar TUDO (mouse + teclado + monitor)", "tudo"),
            ("↩  Voltar", "voltar"),
        ]
        escolha = interface.menu_selecao("Qual ajuste de input lag deseja aplicar?", opcoes)
        if escolha in (None, "voltar"):
            return
        funcao = acoes.get(escolha)
        if funcao:
            funcao(estado)
            interface.pausar()
