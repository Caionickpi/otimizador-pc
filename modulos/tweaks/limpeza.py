"""Tweak: limpeza de arquivos temporários.

Remove apenas locais de cache/temporários conhecidos e seguros:
%TEMP%, C:\\Windows\\Temp, cache do Windows Update (SoftwareDistribution\\Download),
Lixeira, cache de miniaturas e logs antigos do Windows.

NUNCA toca em documentos, fotos, downloads ou área de trabalho do usuário.
Calcula e mostra o espaço a ser liberado ANTES de executar e pede confirmação.
São arquivos descartáveis por natureza, então não há backup (o Windows os
recria conforme necessário).
"""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Any, Optional

import config
from modulos import interface, seguranca


# ---------------------------------------------------------------------------
# Lixeira (via API do Shell)
# ---------------------------------------------------------------------------
class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("i64Size", ctypes.c_int64),
        ("i64NumItems", ctypes.c_int64),
    ]


def _tamanho_lixeira() -> int:
    """Retorna o tamanho total da Lixeira em bytes (0 se indisponível)."""
    if not sys.platform.startswith("win"):
        return 0
    try:
        info = _SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
        resultado = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))  # type: ignore[attr-defined]
        return int(info.i64Size) if resultado == 0 else 0
    except Exception:  # noqa: BLE001
        return 0


def _esvaziar_lixeira() -> bool:
    """Esvazia a Lixeira silenciosamente. Retorna ``True`` em sucesso."""
    if not sys.platform.startswith("win"):
        return False
    try:
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI = 0x00000002
        SHERB_NOSOUND = 0x00000004
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        resultado = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)  # type: ignore[attr-defined]
        # S_OK (0) = esvaziou; alguns sistemas retornam erro se já estava vazia.
        return resultado == 0
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar(f"Falha ao esvaziar a Lixeira: {exc}", logging.WARNING)
        return False


# ---------------------------------------------------------------------------
# Cálculo e remoção de pastas de cache
# ---------------------------------------------------------------------------
def _tamanho_pasta(caminho: Path) -> int:
    """Calcula o tamanho total (bytes) do conteúdo de uma pasta, ignorando erros."""
    total = 0
    if not caminho.exists():
        return 0
    for raiz, _dirs, arquivos in os.walk(caminho):
        for nome in arquivos:
            try:
                total += (Path(raiz) / nome).stat().st_size
            except OSError:
                continue
    return total


def _locais_limpeza() -> list[dict[str, Any]]:
    """Monta a lista de locais de limpeza conhecidos e existentes."""
    locais: list[dict[str, Any]] = []

    temp_usuario = os.environ.get("TEMP") or os.environ.get("TMP")
    windir = os.environ.get("WINDIR", r"C:\Windows")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    candidatos: list[tuple[str, Optional[str], str]] = [
        ("Temporários do usuário (%TEMP%)", temp_usuario, "pasta"),
        ("Temporários do Windows", f"{windir}\\Temp", "pasta"),
        ("Cache do Windows Update", f"{windir}\\SoftwareDistribution\\Download", "pasta"),
        ("Cache de miniaturas", f"{localappdata}\\Microsoft\\Windows\\Explorer" if localappdata else None, "miniaturas"),
        ("Relatórios de erro (WER)", f"{localappdata}\\Microsoft\\Windows\\WER" if localappdata else None, "pasta"),
    ]

    for nome, caminho_str, tipo in candidatos:
        if not caminho_str:
            continue
        caminho = Path(caminho_str)
        if caminho.exists():
            if tipo == "miniaturas":
                tamanho = sum(
                    arq.stat().st_size
                    for arq in caminho.glob("thumbcache_*.db")
                    if arq.is_file()
                ) + sum(
                    arq.stat().st_size
                    for arq in caminho.glob("iconcache_*.db")
                    if arq.is_file()
                )
            else:
                tamanho = _tamanho_pasta(caminho)
            locais.append({"nome": nome, "caminho": caminho, "tipo": tipo, "tamanho": tamanho})

    # Lixeira (tratada via API, não por caminho).
    locais.append({"nome": "Lixeira", "caminho": None, "tipo": "lixeira", "tamanho": _tamanho_lixeira()})
    return locais


def _limpar_conteudo_pasta(caminho: Path, apenas_padrao: Optional[list[str]] = None) -> int:
    """Apaga o conteúdo de uma pasta (mantendo a própria pasta).

    Args:
        caminho: pasta cujo conteúdo será removido.
        apenas_padrao: se informado, apaga só arquivos que casem com estes
            padrões glob (ex.: ['thumbcache_*.db']).

    Returns:
        Bytes efetivamente liberados (aproximado).
    """
    if not caminho.exists():
        return 0

    tamanho_antes = _tamanho_pasta(caminho)

    if apenas_padrao:
        for padrao in apenas_padrao:
            for arquivo in caminho.glob(padrao):
                try:
                    if arquivo.is_file():
                        arquivo.unlink()
                except OSError:
                    continue  # arquivo em uso: ignora
        # Recalcula sobre os padrões — aproxima o que sobrou.
        restante = 0
        for padrao in apenas_padrao:
            restante += sum(a.stat().st_size for a in caminho.glob(padrao) if a.is_file())
        liberado = tamanho_antes - restante
        return max(liberado, 0)

    for item in caminho.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
        except OSError:
            # Arquivo/pasta em uso (ex.: travado pelo Windows). Ignora.
            continue

    tamanho_depois = _tamanho_pasta(caminho)
    return max(tamanho_antes - tamanho_depois, 0)


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de limpeza de arquivos temporários."""
    interface.cabecalho(
        "Limpeza de arquivos temporários",
        "Remove apenas cache/temporários conhecidos. Não toca em arquivos pessoais.",
    )

    interface.texto("Calculando o espaço que pode ser liberado...", "dim")
    locais = _locais_limpeza()
    total = sum(item["tamanho"] for item in locais)

    tabela = interface.nova_tabela("Locais que serão limpos", ["Local", "Espaço a liberar"])
    for item in locais:
        tabela.add_row(item["nome"], interface.formatar_bytes(item["tamanho"]))
    tabela.add_row("[bold]TOTAL[/bold]", f"[bold green]{interface.formatar_bytes(total)}[/bold green]")
    interface.imprimir_tabela(tabela)

    if total == 0:
        interface.info("Nada para limpar — já está tudo enxuto por aqui!")
        return

    if estado.simulacao:
        interface.info(
            "MODO SIMULAÇÃO: nada foi apagado.\n"
            f"Seriam liberados aproximadamente {interface.formatar_bytes(total)}."
        )
        return

    interface.aviso(
        "Estes são arquivos temporários e de cache, seguros para remover. "
        "Como são descartáveis, não há backup — o Windows os recria quando "
        "precisar. Programas abertos podem manter alguns arquivos travados; "
        "esses serão ignorados."
    )
    if not interface.confirmar(f"Liberar ~{interface.formatar_bytes(total)} agora?", padrao=False):
        interface.info("Limpeza cancelada. Nada foi alterado.")
        return

    # Ponto de restauração por consistência da sessão (não recupera temporários,
    # mas mantém o padrão de segurança caso o usuário faça outros ajustes depois).
    seguranca.garantir_ponto_restauracao(estado)

    liberado_total = 0
    with interface.barra_progresso() as progresso:
        tarefa = progresso.add_task("Limpando", total=len(locais))
        for item in locais:
            progresso.update(tarefa, description=f"Limpando: {item['nome']}")
            liberado_total += _executar_limpeza_item(item)
            progresso.advance(tarefa)

    seguranca.registrar_acao(
        "limpeza",
        "Limpeza de temporários concluída",
        True,
        f"liberado ~{interface.formatar_bytes(liberado_total)}",
    )
    interface.sucesso(
        f"Limpeza concluída! Espaço liberado: ~{interface.formatar_bytes(liberado_total)}."
    )


def _executar_limpeza_item(item: dict[str, Any]) -> int:
    """Executa a limpeza de um item da lista e retorna os bytes liberados."""
    tipo = item["tipo"]
    try:
        if tipo == "lixeira":
            antes = item.get("tamanho", 0)
            return antes if _esvaziar_lixeira() else 0
        if tipo == "miniaturas":
            return _limpar_conteudo_pasta(item["caminho"], ["thumbcache_*.db", "iconcache_*.db"])
        return _limpar_conteudo_pasta(item["caminho"])
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar_acao("limpeza", f"Falha em {item['nome']}", False, str(exc))
        return 0
