"""Premium: manutenção automática agendada.

Cria uma Tarefa Agendada do Windows (schtasks) que executa a LIMPEZA de
temporários periodicamente, sem abrir a interface — o clássico "configure e
esqueça". É reversível: dá para ver o status e remover a tarefa quando quiser.

A tarefa chama o próprio executável com o argumento ``--tarefa-limpeza``, que
o main intercepta e roda a limpeza em modo silencioso (reaproveitando o módulo
de limpeza já endurecido contra travamentos).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import config
from modulos import interface, seguranca

_NOME_TAREFA = "OtimizadorPC - Manutencao Automatica"
_ARG_LIMPEZA = "--tarefa-limpeza"

# Frequências oferecidas: rótulo -> (schtasks /sc, args extras).
_FREQUENCIAS = {
    "semanal": ("Semanal (todo domingo, 12h)", ["/sc", "WEEKLY", "/d", "SUN", "/st", "12:00"]),
    "diaria": ("Diária (todo dia, 12h)", ["/sc", "DAILY", "/st", "12:00"]),
    "mensal": ("Mensal (dia 1, 12h)", ["/sc", "MONTHLY", "/d", "1", "/st", "12:00"]),
}


def _comando_tarefa() -> str:
    """Comando que a tarefa executará (o próprio .exe com o argumento headless).

    Entre aspas para suportar caminhos com espaços. Fora do .exe (dev), aponta
    para o interpretador + main.py, mantendo o recurso utilizável em testes.
    """
    exe = sys.executable
    if getattr(sys, "frozen", False):
        return f'"{exe}" {_ARG_LIMPEZA}'
    principal = str(config.PASTA_EXECUCAO / "main.py")
    return f'"{exe}" "{principal}" {_ARG_LIMPEZA}'


def _existe() -> bool:
    """Indica se a tarefa agendada já existe."""
    codigo, _s, _e = seguranca.executar_comando(
        ["schtasks", "/query", "/tn", _NOME_TAREFA], timeout=20
    )
    return codigo == 0


def criar(frequencia: str) -> tuple[bool, str]:
    """Cria/atualiza a tarefa agendada com a frequência escolhida."""
    args_freq = _FREQUENCIAS.get(frequencia, _FREQUENCIAS["semanal"])[1]
    comando = [
        "schtasks", "/create", "/tn", _NOME_TAREFA,
        "/tr", _comando_tarefa(), *args_freq, "/f",
    ]
    codigo, _s, erro = seguranca.executar_comando(comando, timeout=30)
    if codigo == 0:
        seguranca.registrar_acao("agendador", "Tarefa de manutenção criada", True, frequencia)
        return True, "Manutenção automática agendada."
    return False, erro or "Falha ao criar a tarefa (tente como administrador)."


def remover() -> tuple[bool, str]:
    """Remove a tarefa agendada."""
    codigo, _s, erro = seguranca.executar_comando(
        ["schtasks", "/delete", "/tn", _NOME_TAREFA, "/f"], timeout=20
    )
    if codigo == 0:
        seguranca.registrar_acao("agendador", "Tarefa de manutenção removida", True)
        return True, "Manutenção automática removida."
    return False, erro or "Falha ao remover a tarefa."


# ---------------------------------------------------------------------------
# Execução headless (chamada pela tarefa agendada via --tarefa-limpeza)
# ---------------------------------------------------------------------------
def executar_limpeza_headless() -> int:
    """Executa a limpeza de temporários sem interface (para a tarefa agendada).

    Reaproveita o módulo de limpeza (já protegido contra travamentos: orçamento
    de tempo, proteção da pasta do próprio .exe e Lixeira com timeout). Nunca
    lança: registra tudo no log e retorna um código de saída.
    """
    seguranca.configurar_logging()
    seguranca.registrar("[agendador] limpeza automática (headless) iniciada.", logging.INFO)
    try:
        from modulos.tweaks import limpeza

        protegidas = limpeza._pastas_protegidas()
        liberado = 0
        for item in limpeza._locais_limpeza():
            bytes_lib, _pend = limpeza._executar_limpeza_item(item, protegidas)
            liberado += bytes_lib
        seguranca.registrar_acao(
            "agendador", "Limpeza automática concluída", True,
            f"liberado ~{interface.formatar_bytes(liberado)}",
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - tarefa em segundo plano nunca deve estourar
        seguranca.registrar_acao("agendador", "Limpeza automática falhou", False, str(exc))
        return 1


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Cria, consulta ou remove a manutenção automática."""
    if not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    interface.cabecalho("🗓️ Manutenção automática",
                        "Agende a limpeza de temporários para rodar sozinha.")
    existe = _existe()
    if existe:
        interface.info("✔ A manutenção automática está [bold]ATIVA[/bold] neste PC.")
    else:
        interface.texto("Nenhuma manutenção automática configurada ainda.", config.COR_DIM)

    interface.texto(
        "A tarefa roda a limpeza em segundo plano (sem abrir o programa) e nunca "
        "mexe em arquivos pessoais — só cache/temporários.",
        config.COR_DIM,
    )

    opcoes: list[tuple[str, Any]] = [("📅  Agendar / alterar frequência", "agendar")]
    if existe:
        opcoes.append(("🧹  Rodar a limpeza automática agora (teste)", "rodar"))
        opcoes.append(("🗑️  Remover a manutenção automática", "remover"))
    opcoes.append(("↩  Voltar", "voltar"))

    escolha = interface.menu_selecao("O que deseja fazer?", opcoes)
    if escolha in (None, "voltar"):
        return

    if escolha == "remover":
        if interface.confirmar("Remover a manutenção automática?", padrao=False):
            ok, msg = remover()
            (interface.sucesso if ok else interface.erro)(msg)
        return

    if escolha == "rodar":
        if estado.simulacao:
            interface.info("MODO SIMULAÇÃO: a limpeza automática seria executada.")
            return
        with interface.spinner("Rodando limpeza automática") as progresso:
            tarefa = progresso.add_task("Limpando", total=None)
            codigo = executar_limpeza_headless()
            progresso.update(tarefa, completed=1)
        (interface.sucesso if codigo == 0 else interface.erro)(
            "Limpeza automática executada (veja os detalhes em 'Ver logs')."
            if codigo == 0 else "A limpeza automática encontrou um problema (veja os logs)."
        )
        return

    # agendar
    op_freq = [(rotulo, chave) for chave, (rotulo, _a) in _FREQUENCIAS.items()]
    op_freq.append(("Cancelar", None))
    freq = interface.menu_selecao("Com que frequência rodar a limpeza?", op_freq)
    if freq is None:
        return
    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: a tarefa agendada seria criada.")
        return
    ok, msg = criar(freq)
    (interface.sucesso if ok else interface.erro)(msg)
    if ok:
        interface.texto("Dica: você pode remover a qualquer momento por aqui ou pelo "
                        "Agendador de Tarefas do Windows.", config.COR_DIM)
