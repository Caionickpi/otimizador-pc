"""Tweak: plano de energia.

Permite ativar planos internos do Windows (Equilibrado, Alto desempenho,
Economia) ou criar um plano otimizado. A sugestão se adapta a desktop ou
notebook — em notebooks, avisamos sobre o impacto do 'Alto desempenho' na
bateria. O plano ativo anterior é guardado para o 'desfazer'.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

import config
from modulos import interface, seguranca


def _plano_ativo() -> tuple[str, str]:
    """Retorna (guid, nome) do plano de energia atualmente ativo."""
    codigo, saida, _err = seguranca.executar_comando(["powercfg", "/getactivescheme"], timeout=20)
    if codigo != 0 or not saida:
        return "-", "-"
    return _extrair_guid(saida), _extrair_nome(saida)


def _planos_disponiveis() -> list[dict[str, Any]]:
    """Lista os planos de energia existentes (guid, nome, ativo?)."""
    codigo, saida, _err = seguranca.executar_comando(["powercfg", "/list"], timeout=20)
    planos: list[dict[str, Any]] = []
    if codigo != 0:
        return planos
    for linha in saida.splitlines():
        if "GUID" in linha and ":" in linha:
            guid = _extrair_guid(linha)
            nome = _extrair_nome(linha)
            ativo = linha.strip().endswith("*")
            if guid != "-":
                planos.append({"guid": guid, "nome": nome, "ativo": ativo})
    return planos


def _extrair_guid(linha: str) -> str:
    partes = linha.split(":", 1)
    if len(partes) == 2 and partes[1].strip():
        return partes[1].strip().split()[0]
    return "-"


def _extrair_nome(linha: str) -> str:
    inicio, fim = linha.find("("), linha.rfind(")")
    if 0 <= inicio < fim:
        return linha[inicio + 1 : fim].strip()
    return linha.strip()


def _ativar_plano(guid: str) -> tuple[bool, str]:
    """Ativa um plano de energia pelo GUID."""
    codigo, _saida, erro = seguranca.executar_comando(["powercfg", "/setactive", guid], timeout=30)
    if codigo == 0:
        return True, ""
    return False, erro or "Falha ao ativar o plano (talvez exija administrador)."


def _criar_plano_otimizado(tem_bateria: bool) -> tuple[bool, str, Optional[str]]:
    """Cria um plano otimizado duplicando um plano base e ajustando tempos.

    Returns:
        (sucesso, mensagem, guid_criado).
    """
    base = config.GUID_PLANO_EQUILIBRADO if tem_bateria else config.GUID_PLANO_ALTO_DESEMPENHO
    codigo, saida, erro = seguranca.executar_comando(
        ["powercfg", "/duplicatescheme", base], timeout=30
    )
    if codigo != 0:
        return False, erro or "Não foi possível duplicar o plano base.", None

    novo_guid = _extrair_guid(saida)
    if novo_guid == "-":
        return False, "Não consegui identificar o GUID do novo plano.", None

    seguranca.executar_comando(
        ["powercfg", "/changename", novo_guid, f"{config.NOME_APP} - Otimizado",
         "Plano criado pelo Otimizador PC"],
        timeout=20,
    )
    _ativar_plano(novo_guid)

    # Ajustes leves no plano agora ativo. Em notebook, preserva economia na
    # bateria (só mexe nos tempos ligado na tomada).
    seguranca.executar_comando(["powercfg", "/change", "monitor-timeout-ac", "15"], timeout=20)
    if not tem_bateria:
        seguranca.executar_comando(["powercfg", "/change", "standby-timeout-ac", "0"], timeout=20)
        seguranca.executar_comando(["powercfg", "/change", "disk-timeout-ac", "0"], timeout=20)

    return True, "Plano otimizado criado e ativado.", novo_guid


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de ajuste do plano de energia."""
    if not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    energia_perfil = estado.perfil.get("energia", {}) if estado.perfil else {}
    if energia_perfil:
        tem_bateria = bool(energia_perfil.get("eh_portatil", energia_perfil.get("tem_bateria")))
        origem_deteccao = "diagnóstico"
    else:
        # Sem diagnóstico: reserva rápida via bateria (antes assumia desktop em
        # silêncio — perigoso para as escolhas de plano em notebook).
        try:
            import psutil

            tem_bateria = psutil.sensors_battery() is not None
        except Exception:  # noqa: BLE001
            tem_bateria = False
        origem_deteccao = "detecção rápida — rode o Diagnóstico p/ precisão"
    tipo_maquina = "notebook" if tem_bateria else "desktop"

    interface.cabecalho(
        "Plano de energia",
        f"Máquina detectada: {tipo_maquina} ({origem_deteccao}).",
    )

    guid_atual, nome_atual = _plano_ativo()
    interface.info(f"Plano ativo agora: [bold]{nome_atual}[/bold]")

    if tem_bateria:
        interface.aviso(
            "Você está em um notebook. O plano 'Alto desempenho' aumenta o "
            "consumo de bateria e o aquecimento. Para o dia a dia, 'Equilibrado' "
            "costuma ser a melhor escolha."
        )

    opcoes = [
        ("Equilibrado (recomendado para a maioria)", config.GUID_PLANO_EQUILIBRADO),
        ("Alto desempenho", config.GUID_PLANO_ALTO_DESEMPENHO),
        ("Economia de energia", config.GUID_PLANO_ECONOMIA),
        (f"Criar plano otimizado ({config.NOME_APP})", "criar"),
        ("Voltar", "voltar"),
    ]
    escolha = interface.menu_selecao("Qual plano deseja ativar?", opcoes)
    if escolha in (None, "voltar"):
        return

    # Aviso extra ao escolher alto desempenho em notebook.
    if escolha == config.GUID_PLANO_ALTO_DESEMPENHO and tem_bateria:
        if not interface.confirmar(
            "Confirma ativar 'Alto desempenho' mesmo sendo um notebook (gasta mais bateria)?",
            padrao=False,
        ):
            interface.info("Operação cancelada.")
            return

    if estado.simulacao:
        alvo = "plano otimizado" if escolha == "criar" else "plano selecionado"
        interface.info(f"MODO SIMULAÇÃO: o {alvo} seria ativado. Nada foi alterado.")
        return

    if not interface.confirmar("Aplicar esta mudança de plano de energia?", padrao=True):
        interface.info("Operação cancelada.")
        return

    seguranca.garantir_ponto_restauracao(estado)

    if escolha == "criar":
        ok, msg, _novo = _criar_plano_otimizado(tem_bateria)
    else:
        ok, msg = _ativar_plano(escolha)

    if ok:
        # Registra o plano anterior para permitir desfazer.
        seguranca.registrar_desfazer(
            "energia",
            f"Voltar para o plano de energia: {nome_atual}",
            "plano_energia",
            {"guid_anterior": guid_atual},
        )
        seguranca.registrar_acao("energia", "Plano de energia alterado", True, f"de {nome_atual}")
        novo_guid, novo_nome = _plano_ativo()
        interface.sucesso(f"Plano de energia ativo agora: {novo_nome}.\n{msg}")
    else:
        seguranca.registrar_acao("energia", "Plano de energia", False, msg)
        interface.erro(msg)
