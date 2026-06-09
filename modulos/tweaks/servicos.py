"""Tweak: otimização de serviços do Windows.

Só permite mexer em serviços de uma whitelist curada
(``dados/servicos_seguros.json``). Cada serviço traz descrição clara e nível
de risco. Serviços críticos do sistema NUNCA aparecem aqui. O estado original
(tipo de inicialização) é capturado antes de qualquer mudança, garantindo o
"desfazer".
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Optional

import config
from modulos import interface, seguranca

try:  # pragma: no cover
    import wmi  # type: ignore
except Exception:  # noqa: BLE001
    wmi = None  # type: ignore

# Mapeia o StartMode do WMI para o argumento do 'sc config start='.
_MAPA_SC = {
    "auto": "auto",
    "automatic": "auto",
    "manual": "demand",
    "demand": "demand",
    "disabled": "disabled",
    "boot": "boot",
    "system": "system",
}

# Tradução para exibição amigável em pt-BR (não afeta a lógica/comandos).
_PT_ESTADO = {"running": "Em execução", "stopped": "Parado", "paused": "Pausado"}
_PT_INICIO = {
    "auto": "Automático",
    "automatic": "Automático",
    "manual": "Manual",
    "demand": "Manual",
    "disabled": "Desativado",
    "boot": "Boot",
    "system": "Sistema",
}


def _pt_estado(valor: str) -> str:
    return _PT_ESTADO.get(str(valor).lower(), valor)


def _pt_inicio(valor: str) -> str:
    return _PT_INICIO.get(str(valor).lower(), valor)


def _carregar_whitelist() -> list[dict[str, Any]]:
    """Carrega a lista curada de serviços seguros do arquivo JSON."""
    try:
        with config.ARQUIVO_SERVICOS_SEGUROS.open("r", encoding="utf-8") as fp:
            dados = json.load(fp)
        return list(dados.get("servicos", []))
    except (OSError, json.JSONDecodeError) as exc:
        seguranca.registrar(f"Falha ao carregar whitelist de serviços: {exc}", logging.ERROR)
        return []


def _conectar() -> Optional[Any]:
    if wmi is None or not sys.platform.startswith("win"):
        return None
    try:
        return wmi.WMI()
    except Exception:  # noqa: BLE001
        return None


def _todos_estados(c: Optional[Any]) -> Optional[dict[str, dict[str, Any]]]:
    """Lê o estado de TODOS os serviços de uma vez (1 só consulta ao WMI).

    Consultar serviço por serviço deixava a tela lenta. Aqui buscamos tudo de
    uma vez e indexamos por nome (minúsculo).

    Returns:
        ``{nome_minusculo: {existe, start_mode, state}}`` ou ``None`` se o WMI
        não estiver disponível (aí o chamador usa o ``sc`` como reserva).
    """
    if c is None:
        return None
    mapa: dict[str, dict[str, Any]] = {}
    try:
        for svc in c.Win32_Service():
            nome = getattr(svc, "Name", None)
            if not nome:
                continue
            mapa[str(nome).lower()] = {
                "existe": True,
                "start_mode": (getattr(svc, "StartMode", "-") or "-"),
                "state": (getattr(svc, "State", "-") or "-"),
            }
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar(f"WMI Win32_Service() falhou: {exc}", logging.WARNING)
        return None
    return mapa


def _estado_por_sc(nome: str) -> dict[str, Any]:
    """Reserva (sem WMI): consulta o estado de um serviço via 'sc'."""
    info: dict[str, Any] = {"existe": False, "start_mode": "-", "state": "-"}
    codigo, saida, _err = seguranca.executar_comando(["sc", "qc", nome], timeout=20)
    if codigo == 0:
        info["existe"] = True
        for linha in saida.splitlines():
            if "START_TYPE" in linha:
                if "DISABLED" in linha:
                    info["start_mode"] = "Disabled"
                elif "DEMAND" in linha:
                    info["start_mode"] = "Manual"
                elif "AUTO" in linha:
                    info["start_mode"] = "Auto"
    cod_q, saida_q, _e = seguranca.executar_comando(["sc", "query", nome], timeout=20)
    if cod_q == 0:
        for linha in saida_q.splitlines():
            if "STATE" in linha:
                if "RUNNING" in linha:
                    info["state"] = "Running"
                elif "STOPPED" in linha:
                    info["state"] = "Stopped"
    return info


def _estado_servico(nome: str, mapa: Optional[dict[str, dict[str, Any]]]) -> dict[str, Any]:
    """Devolve o estado de um serviço usando o mapa do WMI ou o 'sc' como reserva."""
    if mapa is not None:
        return dict(mapa.get(nome.lower(), {"existe": False, "start_mode": "-", "state": "-"}))
    return _estado_por_sc(nome)


def _aplicar_tipo(nome: str, tipo_sc: str) -> tuple[bool, str]:
    """Aplica um tipo de inicialização ao serviço via 'sc config'."""
    codigo, _saida, erro = seguranca.executar_comando(
        ["sc", "config", nome, "start=", tipo_sc], timeout=30
    )
    if codigo != 0:
        if "Acesso negado" in erro or "Access is denied" in erro or codigo == 5:
            return False, "Acesso negado — execute o programa como administrador."
        return False, f"Falha ao configurar o serviço: {erro or codigo}"
    return True, ""


def _parar_servico(nome: str) -> None:
    """Tenta parar o serviço (ignora se já estava parado)."""
    seguranca.executar_comando(["sc", "stop", nome], timeout=30)


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de otimização de serviços."""
    if not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    whitelist = _carregar_whitelist()
    if not whitelist:
        interface.erro("Não foi possível carregar a lista de serviços seguros.")
        return

    c = _conectar()

    while True:
        interface.cabecalho(
            "Otimização de serviços",
            "Apenas serviços seguros e conhecidos. Sempre reversível.",
        )

        # Lê o estado de todos os serviços de uma vez (rápido) e monta a tabela
        # apenas com os serviços da whitelist que existem nesta máquina.
        mapa_estados = _todos_estados(c)
        linhas: list[dict[str, Any]] = []
        tabela = interface.nova_tabela(
            "Serviços (lista curada)",
            ["#", "Serviço", "Risco", "Estado atual", "Início"],
        )
        for svc in whitelist:
            est = _estado_servico(svc["nome"], mapa_estados)
            if not est["existe"]:
                continue
            risco = svc.get("risco", "baixo")
            cor_risco = config.COR_POR_RISCO.get(risco.lower(), config.COR_NEUTRA)
            linhas.append({**svc, "estado": est})
            tabela.add_row(
                str(len(linhas)),
                svc.get("nome_exibicao", svc["nome"]),
                f"[{cor_risco}]{risco}[/{cor_risco}]",
                _pt_estado(est["state"]),
                _pt_inicio(est["start_mode"]),
            )
        interface.imprimir_tabela(tabela)
        interface.texto(
            "Dica: 'Manual' deixa o serviço ligar só quando algo precisar dele "
            "(opção mais conservadora que 'Desativado').",
            "dim",
        )

        opcoes = [
            ("Ver detalhes de um serviço", "detalhes"),
            ("Alterar o início de um ou mais serviços", "alterar"),
            ("Voltar", "voltar"),
        ]
        escolha = interface.menu_selecao("O que deseja fazer?", opcoes)
        if escolha in (None, "voltar"):
            return
        if escolha == "detalhes":
            _fluxo_detalhes(linhas)
        elif escolha == "alterar":
            _fluxo_alterar(linhas, estado)


def _fluxo_detalhes(linhas: list[dict[str, Any]]) -> None:
    """Mostra a descrição completa de um serviço escolhido."""
    if not linhas:
        interface.info("Nenhum serviço disponível.")
        return
    opcoes = [(svc.get("nome_exibicao", svc["nome"]), i) for i, svc in enumerate(linhas)]
    opcoes.append(("Voltar", None))
    indice = interface.menu_selecao("Qual serviço?", opcoes)
    if indice is None:
        return
    svc = linhas[indice]
    interface.tabela_chave_valor(
        svc.get("nome_exibicao", svc["nome"]),
        [
            ("Nome do serviço", svc["nome"]),
            ("Descrição", svc.get("descricao", "-")),
            ("Risco de desativar", svc.get("risco", "-")),
            ("Recomendado desativar?", "Sim" if svc.get("recomendado_desativar") else "Avaliar"),
            ("Observação", svc.get("observacao", "-")),
            (
                "Estado atual",
                f"{_pt_estado(svc['estado']['state'])} / início {_pt_inicio(svc['estado']['start_mode'])}",
            ),
        ],
    )
    interface.pausar()


def _fluxo_alterar(linhas: list[dict[str, Any]], estado: config.EstadoApp) -> None:
    """Permite selecionar serviços e aplicar um novo tipo de inicialização."""
    if not linhas:
        interface.info("Nenhum serviço disponível.")
        return

    opcoes = [
        (f"{svc.get('nome_exibicao', svc['nome'])}  [risco: {svc.get('risco', '-')}]", i)
        for i, svc in enumerate(linhas)
    ]
    selecionados = interface.menu_multiplo("Marque os serviços a alterar:", opcoes)
    if not selecionados:
        interface.info("Nenhum serviço selecionado.")
        return

    acoes = [
        ("Definir como Manual (recomendado — liga sob demanda)", "demand"),
        ("Desativar (disabled — não liga automaticamente)", "disabled"),
        ("Restaurar Automático (auto)", "auto"),
        ("Cancelar", None),
    ]
    tipo_sc = interface.menu_selecao("Qual início aplicar aos serviços marcados?", acoes)
    if tipo_sc is None:
        interface.info("Operação cancelada.")
        return

    escolhidos = [linhas[i] for i in selecionados]
    resumo = "\n".join(
        f"  • {svc.get('nome_exibicao', svc['nome'])} (atual: {_pt_inicio(svc['estado']['start_mode'])})"
        for svc in escolhidos
    )
    rotulo_acao = {"demand": "Manual", "disabled": "Desativado", "auto": "Automático"}[tipo_sc]
    interface.aviso(
        f"Os serviços abaixo passarão para: [bold]{rotulo_acao}[/bold]\n{resumo}\n\n"
        "O estado atual será guardado para você poder desfazer."
    )

    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: nada foi alterado.")
        return
    if not interface.confirmar("Confirmar a alteração destes serviços?", padrao=False):
        interface.info("Operação cancelada.")
        return

    seguranca.garantir_ponto_restauracao(estado)
    for svc in escolhidos:
        _alterar_um(svc, tipo_sc)


def _alterar_um(svc: dict[str, Any], tipo_sc: str) -> None:
    """Aplica a mudança a um serviço, registrando o original para desfazer."""
    nome = svc["nome"]
    nome_exibicao = svc.get("nome_exibicao", nome)
    start_original = svc["estado"]["start_mode"]

    ok, msg = _aplicar_tipo(nome, tipo_sc)
    if not ok:
        interface.erro(f"{nome_exibicao}: {msg}")
        return

    # Se desativando/manual, também para o serviço agora (se estiver rodando).
    if tipo_sc in ("disabled", "demand") and svc["estado"]["state"].lower() == "running":
        _parar_servico(nome)

    seguranca.registrar_acao("servicos", f"'{nome}' -> {tipo_sc}", True, f"original={start_original}")
    seguranca.registrar_desfazer(
        "servicos",
        f"Restaurar serviço {nome_exibicao} para '{_pt_inicio(start_original)}'",
        "servico",
        {"nome": nome, "start_original": _MAPA_SC.get(start_original.lower(), "demand")},
    )
    interface.sucesso(f"{nome_exibicao}: início alterado para '{_pt_inicio(tipo_sc)}'.")
