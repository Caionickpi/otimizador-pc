"""Tweak: otimização de disco.

Regra de ouro: desfragmentar SOMENTE discos mecânicos (HDD). Em SSD, isso é
prejudicial — o correto é apenas o TRIM (retrim). Quando o tipo do disco é
desconhecido, usamos a otimização do Windows ('/O'), que escolhe sozinha a
ação correta para cada mídia, sem risco para SSDs.

Também verifica se o TRIM está ativo no sistema e, opcionalmente, o ativa.
São operações de manutenção (não alteram configurações de forma que precise
'desfazer').
"""

from __future__ import annotations

import sys
from typing import Any

import config
from modulos import interface, seguranca


def _drives_do_perfil(estado: config.EstadoApp) -> list[dict[str, Any]]:
    """Obtém as unidades a partir do diagnóstico já coletado."""
    discos = estado.perfil.get("armazenamento", []) if estado.perfil else []
    drives: list[dict[str, Any]] = []
    for disco in discos:
        unidade = (disco.get("unidade") or "").rstrip("\\")
        if not unidade or ":" not in unidade:
            continue
        tipo = (disco.get("tipo") or "").upper()
        drives.append({"unidade": unidade, "tipo": tipo})
    return drives


def _acao_para_tipo(tipo: str) -> tuple[list[str], str]:
    """Decide o argumento do defrag e o rótulo conforme o tipo de mídia."""
    if "SSD" in tipo:
        # /L = retrim (TRIM) — sem desfragmentação.
        return (["/L"], "TRIM (retrim)")
    if "HDD" in tipo:
        # /O = otimização (para HDD, equivale a desfragmentar).
        return (["/O"], "Desfragmentar/otimizar")
    # Tipo desconhecido: /O deixa o Windows escolher a ação segura por mídia.
    return (["/O"], "Otimização automática (seguro p/ SSD)")


def _verificar_trim() -> str:
    """Consulta o estado do TRIM no sistema.

    Returns:
        'ativo', 'inativo' ou 'desconhecido'.
    """
    codigo, saida, _err = seguranca.executar_comando(
        ["fsutil", "behavior", "query", "DisableDeleteNotify"], timeout=20
    )
    if codigo != 0 or not saida:
        return "desconhecido"
    # DisableDeleteNotify = 0  -> TRIM ATIVO. = 1 -> TRIM INATIVO.
    texto = saida.replace(" ", "")
    if "=0" in texto:
        return "ativo"
    if "=1" in texto:
        return "inativo"
    return "desconhecido"


def _ativar_trim() -> bool:
    """Ativa o TRIM no sistema (DisableDeleteNotify = 0)."""
    codigo, _s, _e = seguranca.executar_comando(
        ["fsutil", "behavior", "set", "DisableDeleteNotify", "0"], timeout=20
    )
    return codigo == 0


def _otimizar_unidade(unidade: str, args: list[str]) -> tuple[bool, str]:
    """Executa o defrag/otimização em uma unidade (operação demorada).

    Timeout de 4h: a desfragmentação completa de um HDD grande e fragmentado
    pode levar horas — com 30 min, o processo era interrompido no meio e
    reportado como falha (interromper o defrag é seguro, mas frustra).
    """
    codigo, _saida, erro = seguranca.executar_comando(
        ["defrag", unidade, *args], timeout=14400
    )
    if codigo == 0:
        return True, "Concluído."
    if codigo == 5 or "negado" in (erro or "").lower() or "denied" in (erro or "").lower():
        return False, "Acesso negado — execute como administrador."
    return False, erro or f"Falha (código {codigo})."


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de otimização de disco."""
    if not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    interface.cabecalho(
        "Otimização de disco",
        "Desfragmenta HDDs e executa apenas TRIM em SSDs.",
    )

    drives = _drives_do_perfil(estado)
    if not drives:
        interface.aviso(
            "Não há informações de disco. Rode o Diagnóstico no menu principal "
            "antes de usar esta opção."
        )
        return

    # Estado do TRIM no sistema.
    estado_trim = _verificar_trim()
    rotulo_trim = {"ativo": "[green]ATIVO[/green]", "inativo": "[red]INATIVO[/red]", "desconhecido": "desconhecido"}
    interface.info(f"TRIM no sistema: {rotulo_trim.get(estado_trim, estado_trim)}")

    # Monta a tabela de ações por unidade.
    tabela = interface.nova_tabela("Unidades e ação recomendada", ["Unidade", "Tipo", "Ação"])
    for drive in drives:
        _args, rotulo = _acao_para_tipo(drive["tipo"])
        tabela.add_row(drive["unidade"], drive["tipo"] or "-", rotulo)
    interface.imprimir_tabela(tabela)

    # Oferece ativar o TRIM se estiver inativo.
    if estado_trim == "inativo" and not estado.simulacao:
        if interface.confirmar("O TRIM está inativo. Deseja ativá-lo agora (recomendado p/ SSD)?", padrao=True):
            if _ativar_trim():
                seguranca.registrar_acao("disco", "TRIM ativado", True)
                interface.sucesso("TRIM ativado no sistema.")
            else:
                interface.erro("Não foi possível ativar o TRIM (precisa de administrador?).")

    # Seleção das unidades a otimizar.
    opcoes = [(f"{d['unidade']}  ({d['tipo'] or 'tipo desconhecido'})", i) for i, d in enumerate(drives)]
    selecionados = interface.menu_multiplo("Marque as unidades para otimizar:", opcoes)
    if not selecionados:
        interface.info("Nenhuma unidade selecionada.")
        return

    escolhidos = [drives[i] for i in selecionados]
    resumo = "\n".join(
        f"  • {d['unidade']} -> {_acao_para_tipo(d['tipo'])[1]}" for d in escolhidos
    )
    interface.aviso(
        f"Serão executadas estas operações:\n{resumo}\n\n"
        "Em HDD grande/fragmentado isso pode levar HORAS — deixe o programa "
        "aberto (dá para usar o PC normalmente enquanto isso)."
    )

    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: as otimizações acima seriam executadas. Nada foi feito.")
        return
    if not interface.confirmar("Iniciar a otimização agora?", padrao=False):
        interface.info("Operação cancelada.")
        return

    for drive in escolhidos:
        args, rotulo = _acao_para_tipo(drive["tipo"])
        with interface.spinner(f"{rotulo} em {drive['unidade']}") as progresso:
            tarefa = progresso.add_task(f"{rotulo} em {drive['unidade']}", total=None)
            ok, msg = _otimizar_unidade(drive["unidade"], args)
            progresso.update(tarefa, completed=1)
        if ok:
            seguranca.registrar_acao("disco", f"{rotulo} {drive['unidade']}", True)
            interface.sucesso(f"{drive['unidade']}: {rotulo} — {msg}")
        else:
            seguranca.registrar_acao("disco", f"{rotulo} {drive['unidade']}", False, msg)
            interface.erro(f"{drive['unidade']}: {msg}")
