"""Premium: Pontuação de saúde do PC (0–100 + nota A–F).

Transforma o diagnóstico em uma nota única e fácil de entender, listando os
fatores que custam pontos e COMO resolver cada um. É só leitura/cálculo —
não altera nada no sistema. Também é reaproveitado pelo relatório (HTML).
"""

from __future__ import annotations

from typing import Any

import config
from modulos import interface


def _pct_livre_pior(discos: list[dict[str, Any]]) -> float:
    """Menor percentual de espaço LIVRE entre os discos fixos (o mais crítico)."""
    livres = []
    for d in discos:
        total = d.get("total", 0) or 0
        if total <= 0:
            continue
        livres.append(100.0 - float(d.get("percent", 0) or 0))
    return min(livres) if livres else 100.0


def _uptime_dias(perfil: dict[str, Any]) -> float:
    """Extrai os dias ligados a partir do texto de uptime (ex.: '8d 04h 12m')."""
    txt = str(perfil.get("sistema", {}).get("uptime", "") or "")
    if "d" in txt:
        try:
            return float(txt.split("d", 1)[0].strip())
        except ValueError:
            return 0.0
    return 0.0


def calcular(perfil: dict[str, Any]) -> dict[str, Any]:
    """Calcula a pontuação de saúde e os fatores a partir do perfil.

    Returns:
        Dicionário com ``pontuacao`` (0–100), ``nota`` (A–F), ``cor`` e duas
        listas: ``problemas`` (o que tirou pontos + como resolver) e
        ``positivos`` (o que está bom).
    """
    perfil = perfil or {}
    mem = perfil.get("memoria", {})
    discos = perfil.get("armazenamento", []) or []
    inicio = perfil.get("inicializacao", []) or []

    pontos = 100
    problemas: list[dict[str, str]] = []
    positivos: list[str] = []

    # --- RAM ---
    ram_gb = float(mem.get("total_gb", 0) or 0)
    if ram_gb <= 0:
        pass
    elif ram_gb < 4:
        pontos -= 25
        problemas.append({"fator": "Memória RAM muito baixa",
                          "detalhe": f"{ram_gb:.0f} GB — considere um upgrade; feche apps e reduza a inicialização."})
    elif ram_gb < 8:
        pontos -= 15
        problemas.append({"fator": "Pouca memória RAM",
                          "detalhe": f"{ram_gb:.0f} GB — reduza programas na inicialização e os efeitos visuais."})
    elif ram_gb < 16:
        pontos -= 5
        positivos.append(f"RAM adequada ({ram_gb:.0f} GB)")
    else:
        positivos.append(f"RAM folgada ({ram_gb:.0f} GB)")

    # --- Espaço livre em disco (o pior drive) ---
    livre_pct = _pct_livre_pior(discos)
    if not discos:
        pass
    elif livre_pct < 10:
        pontos -= 20
        problemas.append({"fator": "Disco quase cheio",
                          "detalhe": f"só {livre_pct:.0f}% livres no pior disco — use a Limpeza e remova arquivos grandes."})
    elif livre_pct < 15:
        pontos -= 12
        problemas.append({"fator": "Pouco espaço em disco",
                          "detalhe": f"{livre_pct:.0f}% livres — uma limpeza ajuda a respirar."})
    elif livre_pct < 25:
        pontos -= 5
        problemas.append({"fator": "Espaço em disco apertando",
                          "detalhe": f"{livre_pct:.0f}% livres — de olho para não encher."})
    else:
        positivos.append(f"Bom espaço livre em disco ({livre_pct:.0f}%)")

    # --- SSD x HDD ---
    tem_ssd = any("SSD" in (d.get("tipo", "") or "").upper() for d in discos)
    if discos and not tem_ssd:
        pontos -= 10
        problemas.append({"fator": "Sem SSD",
                          "detalhe": "o sistema roda em HDD — um SSD é o upgrade que mais acelera um PC."})
    elif tem_ssd:
        positivos.append("Sistema com SSD")

    # --- Inicialização ---
    n = len(inicio)
    if n > 12:
        pontos -= 14
        problemas.append({"fator": f"Inicialização cheia ({n} programas)",
                          "detalhe": "desative o que não precisa abrir junto com o Windows (menu Inicialização)."})
    elif n > 8:
        pontos -= 8
        problemas.append({"fator": f"Muitos programas na inicialização ({n})",
                          "detalhe": "revise a lista — o boot fica mais rápido."})
    elif n > 5:
        pontos -= 4
        problemas.append({"fator": f"Inicialização um pouco cheia ({n})",
                          "detalhe": "dá para enxugar alguns itens."})
    elif n:
        positivos.append(f"Inicialização enxuta ({n} itens)")

    # --- Saúde física dos discos (crítico) ---
    for d in discos:
        saude = (d.get("saude") or "").lower()
        if saude and saude not in ("saudável", "saudavel", "ok", "-", ""):
            pontos -= 30
            problemas.append({"fator": f"Disco {d.get('unidade', '?')} com saúde '{d.get('saude')}'",
                              "detalhe": "FAÇA BACKUP já — pode ser falha iminente de hardware."})
            break

    # --- Uptime (reiniciar de vez em quando) ---
    dias = _uptime_dias(perfil)
    if dias > 7:
        pontos -= 5
        problemas.append({"fator": f"Sem reiniciar há {dias:.0f} dias",
                          "detalhe": "um reinício limpa a memória e aplica atualizações pendentes."})

    pontos = max(0, min(100, pontos))
    nota, cor = _nota_e_cor(pontos)
    return {"pontuacao": pontos, "nota": nota, "cor": cor,
            "problemas": problemas, "positivos": positivos}


def _nota_e_cor(p: int) -> tuple[str, str]:
    """Converte a pontuação em nota (A–F) e cor do tema."""
    if p >= 90:
        return "A", config.COR_OK
    if p >= 80:
        return "B", config.COR_OK
    if p >= 70:
        return "C", config.COR_AVISO
    if p >= 60:
        return "D", config.COR_AVISO
    return "F", config.COR_ERRO


def _barra(p: int, largura: int = 28) -> str:
    """Monta uma barra textual proporcional à pontuação."""
    cheias = round(largura * p / 100)
    return "█" * cheias + "░" * (largura - cheias)


# ---------------------------------------------------------------------------
# Fluxo / exibição
# ---------------------------------------------------------------------------
def exibir(resultado: dict[str, Any]) -> None:
    """Mostra a pontuação de saúde de forma bonita e didática."""
    p = resultado["pontuacao"]
    cor = resultado["cor"]
    from rich.panel import Panel
    from rich.align import Align
    from rich.text import Text
    from rich import box

    corpo = Text(justify="center")
    corpo.append(f"\n{p}", style=f"bold {cor}")
    corpo.append("/100\n", style=config.COR_DIM)
    corpo.append(f"Nota {resultado['nota']}\n\n", style=f"bold {cor}")
    corpo.append(_barra(p), style=cor)
    interface.console.print(
        Panel(Align.center(corpo), title="🏆 Saúde do PC", border_style=cor,
              box=box.HEAVY, padding=(0, 4))
    )

    if resultado["problemas"]:
        tabela = interface.nova_tabela("O que está custando pontos", ["Fator", "Como melhorar"])
        for prob in resultado["problemas"]:
            tabela.add_row(f"[{config.COR_AVISO}]{interface.escapar(prob['fator'])}[/]",
                           interface.escapar(prob["detalhe"]))
        interface.imprimir_tabela(tabela)
    if resultado["positivos"]:
        interface.texto("✔ Pontos fortes: " + " · ".join(resultado["positivos"]), config.COR_OK)
    if not resultado["problemas"]:
        interface.sucesso("Seu PC está em ótima forma! 🎉")


def menu(estado: config.EstadoApp) -> None:
    """Calcula e exibe a pontuação de saúde (coleta o diagnóstico se preciso)."""
    from modulos import diagnostico

    interface.cabecalho("🏆 Pontuação de saúde do PC", "Uma nota de 0 a 100 do estado geral da máquina.")
    if not estado.diagnostico_pronto():
        interface.info("Preciso do diagnóstico para calcular a nota (é rápido).")
        if not interface.confirmar("Coletar o diagnóstico agora?", padrao=True):
            return
        estado.perfil = diagnostico.coletar_perfil()
    exibir(calcular(estado.perfil))
