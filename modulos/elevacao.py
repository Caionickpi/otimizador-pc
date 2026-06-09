"""Verificação e elevação de privilégios de administrador.

As funções de diagnóstico (somente leitura) funcionam sem administrador.
Já os ajustes que alteram o sistema exigem privilégios elevados. Este módulo
detecta o nível atual e, quando necessário, reabre o programa elevado usando
``ShellExecuteW`` com o verbo ``runas`` (o que dispara o prompt do UAC).

Todo o código é defensivo: em sistemas que não sejam Windows, as funções
retornam valores seguros em vez de lançar exceções.
"""

from __future__ import annotations

import ctypes
import sys
from typing import NoReturn


def eh_administrador() -> bool:
    """Retorna ``True`` se o processo atual está rodando como administrador.

    Em sistemas não-Windows, retorna ``False`` (não há o conceito equivalente
    aqui, e o programa é destinado ao Windows).
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        # IsUserAnAdmin retorna BOOL (não-zero quando elevado).
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:
        # Se a API não estiver disponível por algum motivo, assume não-admin
        # (caminho mais seguro: o programa apenas oferecerá leitura).
        return False


def reabrir_como_administrador() -> bool:
    """Tenta reabrir o programa com privilégios de administrador.

    Dispara o prompt do UAC. Retorna ``True`` se o pedido de elevação foi
    aceito e um novo processo elevado foi iniciado (caso em que o processo
    atual deve encerrar). Retorna ``False`` se não foi possível ou se o
    usuário recusou o UAC.
    """
    if not sys.platform.startswith("win"):
        return False

    try:
        # Reúne os argumentos originais para preservar o contexto ao reabrir.
        parametros = " ".join(f'"{arg}"' for arg in sys.argv)

        # ShellExecuteW(hwnd, verbo, arquivo, parametros, dir, mostrar)
        # Retorno > 32 indica sucesso. nShowCmd=1 => SW_SHOWNORMAL.
        resultado = ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
            None,
            "runas",
            sys.executable,
            parametros,
            None,
            1,
        )
        return int(resultado) > 32
    except Exception:
        return False


def elevar_e_encerrar() -> NoReturn | None:
    """Reabre elevado e encerra o processo atual em caso de sucesso.

    Se a elevação falhar ou for recusada, retorna ``None`` para que o
    chamador possa decidir continuar em modo somente-leitura.
    """
    if reabrir_como_administrador():
        # Um novo processo elevado assumiu; encerra o atual silenciosamente.
        sys.exit(0)
    return None
