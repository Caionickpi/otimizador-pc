"""Premium: medição "antes e depois".

Captura métricas rápidas e reversíveis (sem alterar nada) num instantâneo,
guarda em disco e, depois que você otimiza, compara para mostrar o GANHO real.
Métricas escolhidas por serem leves e sensíveis a otimização: processos ativos,
uso de RAM, RAM disponível, itens de inicialização e espaço livre em disco.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

import psutil

import config
from modulos import interface, seguranca

_ARQUIVO = config.PASTA_BACKUPS / "snapshot_desempenho.json"

# Para cada métrica: rótulo, unidade e se "menor é melhor".
_METRICAS = {
    "processos": ("Processos ativos", "", True),
    "ram_uso_pct": ("Uso de RAM", "%", True),
    "ram_disponivel": ("RAM disponível", "bytes", False),
    "inicializacao": ("Programas na inicialização", "", True),
    "disco_livre": ("Espaço livre (disco do sistema)", "bytes", False),
}


def _drive_sistema() -> str:
    """Letra do disco do sistema (ex.: 'C:\\'), com reserva segura."""
    windir = os.environ.get("WINDIR", r"C:\Windows")
    return windir[:2] + "\\" if len(windir) >= 2 else "C:\\"


def capturar() -> dict[str, Any]:
    """Coleta um instantâneo das métricas de desempenho (rápido, só leitura)."""
    dados: dict[str, Any] = {"em": datetime.now().isoformat(timespec="seconds")}
    try:
        dados["processos"] = len(psutil.pids())
    except Exception:  # noqa: BLE001
        dados["processos"] = 0
    try:
        vm = psutil.virtual_memory()
        dados["ram_uso_pct"] = round(vm.percent, 1)
        dados["ram_disponivel"] = int(vm.available)
    except Exception:  # noqa: BLE001
        dados["ram_uso_pct"] = 0.0
        dados["ram_disponivel"] = 0
    try:
        from modulos.tweaks import inicializacao
        dados["inicializacao"] = len(inicializacao._listar_ativos())
    except Exception:  # noqa: BLE001
        dados["inicializacao"] = 0
    try:
        dados["disco_livre"] = int(psutil.disk_usage(_drive_sistema()).free)
    except Exception:  # noqa: BLE001
        dados["disco_livre"] = 0
    return dados


def _salvar(snap: dict[str, Any]) -> bool:
    config.garantir_pastas()
    try:
        with _ARQUIVO.open("w", encoding="utf-8") as fp:
            json.dump(snap, fp, ensure_ascii=False, indent=2)
        return True
    except OSError as exc:
        seguranca.registrar(f"[desempenho] falha ao salvar snapshot: {exc}", logging.WARNING)
        return False


def _carregar() -> Optional[dict[str, Any]]:
    if not _ARQUIVO.exists():
        return None
    try:
        with _ARQUIVO.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, json.JSONDecodeError):
        return None


def _formatar(chave: str, valor: Any) -> str:
    """Formata um valor de métrica conforme a unidade."""
    _rotulo, unidade, _menor = _METRICAS[chave]
    if unidade == "bytes":
        return interface.formatar_bytes(valor)
    if unidade == "%":
        return f"{valor:.0f}%"
    return str(valor)


def comparar(antes: dict[str, Any], depois: dict[str, Any]) -> list[dict[str, Any]]:
    """Compara dois instantâneos e classifica cada métrica (melhorou/piorou)."""
    linhas: list[dict[str, Any]] = []
    for chave, (rotulo, _un, menor_melhor) in _METRICAS.items():
        a, d = antes.get(chave, 0), depois.get(chave, 0)
        delta = d - a
        if delta == 0:
            tendencia = "igual"
        else:
            melhorou = (delta < 0) if menor_melhor else (delta > 0)
            tendencia = "melhorou" if melhorou else "piorou"
        linhas.append({
            "rotulo": rotulo, "antes": _formatar(chave, a), "depois": _formatar(chave, d),
            "tendencia": tendencia,
        })
    return linhas


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Captura/compara instantâneos de desempenho."""
    interface.cabecalho("📊 Antes e depois", "Meça o PC, otimize e veja o ganho real.")
    anterior = _carregar()

    opcoes: list[tuple[str, Any]] = []
    if anterior:
        opcoes.append((f"📸  Comparar agora com a captura de {anterior.get('em', '?')}", "comparar"))
        opcoes.append(("🔄  Substituir a captura 'antes' por uma nova (agora)", "capturar"))
    else:
        opcoes.append(("📸  Capturar o estado ATUAL (antes de otimizar)", "capturar"))
    opcoes.append(("↩  Voltar", "voltar"))

    escolha = interface.menu_selecao("O que deseja fazer?", opcoes)
    if escolha in (None, "voltar"):
        return

    if escolha == "capturar":
        snap = capturar()
        if _salvar(snap):
            interface.sucesso(
                "Captura 'antes' salva! Agora aplique suas otimizações (perfis, "
                "limpeza, inicialização...) e volte aqui para comparar."
            )
            _tabela_snapshot(snap)
        else:
            interface.erro("Não consegui salvar a captura (sem permissão de escrita?).")
        return

    # comparar
    depois = capturar()
    linhas = comparar(anterior, depois)
    tabela = interface.nova_tabela(
        f"Comparação (antes: {anterior.get('em', '?')} → agora)",
        ["Métrica", "Antes", "Depois", "Resultado"],
    )
    icones = {
        "melhorou": f"[{config.COR_OK}]▲ melhorou[/]",
        "piorou": f"[{config.COR_ERRO}]▼ piorou[/]",
        "igual": f"[{config.COR_DIM}]= igual[/]",
    }
    for ln in linhas:
        tabela.add_row(ln["rotulo"], ln["antes"], ln["depois"], icones[ln["tendencia"]])
    interface.imprimir_tabela(tabela)
    melhoras = sum(1 for ln in linhas if ln["tendencia"] == "melhorou")
    interface.info(f"{melhoras} de {len(linhas)} métricas melhoraram. "
                   "Lembre: reiniciar o PC ajuda a refletir vários ajustes.")


def _tabela_snapshot(snap: dict[str, Any]) -> None:
    tabela = interface.nova_tabela("Estado capturado", ["Métrica", "Valor"])
    for chave, (rotulo, _un, _m) in _METRICAS.items():
        tabela.add_row(rotulo, _formatar(chave, snap.get(chave, 0)))
    interface.imprimir_tabela(tabela)
