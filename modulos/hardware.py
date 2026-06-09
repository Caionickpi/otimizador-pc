"""Perfil de otimização derivado do diagnóstico (a base da escalabilidade).

Transforma o diagnóstico bruto em um "perfil de otimização" enxuto, usado para
adaptar recomendações e ajustes ao hardware real de cada PC — a base da
"experiência única por computador". Também classifica jogos (competitivo x
geral) para orientar a otimização por jogo.

Não depende de Windows: opera sobre o dicionário de diagnóstico já coletado.
"""

from __future__ import annotations

from typing import Any

# Palavras-chave de jogos competitivos (onde latência/FPS importam mais).
_JOGOS_COMPETITIVOS = (
    "counter-strike", "cs2", "cs:go", "csgo", "valorant", "league of legends",
    "dota", "fortnite", "apex legends", "overwatch", "rainbow six", "siege",
    "rocket league", "pubg", "call of duty", "warzone", "modern warfare",
    "fall guys", "team fortress", "paladins", "the finals", "marvel rivals",
)


def _vendor_gpu(nome: str) -> str:
    """Identifica o fabricante da GPU pelo nome reportado."""
    n = (nome or "").upper()
    if any(t in n for t in ("NVIDIA", "GEFORCE", "RTX", "GTX")):
        return "NVIDIA"
    if any(t in n for t in ("RADEON", "AMD", " RX")):
        return "AMD"
    if "INTEL" in n:
        return "Intel"
    return "-"


def perfil_otimizacao(perfil: dict[str, Any]) -> dict[str, Any]:
    """Resume o diagnóstico em um perfil de decisão para os ajustes."""
    perfil = perfil or {}
    mem = perfil.get("memoria", {})
    gpus = perfil.get("gpu", []) or []
    discos = perfil.get("armazenamento", []) or []
    energia = perfil.get("energia", {})
    cpu = perfil.get("cpu", {})

    vendors = [_vendor_gpu(g.get("modelo", "")) for g in gpus]
    reais = [v for v in vendors if v != "-"]
    tem_dgpu = ("NVIDIA" in vendors) or ("AMD" in vendors)
    tem_igpu = "Intel" in vendors
    ram_gb = float(mem.get("total_gb", 0) or 0)
    # A GPU "principal" para jogos é a dedicada (NVIDIA/AMD), se houver.
    gpu_principal = next((v for v in vendors if v in ("NVIDIA", "AMD")), None)
    gpu_principal = gpu_principal or (reais[0] if reais else "-")

    return {
        "gpu_principal": gpu_principal,
        "gpus": [g.get("modelo", "-") for g in gpus],
        "tem_dgpu": tem_dgpu,
        "hibrido": tem_dgpu and tem_igpu,        # típico de notebook gamer
        "ram_gb": ram_gb,
        "ram_baixa": 0 < ram_gb <= 8,
        "tem_ssd": any("SSD" in (d.get("tipo", "") or "").upper() for d in discos),
        "notebook": bool(energia.get("tem_bateria")),
        "nucleos": int(cpu.get("nucleos_fisicos", 0) or 0),
    }


def resumo_curto(hw: dict[str, Any]) -> str:
    """Uma linha amigável com o perfil do PC, para cabeçalhos."""
    tipo = "Notebook" if hw.get("notebook") else "Desktop"
    gpu = hw.get("gpu_principal", "-")
    ram = hw.get("ram_gb", 0) or 0
    disco = "SSD" if hw.get("tem_ssd") else "HDD"
    return f"{tipo} · GPU {gpu} · {ram:.0f} GB RAM · disco {disco}"


def classificar_jogo(nome: str) -> str:
    """Classifica um jogo como 'competitivo' (latência) ou 'geral' (AAA)."""
    n = (nome or "").lower()
    return "competitivo" if any(k in n for k in _JOGOS_COMPETITIVOS) else "geral"
