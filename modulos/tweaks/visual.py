"""Tweak: efeitos visuais / desempenho.

Ajusta o Windows para priorizar desempenho (desliga animações, sombras e
transparências pesadas). Antes de alterar, exporta (.reg) todas as chaves que
serão tocadas, e registra um único 'desfazer' que restaura tudo de uma vez.

As mudanças costumam ter efeito completo após sair e entrar na conta de
usuário (ou reiniciar).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import config
from modulos import interface, seguranca

try:  # pragma: no cover
    import winreg  # type: ignore
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore


# Chaves (em HKCU) que serão exportadas para backup antes de qualquer mudança.
_CHAVES_BACKUP = [
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
    r"Control Panel\Desktop",
    r"Control Panel\Desktop\WindowMetrics",
]

# Valores aplicados para priorizar desempenho — montados em _montar_valores()
# (depende de winreg, que pode não existir fora do Windows).
def _montar_valores() -> list[tuple[str, str, int, Any]]:
    """Monta a lista de valores a aplicar (lazy, pois depende de winreg)."""
    if winreg is None:
        return []
    return [
        # 2 = "Ajustar para obter melhor desempenho".
        (r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
         "VisualFXSetting", winreg.REG_DWORD, 2),
        # Animações da barra de tarefas e janelas.
        (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
         "TaskbarAnimations", winreg.REG_DWORD, 0),
        (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
         "ListviewAlphaSelect", winreg.REG_DWORD, 0),
        (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
         "ListviewShadow", winreg.REG_DWORD, 0),
        # Mostrar conteúdo da janela ao arrastar (0 = só a moldura, mais leve).
        (r"Control Panel\Desktop", "DragFullWindows", winreg.REG_SZ, "0"),
        # Animação de minimizar/maximizar.
        (r"Control Panel\Desktop\WindowMetrics", "MinAnimate", winreg.REG_SZ, "0"),
    ]


def _definir_valor(subchave: str, nome: str, tipo: int, dado: Any) -> bool:
    """Define um valor no registro (HKCU), criando a chave se necessário."""
    if winreg is None:
        return False
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, subchave, 0, winreg.KEY_SET_VALUE) as chave:
            winreg.SetValueEx(chave, nome, 0, tipo, dado)
        return True
    except OSError as exc:
        seguranca.registrar(f"Falha ao definir {subchave}\\{nome}: {exc}", logging.WARNING)
        return False


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de ajuste de efeitos visuais."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    interface.cabecalho(
        "Efeitos visuais / desempenho",
        "Desliga enfeites para deixar a interface mais leve e responsiva.",
    )
    interface.info(
        "Serão desativados: animações de janelas e barra de tarefas, sombras de "
        "ícones e o conteúdo completo das janelas ao arrastar.\n"
        "Tudo é reversível (fazemos backup das chaves antes de mexer)."
    )

    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: os efeitos visuais seriam reduzidos. Nada foi alterado.")
        return

    if not interface.confirmar("Aplicar os ajustes de efeitos visuais agora?", padrao=False):
        interface.info("Operação cancelada.")
        return

    seguranca.garantir_ponto_restauracao(estado)

    # 1) Backup de todas as chaves antes de mexer.
    arquivos_backup: list[str] = []
    for subchave in _CHAVES_BACKUP:
        destino = seguranca.backup_chave_registro(f"HKCU\\{subchave}", "efeitos_visuais")
        if destino:
            arquivos_backup.append(str(destino))

    # 2) Aplica os valores.
    aplicados = 0
    for subchave, nome, tipo, dado in _montar_valores():
        if _definir_valor(subchave, nome, tipo, dado):
            aplicados += 1

    if aplicados == 0:
        interface.erro("Nenhum ajuste pôde ser aplicado (verifique as permissões).")
        return

    # 3) Registra um único 'desfazer' que restaura todos os backups.
    if arquivos_backup:
        seguranca.registrar_desfazer(
            "visual",
            "Restaurar efeitos visuais anteriores",
            "reg_import",
            {"arquivos": arquivos_backup},
        )
    seguranca.registrar_acao("visual", "Efeitos visuais reduzidos", True, f"{aplicados} valores")
    interface.sucesso(
        f"Efeitos visuais ajustados para desempenho ({aplicados} ajustes aplicados).\n"
        "Saia e entre novamente na sua conta (ou reinicie) para o efeito completo."
    )
