"""Análise do perfil e geração de recomendações inteligentes.

Em vez de dicas genéricas, este módulo cruza os dados do diagnóstico para
sugerir ações realmente pertinentes à máquina (ex.: nunca recomendar
desfragmentar um SSD; recomendar TRIM no lugar). As recomendações vêm em
ordem de prioridade, cada uma com o impacto esperado.
"""

from __future__ import annotations

from typing import Any

import config
from modulos import interface

# Pesos para ordenar por prioridade (maior = mostrado primeiro).
_PESO_PRIORIDADE = {"alta": 0, "media": 1, "baixa": 2}


def _nova(
    titulo: str,
    descricao: str,
    prioridade: str,
    impacto: str,
    categoria: str,
) -> dict[str, Any]:
    """Cria uma recomendação padronizada."""
    return {
        "titulo": titulo,
        "descricao": descricao,
        "prioridade": prioridade,
        "impacto": impacto,
        "categoria": categoria,
    }


def gerar_recomendacoes(perfil: dict[str, Any]) -> list[dict[str, Any]]:
    """Gera a lista de recomendações com base no perfil coletado.

    Returns:
        Lista de recomendações já ordenadas por prioridade.
    """
    if not perfil:
        return []

    recs: list[dict[str, Any]] = []
    memoria = perfil.get("memoria", {})
    discos = perfil.get("armazenamento", [])
    energia = perfil.get("energia", {})
    inicializacao = perfil.get("inicializacao", [])
    tem_bateria = bool(energia.get("tem_bateria"))

    _analisar_discos(discos, recs)
    _analisar_memoria(memoria, inicializacao, recs)
    _analisar_inicializacao(inicializacao, recs)
    _analisar_energia(energia, tem_bateria, recs)

    # Recomendação geral de limpeza sempre disponível (baixo risco, útil).
    recs.append(
        _nova(
            "Limpeza de arquivos temporários",
            "Liberar espaço removendo temporários, cache do Windows Update e "
            "Lixeira. Ação segura e reversível na prática (são arquivos descartáveis).",
            "baixa",
            "Libera espaço em disco e pode acelerar o sistema.",
            "limpeza",
        )
    )

    recs.sort(key=lambda r: _PESO_PRIORIDADE.get(r["prioridade"], 3))
    return recs


def _analisar_discos(discos: list[dict[str, Any]], recs: list[dict[str, Any]]) -> None:
    """Analisa cada unidade: SSD x HDD, TRIM x desfragmentação, espaço livre."""
    for disco in discos:
        unidade = disco.get("unidade", "?")
        tipo = (disco.get("tipo") or "").upper()
        percent = disco.get("percent", 0)
        livre = disco.get("livre", 0)
        livre_gb = livre / (1024 ** 3)

        if "SSD" in tipo:
            recs.append(
                _nova(
                    f"SSD {unidade}: garantir TRIM (não desfragmentar)",
                    "Esta unidade é um SSD. Desfragmentar é desnecessário e desgasta "
                    "a unidade. O recomendado é manter o TRIM ativo e desativar a "
                    "desfragmentação agendada para este disco.",
                    "media",
                    "Preserva a vida útil do SSD e mantém o desempenho.",
                    "disco",
                )
            )
        elif "HDD" in tipo:
            recs.append(
                _nova(
                    f"HDD {unidade}: desfragmentar/otimizar",
                    "Esta unidade é um disco mecânico (HDD). A desfragmentação "
                    "reorganiza os arquivos e pode melhorar a velocidade de leitura.",
                    "baixa",
                    "Pode acelerar a abertura de arquivos e programas.",
                    "disco",
                )
            )

        # Pouco espaço livre: prioridade alta.
        if percent >= (100 - config.LIMIAR_DISCO_LIVRE_PCT) or livre_gb <= config.LIMIAR_DISCO_LIVRE_GB:
            recs.append(
                _nova(
                    f"Pouco espaço livre em {unidade}",
                    f"Restam apenas {interface.formatar_bytes(livre)} livres "
                    f"({100 - percent:.0f}%). Pouco espaço deixa o Windows lento. "
                    "Priorize a limpeza de temporários e a remoção de arquivos grandes.",
                    "alta",
                    "Evita lentidão e travamentos por falta de espaço.",
                    "limpeza",
                )
            )

        # Saúde do disco comprometida: alerta crítico.
        saude = (disco.get("saude") or "").lower()
        if saude and saude not in ("saudável", "saudavel", "ok", "-"):
            recs.append(
                _nova(
                    f"Saúde do disco {unidade}: {disco.get('saude')}",
                    "O status de saúde reportado não é 'Saudável'. Faça backup dos "
                    "seus dados importantes o quanto antes. Esta ferramenta não "
                    "conserta hardware com defeito.",
                    "alta",
                    "Previne perda de dados por falha iminente do disco.",
                    "disco",
                )
            )


def _analisar_memoria(
    memoria: dict[str, Any],
    inicializacao: list[dict[str, Any]],
    recs: list[dict[str, Any]],
) -> None:
    """Analisa a RAM: pouca memória aumenta a prioridade de várias ações."""
    total_gb = memoria.get("total_gb", 0)
    if total_gb and total_gb <= config.LIMIAR_RAM_BAIXA_GB:
        recs.append(
            _nova(
                f"RAM limitada ({total_gb:.0f} GB)",
                "Com pouca memória, vale priorizar: reduzir programas na "
                "inicialização, ajustar a memória virtual e diminuir os efeitos "
                "visuais para liberar recursos.",
                "alta",
                "Reduz lentidão e uso de disco como memória (swap).",
                "memoria",
            )
        )
        recs.append(
            _nova(
                "Reduzir efeitos visuais",
                "Ajustar o Windows para priorizar desempenho desliga animações e "
                "transparências, aliviando a CPU/GPU e a memória.",
                "media",
                "Interface mais responsiva em máquinas modestas.",
                "visual",
            )
        )


def _analisar_inicializacao(inicializacao: list[dict[str, Any]], recs: list[dict[str, Any]]) -> None:
    """Analisa a quantidade de programas na inicialização."""
    quantidade = len(inicializacao)
    if quantidade > config.LIMIAR_MUITOS_STARTUP:
        recs.append(
            _nova(
                f"Muitos programas na inicialização ({quantidade})",
                "Vários programas abrindo junto com o Windows deixam o boot lento. "
                "Revise a lista e desative os que você não usa logo ao ligar o PC. "
                "A desativação é reversível.",
                "alta",
                "Boot mais rápido e menos consumo de memória ao ligar.",
                "inicializacao",
            )
        )


def _analisar_energia(
    energia: dict[str, Any],
    tem_bateria: bool,
    recs: list[dict[str, Any]],
) -> None:
    """Analisa o plano de energia conforme desktop ou notebook."""
    plano = (energia.get("plano_ativo") or "").lower()
    em_economia = "economia" in plano or "saver" in plano

    if em_economia and not tem_bateria:
        recs.append(
            _nova(
                "Desktop em modo Economia de energia",
                "Seu desktop está no plano 'Economia de energia', que limita o "
                "desempenho. Em um computador ligado na tomada, o plano "
                "'Equilibrado' (ou 'Alto desempenho') costuma ser melhor.",
                "media",
                "Mais desempenho sem custo de bateria (é um desktop).",
                "energia",
            )
        )
    elif tem_bateria:
        recs.append(
            _nova(
                "Notebook: cuidado com 'Alto desempenho'",
                "Em notebooks, o plano 'Alto desempenho' consome muito mais "
                "bateria e esquenta mais. Prefira 'Equilibrado' no dia a dia; use "
                "'Alto desempenho' só quando estiver na tomada.",
                "baixa",
                "Equilíbrio entre desempenho e duração da bateria.",
                "energia",
            )
        )


def exibir_recomendacoes(recomendacoes: list[dict[str, Any]]) -> None:
    """Exibe as recomendações em uma tabela colorida por prioridade."""
    if not recomendacoes:
        interface.info(
            "Nenhuma recomendação específica. Rode o diagnóstico primeiro "
            "(ou seu sistema já está bem ajustado!)."
        )
        return

    tabela = interface.nova_tabela(
        "Recomendações personalizadas (em ordem de prioridade)",
        ["Prioridade", "Recomendação", "Por quê / Impacto"],
    )
    rotulo_prioridade = {"alta": "ALTA", "media": "MÉDIA", "baixa": "BAIXA"}
    for rec in recomendacoes:
        prioridade = rec.get("prioridade", "baixa")
        cor = config.COR_POR_PRIORIDADE.get(prioridade, config.COR_INFO)
        rotulo = f"[{cor}]{rotulo_prioridade.get(prioridade, prioridade.upper())}[/{cor}]"
        corpo = f"[bold]{rec.get('titulo', '-')}[/bold]\n{rec.get('descricao', '')}"
        tabela.add_row(rotulo, corpo, rec.get("impacto", "-"))
    interface.imprimir_tabela(tabela)
    interface.texto(
        "\nDica: vá ao menu de cada categoria para aplicar os ajustes com segurança "
        "(sempre com backup e confirmação).",
        "dim",
    )
