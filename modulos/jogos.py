"""Detecção de jogos instalados (Steam e Epic) — somente leitura e rápida.

Lê os metadados dos próprios launchers (sem varrer o disco inteiro):
    * Steam: ``libraryfolders.vdf`` -> bibliotecas -> ``appmanifest_*.acf``.
    * Epic:  manifestos ``*.item`` (JSON) em ProgramData.

A descoberta do ``.exe`` de cada jogo é opcional e feita sob demanda (só para o
jogo escolhido), mantendo a listagem instantânea. Tudo é tolerante a falhas:
qualquer erro de leitura apenas omite aquele jogo, sem quebrar o programa.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

from modulos import seguranca

try:  # pragma: no cover
    import winreg  # type: ignore
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore

# .exe que normalmente NÃO são o jogo (ferramentas/instaladores/anticheat).
_EXE_IGNORAR = (
    "unins", "setup", "vcredist", "dxsetup", "crashreport", "crashhandler",
    "redist", "dotnet", "uninstall", "easyanticheat_setup", "btvise",
    "touchup", "installscript", "vc_redist", "directx",
)


# ---------------------------------------------------------------------------
# Parsers puros (testáveis sem Windows)
# ---------------------------------------------------------------------------
def _paths_steam_vdf(conteudo: str) -> list[str]:
    """Extrai os caminhos das bibliotecas de um ``libraryfolders.vdf``."""
    return [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', conteudo)]


def _parse_acf(conteudo: str) -> dict[str, str]:
    """Extrai ``name``/``installdir``/``appid`` de um ``appmanifest_*.acf``."""
    dados: dict[str, str] = {}
    for chave in ("name", "installdir", "appid"):
        m = re.search(rf'"{chave}"\s+"([^"]*)"', conteudo)
        if m:
            dados[chave] = m.group(1)
    return dados


def _parse_epic_item(conteudo: str) -> Optional[dict[str, str]]:
    """Extrai nome/local/exe de um manifesto ``.item`` (JSON) da Epic."""
    try:
        d = json.loads(conteudo)
    except (ValueError, TypeError):
        return None
    nome = d.get("DisplayName")
    local = d.get("InstallLocation")
    if not (nome and local):
        return None
    return {"nome": nome, "local": local, "exe_rel": d.get("LaunchExecutable") or ""}


# ---------------------------------------------------------------------------
# Localização dos launchers / executáveis
# ---------------------------------------------------------------------------
def _steam_path() -> Optional[Path]:
    """Descobre a pasta de instalação do Steam pelo registro."""
    if winreg is None:
        return None
    for hive, sub in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
    ):
        try:
            with winreg.OpenKey(hive, sub) as chave:
                for nome_val in ("SteamPath", "InstallPath"):
                    try:
                        valor, _ = winreg.QueryValueEx(chave, nome_val)
                    except FileNotFoundError:
                        continue
                    if valor:
                        caminho = Path(str(valor))
                        if caminho.exists():
                            return caminho
        except OSError:
            continue
    return None


def achar_exe(pasta: Path, dica: str = "") -> Optional[str]:
    """Heurística: acha o ``.exe`` mais provável de ser o jogo dentro da pasta.

    Procura só até 2 níveis de profundidade e escolhe o maior ``.exe`` que não
    pareça ferramenta/instalador (com um bônus se o nome lembrar o do jogo).
    """
    try:
        if not pasta.exists():
            return None
        candidatos: list[tuple[int, str]] = []
        for raiz, _dirs, arquivos in os.walk(pasta):
            try:
                profundidade = len(Path(raiz).relative_to(pasta).parts)
            except ValueError:
                profundidade = 0
            if profundidade > 2:
                continue
            for nome in arquivos:
                baixo = nome.lower()
                if not baixo.endswith(".exe") or any(t in baixo for t in _EXE_IGNORAR):
                    continue
                try:
                    tam = (Path(raiz) / nome).stat().st_size
                except OSError:
                    tam = 0
                bonus = 8 * 1024 * 1024 if dica and dica.lower()[:4] in baixo else 0
                candidatos.append((tam + bonus, str(Path(raiz) / nome)))
        if not candidatos:
            return None
        candidatos.sort(reverse=True)
        return candidatos[0][1]
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Coletores por launcher
# ---------------------------------------------------------------------------
def _jogos_steam() -> list[dict[str, Any]]:
    jogos: list[dict[str, Any]] = []
    base = _steam_path()
    if base is None:
        return jogos
    bibliotecas = [base]
    vdf = base / "steamapps" / "libraryfolders.vdf"
    try:
        if vdf.exists():
            for p in _paths_steam_vdf(vdf.read_text(encoding="utf-8", errors="ignore")):
                bibliotecas.append(Path(p))
    except OSError:
        pass

    vistos: set[str] = set()
    for lib in bibliotecas:
        steamapps = lib / "steamapps"
        try:
            acfs = list(steamapps.glob("appmanifest_*.acf"))
        except OSError:
            continue
        for acf in acfs:
            try:
                info = _parse_acf(acf.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            nome, instal = info.get("name"), info.get("installdir")
            if not nome or not instal or nome in vistos:
                continue
            vistos.add(nome)
            jogos.append({
                "nome": nome, "origem": "Steam", "exe": None,
                "pasta": str(steamapps / "common" / instal), "installdir": instal,
            })
    return jogos


def _jogos_epic() -> list[dict[str, Any]]:
    jogos: list[dict[str, Any]] = []
    programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    manifestos = Path(programdata) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    try:
        items = list(manifestos.glob("*.item"))
    except OSError:
        return jogos
    for item in items:
        try:
            d = _parse_epic_item(item.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if not d:
            continue
        exe = str(Path(d["local"]) / d["exe_rel"]) if d["exe_rel"] else None
        jogos.append({
            "nome": d["nome"], "origem": "Epic", "exe": exe,
            "pasta": d["local"], "installdir": "",
        })
    return jogos


def detectar_jogos(resolver_exe: bool = False) -> list[dict[str, Any]]:
    """Detecta jogos instalados (Steam + Epic). Rápido e tolerante a falhas.

    Args:
        resolver_exe: se ``True``, já tenta localizar o ``.exe`` de cada jogo
            (mais lento). O padrão é ``False`` — resolva o ``.exe`` apenas do
            jogo escolhido com :func:`achar_exe`, mantendo a lista instantânea.
    """
    if not sys.platform.startswith("win"):
        return []
    jogos: list[dict[str, Any]] = []
    for coletor in (_jogos_steam, _jogos_epic):
        try:
            jogos.extend(coletor())
        except Exception as exc:  # noqa: BLE001
            seguranca.registrar(f"[jogos] coletor falhou: {exc}", logging.WARNING)
    if resolver_exe:
        for j in jogos:
            if not j.get("exe") and j.get("pasta"):
                j["exe"] = achar_exe(Path(j["pasta"]), j.get("installdir", ""))
    jogos.sort(key=lambda j: j["nome"].lower())
    return jogos
