"""Premium: perfis de otimização em 1 clique.

Aplica um pacote curado de ajustes adaptado ao seu hardware e ao seu uso —
em vez de o usuário caçar opção por opção. Tudo é montado a partir dos
construtores de valores já existentes (avançado, input lag e efeitos visuais)
e aplicado pelo MESMO motor seguro (avancado._aplicar_pacote): backup .reg,
ponto de restauração, confirmação, modo simulação e desfazer PRECISO.

Perfis:
    🎮 Gamer            — desempenho e latência para jogos.
    💼 Trabalho         — interface enxuta e teclado responsivo.
    🐌 Máquina fraca    — alívio máximo de animações/latência (PCs modestos).
    🔋 Notebook         — leveza sem mexer em energia/GPU (preserva bateria).
"""

from __future__ import annotations

import sys
from typing import Any

import config
from modulos import hardware, interface
from modulos.tweaks import avancado, inputlag

try:  # pragma: no cover
    import winreg  # type: ignore

    _SZ, _DWORD = winreg.REG_SZ, winreg.REG_DWORD
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore
    _SZ, _DWORD = 1, 4

Valor = tuple[str, str, str, int, Any]


def _valores_visual() -> list[Valor]:
    """Efeitos visuais voltados a desempenho (mesmos da aba Visual, em HKCU)."""
    av = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
    return [
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
         "VisualFXSetting", _DWORD, 2),
        ("HKCU", av, "TaskbarAnimations", _DWORD, 0),
        ("HKCU", av, "ListviewAlphaSelect", _DWORD, 0),
        ("HKCU", av, "ListviewShadow", _DWORD, 0),
        ("HKCU", r"Control Panel\Desktop", "DragFullWindows", _SZ, "0"),
        ("HKCU", r"Control Panel\Desktop\WindowMetrics", "MinAnimate", _SZ, "0"),
    ]


def _dedup(valores: list[Valor]) -> list[Valor]:
    """Remove valores repetidos mantendo a ordem (perfis combinam pacotes)."""
    visto: set[tuple[str, str, str]] = set()
    saida: list[Valor] = []
    for v in valores:
        chave = (v[0], v[1].lower(), v[2].lower())
        if chave not in visto:
            visto.add(chave)
            saida.append(v)
    return saida


# ---------------------------------------------------------------------------
# Construtores de perfil (retornam valores + texto + se exige reinício)
# ---------------------------------------------------------------------------
def _perfil_gamer(hw: dict[str, Any]) -> dict[str, Any]:
    valores = (
        avancado.valores_pacote_jogos()
        + inputlag._valores_mouse()
        + inputlag._valores_monitor()
    )
    dicas = ["Modo Jogo + Game DVR off, prioridade p/ jogos (MMCSS), HAGS, "
             "mouse 1:1 e tela cheia sem composição."]
    if hw.get("notebook"):
        dicas.append("⚠ Notebook: aplico os ajustes, mas NÃO forço plano de energia "
                     "(evito gastar bateria). Para o máximo, jogue na tomada.")
    if not hw.get("tem_dgpu"):
        dicas.append("Sem GPU dedicada detectada: os ajustes de GPU são inofensivos "
                     "e o ganho vem mais do Modo Jogo e da latência.")
    return {"valores": _dedup(valores), "dicas": dicas, "reinicio": True}


def _perfil_trabalho(hw: dict[str, Any]) -> dict[str, Any]:
    valores = _valores_visual() + inputlag._valores_teclado()
    return {"valores": _dedup(valores),
            "dicas": ["Interface enxuta (sem animações pesadas) e teclado mais "
                      "responsivo — foco em produtividade, risco baixo."],
            "reinicio": False}


def _perfil_leve(hw: dict[str, Any]) -> dict[str, Any]:
    valores = (
        _valores_visual()
        + inputlag._valores_mouse()
        + inputlag._valores_teclado()
        + inputlag._valores_monitor()
    )
    return {"valores": _dedup(valores),
            "dicas": ["Alívio máximo para PCs modestos: desliga animações, deixa "
                      "mouse/teclado 1:1 e tira a composição de tela cheia. "
                      "Nada que mexa em energia/GPU pesada."],
            "reinicio": False}


def _perfil_notebook(hw: dict[str, Any]) -> dict[str, Any]:
    valores = _valores_visual() + inputlag._valores_teclado()
    return {"valores": _dedup(valores),
            "dicas": ["Leveza que também ajuda a bateria (menos animações), sem "
                      "tocar em plano de energia nem GPU. Para economia de bateria, "
                      "mantenha o plano 'Equilibrado'."],
            "reinicio": False}


_PERFIS = {
    "gamer": ("🎮  Gamer (desempenho + latência p/ jogos)", _perfil_gamer),
    "trabalho": ("💼  Trabalho (interface enxuta + teclado responsivo)", _perfil_trabalho),
    "leve": ("🐌  Máquina fraca (alívio máximo de animações/latência)", _perfil_leve),
    "notebook": ("🔋  Notebook (leveza sem mexer em energia/GPU)", _perfil_notebook),
}


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Escolhe um perfil e aplica o pacote correspondente (adaptado ao hardware)."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    interface.cabecalho("⚡ Perfis de otimização (1 clique)",
                        "Um pacote pronto e seguro, adaptado ao seu PC.")

    hw: dict[str, Any] = {}
    if estado.diagnostico_pronto():
        hw = hardware.perfil_otimizacao(estado.perfil)
        interface.info(f"Seu PC: [bold]{interface.escapar(hardware.resumo_curto(hw))}[/bold]")
    else:
        interface.texto("Dica: rode o Diagnóstico antes para eu adaptar melhor ao seu hardware.",
                        config.COR_DIM)

    opcoes = [(rotulo, chave) for chave, (rotulo, _f) in _PERFIS.items()]
    opcoes.append(("↩  Voltar", "voltar"))
    escolha = interface.menu_selecao("Qual perfil deseja aplicar?", opcoes)
    if escolha in (None, "voltar"):
        return

    rotulo, construtor = _PERFIS[escolha]
    perfil = construtor(hw)
    nome_limpo = rotulo.split("(")[0].strip()
    descricao = (
        f"Perfil [bold]{interface.escapar(nome_limpo)}[/bold] — "
        f"{len(perfil['valores'])} ajustes em um pacote único.\n\n"
        + "\n".join(f"• {d}" for d in perfil["dicas"])
    )
    avancado._aplicar_pacote(
        estado,
        titulo=f"Perfil {nome_limpo}",
        descricao=descricao,
        riscos="Risco BAIXO–MÉDIO e 100% reversível em 'Desfazer última alteração'. "
        "Itens do sistema (HKLM) podem exigir administrador; sem ele, aplico os do usuário.",
        valores=perfil["valores"],
        exige_reinicio=perfil["reinicio"],
        modulo="perfis",
        cabecalho_titulo=f"⚡ Perfil {nome_limpo}",
    )
