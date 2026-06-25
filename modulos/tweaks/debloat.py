"""Tweak: Debloat do Windows — remover excessos com segurança.

Reúne três frentes, todas fiéis ao princípio do programa (descrição, aviso de
risco, confirmação, modo simulação e — quando possível — desfazer):

    1. Privacidade & Copilot (por registro, 100% reversível): desliga o Copilot,
       a telemetria, os widgets, a pesquisa web (Bing) no Iniciar, o ID de
       publicidade e as "sugestões"/anúncios. Usa o MESMO motor seguro dos
       ajustes avançados (backup .reg + ponto de restauração + desfazer preciso).

    2. Apps da Store (bloatware): remove apps pré-instalados que você escolher.
       A remoção é só para o seu usuário, então o "Desfazer" tenta reinstalá-los
       a partir dos arquivos que o Windows mantém (sem precisar baixar de novo).

    3. Desinstalar programas (Win32): lista os programas instalados e abre o
       desinstalador OFICIAL do que você escolher. (Esta ação NÃO é reversível
       pelo programa — é o instalador do fabricante que faz a remoção.)

⚠️  LINHA VERMELHA: este módulo NÃO desliga o Windows Defender / antivírus.
Isso exporia o usuário a malware e vai contra o princípio de segurança do
programa — é uma decisão de produto deliberada.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any, Optional

import config
from modulos import interface, seguranca
from modulos.tweaks import avancado

try:  # pragma: no cover
    import winreg  # type: ignore
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore

_DWORD = avancado._REG_DWORD


# ===========================================================================
# 1) Privacidade & Copilot (por registro — reversível)
# ===========================================================================
# Cada categoria: rótulo -> lista de valores (raiz, subchave, nome, tipo, dado).
_CATEGORIAS_PRIVACIDADE: dict[str, tuple[str, list[tuple[str, str, str, int, Any]]]] = {
    "copilot": ("🤖  Desativar o Copilot do Windows", [
        ("HKCU", r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", _DWORD, 1),
        ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", _DWORD, 1),
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowCopilotButton", _DWORD, 0),
    ]),
    "telemetria": ("📡  Reduzir a telemetria / coleta de dados", [
        ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", _DWORD, 0),
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Privacy",
         "TailoredExperiencesWithDiagnosticDataEnabled", _DWORD, 0),
    ]),
    "widgets": ("🧩  Desativar Widgets / Notícias e Interesses", [
        ("HKLM", r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", _DWORD, 0),
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarDa", _DWORD, 0),
    ]),
    "bing": ("🔎  Tirar a pesquisa web (Bing) do menu Iniciar", [
        ("HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", _DWORD, 1),
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", _DWORD, 0),
    ]),
    "publicidade": ("🪧  Desligar o ID de publicidade", [
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", _DWORD, 0),
    ]),
    "sugestoes": ("✨  Desativar sugestões e anúncios do sistema", [
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
         "SystemPaneSuggestionsEnabled", _DWORD, 0),
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
         "SubscribedContent-338388Enabled", _DWORD, 0),
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
         "SilentInstalledAppsEnabled", _DWORD, 0),
    ]),
}


def _acao_privacidade(estado: config.EstadoApp) -> None:
    """Deixa o usuário escolher categorias de privacidade e aplica num pacote só."""
    interface.cabecalho("🧽 Debloat · Privacidade & Copilot",
                        "Escolha o que desativar — tudo reversível em 'Desfazer'.")
    opcoes = [(rotulo, chave) for chave, (rotulo, _v) in _CATEGORIAS_PRIVACIDADE.items()]
    escolhidas = interface.menu_multiplo(
        "Marque o que deseja desativar (Espaço marca, Enter confirma):", opcoes
    )
    if not escolhidas:
        interface.info("Nada selecionado. Nenhuma alteração feita.")
        return

    valores: list[tuple[str, str, str, int, Any]] = []
    nomes: list[str] = []
    for chave in escolhidas:
        rotulo, vals = _CATEGORIAS_PRIVACIDADE[chave]
        valores.extend(vals)
        nomes.append(rotulo.split("  ", 1)[-1].strip())

    avancado._aplicar_pacote(
        estado,
        titulo="Debloat de privacidade",
        descricao="Vou desativar: " + "; ".join(nomes) + ".",
        riscos="Risco BAIXO e 100% reversível em 'Desfazer última alteração'. "
        "Itens do sistema (HKLM) podem exigir administrador; sem ele, aplico os do "
        "usuário. Algumas mudanças (Iniciar/Widgets) pedem para reiniciar o Explorer "
        "ou fazer login de novo para aparecerem.",
        valores=valores,
        modulo="debloat",
        cabecalho_titulo="🧽 Debloat · Privacidade & Copilot",
    )


# ===========================================================================
# 2) Apps da Store (bloatware) — remoção com reinstalação no "Desfazer"
# ===========================================================================
# (rótulo amigável, padrão do nome do pacote para o Get-AppxPackage)
_APPS_BLOATWARE: list[tuple[str, str]] = [
    ("Solitaire Collection", "*MicrosoftSolitaireCollection*"),
    ("Notícias (Bing News)", "*BingNews*"),
    ("Clima (Bing Weather)", "*BingWeather*"),
    ("Clipchamp (editor de vídeo)", "*Clipchamp*"),
    ("Mapas", "*WindowsMaps*"),
    ("Pessoas (People)", "*People*"),
    ("Obter Ajuda", "*GetHelp*"),
    ("Dicas / Começar (Get Started)", "*Getstarted*"),
    ("Hub de Comentários (Feedback)", "*WindowsFeedbackHub*"),
    ("Skype", "*SkypeApp*"),
    ("Mixed Reality Portal", "*MixedReality.Portal*"),
    ("Cortana", "*549981C3F5F10*"),
    ("Microsoft Teams (Chat pessoal)", "*MicrosoftTeams*"),
    ("Your Phone / Vincular ao Celular", "*YourPhone*"),
    ("Xbox (apps complementares)", "*Xbox.TCUI* *XboxGamingOverlay* *XboxGameOverlay* *XboxIdentityProvider* *XboxSpeechToTextOverlay*"),
]


def _ps_reinstalar(padroes: list[str]) -> str:
    """Monta o comando PowerShell que reinstala (re-registra) apps removidos."""
    partes = []
    for p in padroes:
        for token in p.split():
            partes.append(
                f"Get-AppxPackage -AllUsers {token} | ForEach-Object "
                f"{{ Add-AppxPackage -DisableDevelopmentMode -Register "
                f'"$($_.InstallLocation)\\AppXManifest.xml" -ErrorAction SilentlyContinue }}'
            )
    return "; ".join(partes)


def _acao_remover_apps(estado: config.EstadoApp) -> None:
    """Remove apps da Store escolhidos (com reinstalação registrada no desfazer)."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    interface.cabecalho("🧽 Debloat · Apps da Store",
                        "Remova apps pré-instalados que você não usa.")
    interface.info(
        "A remoção é feita só para o SEU usuário. O 'Desfazer' tenta reinstalar "
        "a partir dos arquivos que o Windows mantém — sem baixar de novo. Se algo "
        "não voltar, dá para reinstalar pela Microsoft Store."
    )
    escolhidos = interface.menu_multiplo(
        "Marque os apps que deseja remover (Espaço marca, Enter confirma):",
        _APPS_BLOATWARE,
    )
    if not escolhidos:
        interface.info("Nada selecionado. Nenhuma alteração feita.")
        return

    if estado.simulacao:
        interface.info(
            f"MODO SIMULAÇÃO: {len(escolhidos)} app(s) seriam removidos. Nada foi alterado."
        )
        return
    if not interface.confirmar(f"Remover {len(escolhidos)} app(s) agora?", padrao=False):
        interface.info("Operação cancelada. Nada foi alterado.")
        return
    if not seguranca.garantir_ponto_restauracao(estado):
        interface.info("Operação cancelada (sem ponto de restauração).")
        return

    removidos: list[str] = []
    with interface.barra_progresso() as progresso:
        tarefa = progresso.add_task("Removendo apps", total=len(escolhidos))
        for padrao in escolhidos:
            for token in padrao.split():
                seguranca.executar_comando(
                    f"Get-AppxPackage {token} | Remove-AppxPackage -ErrorAction SilentlyContinue",
                    powershell=True,
                    timeout=120,
                )
            removidos.append(padrao)
            progresso.advance(tarefa)

    rotulos = [r for r, p in _APPS_BLOATWARE if p in removidos]
    seguranca.registrar_desfazer(
        "debloat",
        f"Reinstalar {len(removidos)} app(s) da Store: " + ", ".join(rotulos[:4])
        + ("..." if len(rotulos) > 4 else ""),
        "powershell",
        {"comando": _ps_reinstalar(removidos),
         "ok_msg": "Tentativa de reinstalação concluída — confira na Store o que voltou."},
    )
    seguranca.registrar_acao("debloat", "Remoção de apps da Store", True, f"{len(removidos)} app(s)")
    interface.sucesso(
        f"{len(removidos)} app(s) removido(s). Use 'Desfazer última alteração' para "
        "reinstalar, se mudar de ideia."
    )


# ===========================================================================
# 3) Desinstalar programas (Win32) — abre o desinstalador oficial
# ===========================================================================
def _ler_valor(chave: Any, nome: str) -> Any:
    try:
        valor, _tipo = winreg.QueryValueEx(chave, nome)
        return valor
    except (FileNotFoundError, OSError):
        return None


def _listar_programas() -> list[tuple[str, str]]:
    """Lista (nome, comando_de_desinstalação) dos programas instalados (Win32)."""
    if winreg is None:
        return []
    locais = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    vistos: set[str] = set()
    saida: list[tuple[str, str]] = []
    for hive, sub in locais:
        try:
            raiz = winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        except OSError:
            continue
        with raiz:
            i = 0
            while True:
                try:
                    nome_sub = winreg.EnumKey(raiz, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(raiz, nome_sub) as sk:
                        nome = _ler_valor(sk, "DisplayName")
                        unins = _ler_valor(sk, "UninstallString")
                        if not nome or not unins:
                            continue
                        if _ler_valor(sk, "SystemComponent") == 1:
                            continue
                        if _ler_valor(sk, "ParentKeyName"):
                            continue  # é uma atualização/componente, não o programa
                        chave_id = str(nome).strip().lower()
                        if chave_id in vistos:
                            continue
                        vistos.add(chave_id)
                        saida.append((str(nome).strip(), str(unins)))
                except OSError:
                    continue
    saida.sort(key=lambda t: t[0].lower())
    return saida


def _acao_desinstalar(estado: config.EstadoApp) -> None:
    """Lista os programas instalados e abre o desinstalador oficial do escolhido."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    interface.cabecalho("🧽 Debloat · Desinstalar programas",
                        "Abre o desinstalador OFICIAL do programa que você escolher.")
    with interface.spinner("Lendo os programas instalados") as progresso:
        tarefa = progresso.add_task("Lendo", total=None)
        programas = _listar_programas()
        progresso.update(tarefa, completed=1)

    if not programas:
        interface.aviso("Não encontrei programas para listar.")
        return

    interface.aviso(
        "⚠ Esta ação NÃO é reversível pelo Otimizador PC: quem remove é o "
        "desinstalador do próprio fabricante. Para reinstalar, baixe o programa "
        "de novo. (Para apps da Store, use a opção 'Apps da Store'.)"
    )
    opcoes = [(nome, comando) for nome, comando in programas]
    opcoes.append(("↩  Voltar", "voltar"))
    escolha = interface.menu_selecao(
        f"Qual programa deseja desinstalar? ({len(programas)} encontrados)", opcoes
    )
    if escolha in (None, "voltar"):
        return

    nome = next((n for n, c in programas if c == escolha), "programa")
    if estado.simulacao:
        interface.info(f"MODO SIMULAÇÃO: eu abriria o desinstalador de '{nome}'. Nada foi alterado.")
        return
    if not interface.confirmar(f"Abrir o desinstalador de '{nome}' agora?", padrao=False):
        interface.info("Operação cancelada.")
        return

    try:
        # Lança o desinstalador oficial em processo próprio (não trava a janela).
        subprocess.Popen(str(escolha), shell=True)
        seguranca.registrar_acao("debloat", f"Desinstalador aberto: {nome}", True)
        interface.sucesso(
            f"Abri o desinstalador de '{nome}'. Siga as instruções na janela dele."
        )
    except OSError as exc:
        seguranca.registrar_acao("debloat", f"Desinstalador: {nome}", False, str(exc))
        interface.erro(f"Não consegui abrir o desinstalador: {exc}")


# ===========================================================================
# Menu
# ===========================================================================
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de debloat (privacidade, apps da Store e desinstalação)."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    acoes = {
        "privacidade": _acao_privacidade,
        "apps": _acao_remover_apps,
        "desinstalar": _acao_desinstalar,
    }
    while True:
        interface.cabecalho(
            "🧽 Debloat do Windows",
            "Tire os excessos do Windows — com a mesma segurança de sempre.",
        )
        interface.info(
            "🛡 Por segurança, este módulo NÃO mexe no Windows Defender/antivírus.\n"
            "Privacidade é reversível em 'Desfazer'. A desinstalação de programas é "
            "feita pelo instalador do fabricante (não reversível pelo programa)."
        )
        if not estado.eh_admin:
            interface.info(
                "Você não está como administrador: ajustes de sistema (HKLM) e a "
                "remoção de alguns apps podem falhar. Reabra elevado para o efeito total."
            )
        opcoes = [
            ("🔒  Privacidade & Copilot (telemetria, widgets, Bing...)", "privacidade"),
            ("📦  Remover apps da Store (bloatware)", "apps"),
            ("🗑  Desinstalar programas instalados", "desinstalar"),
            ("↩  Voltar", "voltar"),
        ]
        escolha = interface.menu_selecao("O que deseja fazer?", opcoes)
        if escolha in (None, "voltar"):
            return
        funcao = acoes.get(escolha)
        if funcao:
            funcao(estado)
            interface.pausar()
