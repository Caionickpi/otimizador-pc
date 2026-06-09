"""Tweak: otimização POR JOGO (experiência específica por hardware + jogo).

Fluxo: detectar o hardware (rápido) -> detectar jogos instalados (Steam/Epic)
-> o usuário escolhe um jogo -> aplicamos um perfil de otimização adaptado ao
hardware e ao tipo de jogo (competitivo x geral).

O que é aplicado, tudo reversível em "Desfazer última alteração":
    * Por executável do jogo (HKCU, sem admin):
        - Preferência de GPU = Alto desempenho (ótimo em notebooks híbridos).
        - Desativar otimizações de tela cheia (pode reduzir latência/stutter).
    * Pacote global de jogo (Modo Jogo, Game DVR off, MMCSS, HAGS, prioridade).
    * Se o jogo for competitivo: também reduz a latência de rede (Nagle).
"""

from __future__ import annotations

import sys
from pathlib import Path

import config
from modulos import diagnostico, hardware, interface
from modulos import jogos as deteccao

try:  # pragma: no cover
    import winreg  # type: ignore
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore


def _garantir_perfil(estado: config.EstadoApp) -> bool:
    """Garante que há diagnóstico (necessário para adaptar ao hardware)."""
    if estado.diagnostico_pronto():
        return True
    interface.info("Para adaptar ao seu PC, preciso detectar os componentes (é rápido).")
    if not interface.confirmar("Detectar o hardware agora?", padrao=True):
        return False
    estado.perfil = diagnostico.coletar_perfil()
    return estado.diagnostico_pronto()


def _valores_por_exe(exe: str) -> list[tuple[str, str, str, int, object]]:
    """Tweaks específicos do executável do jogo (HKCU, não exigem admin)."""
    return [
        # Preferência de GPU: 2 = Alto desempenho (usa a GPU dedicada).
        ("HKCU", r"Software\Microsoft\DirectX\UserGpuPreferences",
         exe, winreg.REG_SZ, "GpuPreference=2;"),
        # Desativar otimizações de tela cheia para este executável.
        ("HKCU", r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
         exe, winreg.REG_SZ, "~ DISABLEDXMAXIMIZEDWINDOWEDMODE"),
    ]


def _escolher_jogo(estado: config.EstadoApp) -> tuple[str, str] | None:
    """Detecta jogos, deixa o usuário escolher e resolve o .exe.

    Returns:
        ``(nome_do_jogo, caminho_do_exe)`` ou ``None`` se cancelado.
    """
    with interface.spinner("Procurando jogos instalados (Steam/Epic)") as progresso:
        tarefa = progresso.add_task("Procurando jogos", total=None)
        lista = deteccao.detectar_jogos(resolver_exe=False)
        progresso.update(tarefa, completed=1)

    if lista:
        interface.texto(f"Encontrei {len(lista)} jogo(s) instalado(s).", config.COR_OK)
    else:
        interface.aviso(
            "Nenhum jogo do Steam/Epic foi detectado automaticamente.\n"
            "Você ainda pode informar o caminho do .exe do jogo manualmente."
        )

    opcoes: list[tuple[str, object]] = [
        (f"🎮  {j['nome']}   [{j['origem']}]", i) for i, j in enumerate(lista)
    ]
    opcoes.append(("✏  Informar o caminho do .exe manualmente", "manual"))
    opcoes.append(("↩  Voltar", None))

    escolha = interface.menu_selecao("Para qual jogo deseja otimizar?", opcoes)
    if escolha is None:
        return None

    if escolha == "manual":
        return _exe_manual()

    jogo = lista[escolha]
    nome = jogo["nome"]
    exe = jogo.get("exe")
    if not exe and jogo.get("pasta"):
        with interface.spinner(f"Localizando o executável de {nome}") as progresso:
            tarefa = progresso.add_task("Localizando", total=None)
            exe = deteccao.achar_exe(Path(jogo["pasta"]), jogo.get("installdir", ""))
            progresso.update(tarefa, completed=1)
    if not exe:
        interface.aviso("Não localizei o .exe automaticamente. Informe-o, por favor.")
        return _exe_manual(nome)
    return nome, exe


def _exe_manual(nome_sugerido: str = "") -> tuple[str, str] | None:
    """Pede o caminho do .exe manualmente e valida minimamente."""
    caminho = interface.pedir_texto("Cole o caminho completo do .exe do jogo:")
    exe = caminho.strip().strip('"')
    if not exe.lower().endswith(".exe"):
        interface.erro("Isso não parece um caminho de .exe. Operação cancelada.")
        return None
    nome = nome_sugerido or Path(exe).stem
    return nome, exe


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz a otimização por jogo."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return
    from modulos.tweaks import avancado  # motor seguro de aplicação (reuso)

    interface.cabecalho(
        "🎯 Otimização por jogo",
        "Detecta os jogos no seu PC e otimiza tudo para o que você escolher.",
    )
    if not _garantir_perfil(estado):
        interface.aviso("Sem o diagnóstico não dá para adaptar ao seu hardware.")
        return

    hw = hardware.perfil_otimizacao(estado.perfil)
    interface.info(f"Seu PC: [bold]{interface.escapar(hardware.resumo_curto(hw))}[/bold]")

    escolha = _escolher_jogo(estado)
    if escolha is None:
        interface.info("Operação cancelada.")
        return
    nome_jogo, exe = escolha
    classe = hardware.classificar_jogo(nome_jogo)

    # Monta o perfil: por-exe + pacote global + (latência, se competitivo).
    valores = _valores_por_exe(exe) + avancado.valores_pacote_jogos()
    if classe == "competitivo":
        valores += avancado.valores_nagle()

    # Dicas adaptadas ao hardware.
    dicas: list[str] = []
    if hw["hibrido"]:
        dicas.append("• Notebook híbrido: forço a GPU dedicada para este jogo.")
    elif hw["tem_dgpu"]:
        dicas.append("• GPU dedicada: defino preferência de alto desempenho para o jogo.")
    if hw["ram_baixa"]:
        dicas.append("• Pouca RAM: priorizo desempenho (considere também a aba Avançados).")
    if classe == "competitivo":
        dicas.append("• Jogo competitivo: incluo redução de latência de rede (Nagle).")
    if not hw["tem_ssd"]:
        dicas.append("• HDD detectado: os tempos de carregamento melhoram migrando o jogo p/ SSD.")
    bloco_dicas = ("\n".join(dicas) + "\n\n") if dicas else ""

    descricao = (
        f"Vou otimizar o PC para [bold]{interface.escapar(nome_jogo)}[/bold] "
        f"(perfil: {classe}).\n"
        f"Executável: {interface.escapar(exe)}\n\n"
        f"{bloco_dicas}"
        "Inclui, para este jogo: GPU em alto desempenho e desativar otimizações "
        "de tela cheia. E no sistema: Modo Jogo, Game DVR desligado, prioridade "
        "para jogos (MMCSS) e agendamento de GPU por hardware (HAGS)."
    )
    riscos = (
        "Risco MÉDIO. Tela cheia/HAGS podem variar conforme o jogo e o driver; "
        "TUDO é reversível em 'Desfazer última alteração'. Itens do sistema "
        "(HKLM) exigem administrador — sem ele, aplico ao menos os do jogo."
    )

    avancado._aplicar_pacote(
        estado,
        titulo=f"Otimizar para {nome_jogo}",
        descricao=descricao,
        riscos=riscos,
        valores=valores,
        exige_reinicio=True,
        modulo="jogos",
        cabecalho_titulo=f"🎯 Otimizar para {nome_jogo}",
    )
    interface.info(
        "Para desempenho máximo, ative também o plano 'Desempenho Máximo' na aba "
        "Avançados (ótimo em desktop; em notebook, cuidado com a bateria)."
    )
