"""Otimizador PC — ponto de entrada e menu principal.

Programa de terminal (TUI) para diagnóstico e ajustes seguros de computadores
Windows. Fluxo: diagnosticar -> analisar/recomendar -> aplicar ajustes
escolhidos (sempre com backup e confirmação).

Princípio número 1: SEGURANÇA. Nenhuma alteração acontece sem descrição,
backup/ponto de restauração, confirmação e registro em log. Uma falha em um
ajuste nunca derruba o programa inteiro.
"""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Any, Callable

import config
from modulos import (
    agendador,
    atualizacao,
    desempenho,
    diagnostico,
    elevacao,
    interface,
    recomendacoes,
    relatorio,
    saude,
    seguranca,
)
from modulos.tweaks import (
    avancado,
    disco,
    energia,
    inicializacao,
    inputlag,
    limpeza,
    otimizar_jogo,
    perfis,
    rede,
    servicos,
    visual,
)


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------
def _verificar_ambiente(estado: config.EstadoApp) -> None:
    """Avisa se o programa não está rodando no Windows (alvo do projeto)."""
    if not estado.windows:
        interface.aviso(
            "Este programa foi feito para o Windows 10/11. Em outro sistema, a "
            "maioria das funções de ajuste não terá efeito. Você ainda pode "
            "navegar pelos menus, mas rode-o no Windows para uso real."
        )
        interface.pausar()


def _tratar_privilegios(estado: config.EstadoApp) -> None:
    """Verifica privilégios e, se necessário, oferece reabrir como admin."""
    estado.eh_admin = elevacao.eh_administrador()
    if estado.eh_admin or not estado.windows:
        return

    interface.aviso(
        "O programa NÃO está rodando como administrador.\n\n"
        "O diagnóstico e as recomendações funcionam normalmente. Porém, vários "
        "ajustes (serviços, energia, rede, inicialização do sistema) exigem "
        "privilégios de administrador para serem aplicados.\n\n"
        "Você pode reabrir o programa elevado agora (vai aparecer o aviso do "
        "Windows / UAC)."
    )
    if interface.confirmar("Reabrir como administrador agora?", padrao=True):
        elevacao.elevar_e_encerrar()  # encerra este processo se conseguir elevar
        # Se chegou aqui, a elevação falhou ou foi recusada:
        interface.info("Seguindo em modo somente-leitura (sem privilégios de admin).")


def _verificar_atualizacao_inicial(estado: config.EstadoApp) -> None:
    """Checagem automática e silenciosa de atualização no início (best-effort).

    Nunca pode atrapalhar a abertura: timeout curto e qualquer erro (sem
    internet, sem release etc.) é engolido — só avisa se houver versão nova.
    """
    try:
        atualizacao.verificar(estado, no_inicio=True)
    except Exception as exc:  # noqa: BLE001 - a abertura nunca pode quebrar por isso
        seguranca.registrar(f"Checagem de atualização no início falhou: {exc}", logging.WARNING)


# ---------------------------------------------------------------------------
# Execução protegida de cada ação
# ---------------------------------------------------------------------------
def _executar_seguro(rotulo: str, funcao: Callable[[], None]) -> None:
    """Executa uma ação capturando qualquer erro, sem derrubar o programa."""
    try:
        funcao()
    except KeyboardInterrupt:
        interface.info("Ação interrompida pelo usuário.")
    except Exception as exc:  # noqa: BLE001 - blindagem do menu principal
        seguranca.registrar(
            f"Erro não tratado em '{rotulo}': {exc}\n{traceback.format_exc()}",
            logging.ERROR,
        )
        interface.erro(
            f"Ocorreu um erro nesta ação ({rotulo}), mas o programa continua "
            f"funcionando normalmente.\n\nDetalhe técnico: {exc}"
        )
    interface.pausar()


# ---------------------------------------------------------------------------
# Ações do menu
# ---------------------------------------------------------------------------
def _acao_diagnostico(estado: config.EstadoApp) -> None:
    """Coleta (ou recoleta) e exibe o diagnóstico da máquina."""
    estado.perfil = diagnostico.coletar_perfil()
    interface.linha_em_branco()
    diagnostico.exibir_perfil(estado.perfil)


def _garantir_diagnostico(estado: config.EstadoApp) -> bool:
    """Garante que há um diagnóstico; oferece coletar se ainda não houver."""
    if estado.diagnostico_pronto():
        return True
    interface.info("Ainda não coletei o diagnóstico desta máquina.")
    if interface.confirmar("Coletar o diagnóstico agora?", padrao=True):
        estado.perfil = diagnostico.coletar_perfil()
        return estado.diagnostico_pronto()
    return False


def _acao_recomendacoes(estado: config.EstadoApp) -> None:
    """Gera e exibe recomendações personalizadas (exige diagnóstico)."""
    if not _garantir_diagnostico(estado):
        interface.aviso("Sem diagnóstico não dá para recomendar com precisão.")
        return
    recs = recomendacoes.gerar_recomendacoes(estado.perfil)
    interface.linha_em_branco()
    recomendacoes.exibir_recomendacoes(recs)


def _acao_simulacao(estado: config.EstadoApp) -> None:
    """Liga/desliga o modo simulação (dry-run)."""
    estado.simulacao = not estado.simulacao
    if estado.simulacao:
        interface.sucesso(
            "MODO SIMULAÇÃO LIGADO.\nA partir de agora, os ajustes apenas mostram "
            "o que fariam, sem alterar nada de verdade."
        )
    else:
        interface.info("Modo simulação desligado. Os ajustes voltarão a aplicar mudanças reais (sempre com confirmação).")


def _acao_desfazer(estado: config.EstadoApp) -> None:
    """Desfaz a última alteração registrada."""
    descricao = seguranca.descrever_ultima_acao()
    if not descricao:
        interface.info("Não há nenhuma alteração para desfazer.")
        return
    interface.aviso(f"Última alteração registrada:\n  {descricao}")
    if not interface.confirmar("Deseja desfazer esta alteração?", padrao=False):
        interface.info("Nada foi desfeito.")
        return
    ok, msg = seguranca.desfazer_ultima_acao()
    (interface.sucesso if ok else interface.erro)(msg)


def _acao_ver_logs(estado: config.EstadoApp) -> None:
    """Mostra as últimas linhas do log do dia e o caminho da pasta de logs."""
    from datetime import datetime

    arquivo = config.PASTA_LOGS / f"otimizador_{datetime.now():%Y-%m-%d}.log"
    interface.cabecalho("Logs", f"Pasta: {config.PASTA_LOGS}")
    if not arquivo.exists():
        interface.info("Ainda não há log para hoje.")
        return
    try:
        linhas = arquivo.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        interface.erro(f"Não consegui ler o log: {exc}")
        return
    ultimas = linhas[-30:]
    interface.texto("\n".join(ultimas) if ultimas else "(log vazio)", config.COR_NEUTRA)
    interface.texto(f"\nMostrando as últimas {len(ultimas)} de {len(linhas)} linhas.", "dim")


def _rotulo_admin(estado: config.EstadoApp) -> str:
    """Texto curto indicando o nível de privilégio."""
    return (
        f"[{config.COR_OK}]✔ administrador[/]"
        if estado.eh_admin
        else f"[{config.COR_AVISO}]● usuário comum[/]"
    )


# ---------------------------------------------------------------------------
# Menu principal
# ---------------------------------------------------------------------------
def _menu_principal(estado: config.EstadoApp) -> None:
    """Laço do menu principal."""
    while True:
        interface.limpar_tela()
        sim = (
            f"[{config.COR_OK}]● LIGADO[/]"
            if estado.simulacao
            else f"[{config.COR_DIM}]○ desligado[/]"
        )
        interface.cabecalho(
            f"⚙  {config.NOME_APP}  [{config.COR_DIM}]v{config.VERSAO_APP}[/]",
            f"Privilégio: {_rotulo_admin(estado)}    [{config.COR_DIM}]│[/]    "
            f"🧪 Simulação: {sim}",
        )

        opcoes: list[Any] = [
            ("1)  🔍  Diagnóstico do computador", "diagnostico"),
            ("2)  💡  Recomendações personalizadas", "recomendacoes"),
            interface.separador("Ajustes"),
            ("3)  🧹  Limpeza de arquivos temporários", "limpeza"),
            ("4)  🚀  Gerenciar inicialização", "inicializacao"),
            ("5)  🛠  Otimizar serviços", "servicos"),
            ("6)  🔋  Plano de energia", "energia"),
            ("7)  🌐  Otimização de rede", "rede"),
            ("8)  ✨  Efeitos visuais / desempenho", "visual"),
            ("9)  💽  Otimização de disco", "disco"),
            interface.separador("Avançado · risco"),
            ("10) 🔥  Otimizações avançadas (jogos e desempenho)", "avancado"),
            ("11) 🖱  Reduzir input lag (mouse/teclado/monitor)", "inputlag"),
            interface.separador("Por jogo"),
            ("12) 🎯  Otimizar para um jogo (detecta no PC)", "otimizar_jogo"),
            interface.separador("⭐ Premium"),
            ("13) 🏆  Pontuação de saúde do PC", "saude"),
            ("14) ⚡  Perfis de otimização (1 clique)", "perfis"),
            ("15) 📊  Antes e depois (desempenho)", "desempenho"),
            ("16) 📄  Gerar relatório (HTML)", "relatorio"),
            ("17) 🗓️  Manutenção automática (agendar limpeza)", "agendador"),
            interface.separador("Ferramentas"),
            (f"18) 🧪  Modo simulação ({'desligar' if estado.simulacao else 'ligar'})", "simulacao"),
            ("19) ↩  Desfazer última alteração", "desfazer"),
            ("20) 📜  Ver logs", "logs"),
            ("21) 🔄  Verificar atualizações", "atualizacao"),
            ("0)  🚪  Sair", "sair"),
        ]
        escolha = interface.menu_selecao("Escolha uma opção:", opcoes)

        if escolha in (None, "sair"):
            _sair(estado)
            return

        acoes: dict[str, tuple[str, Callable[[], None]]] = {
            "diagnostico": ("Diagnóstico", lambda: _acao_diagnostico(estado)),
            "recomendacoes": ("Recomendações", lambda: _acao_recomendacoes(estado)),
            "limpeza": ("Limpeza", lambda: limpeza.menu(estado)),
            "inicializacao": ("Inicialização", lambda: inicializacao.menu(estado)),
            "servicos": ("Serviços", lambda: servicos.menu(estado)),
            "energia": ("Energia", lambda: energia.menu(estado)),
            "rede": ("Rede", lambda: rede.menu(estado)),
            "visual": ("Efeitos visuais", lambda: visual.menu(estado)),
            "disco": ("Disco", lambda: disco.menu(estado)),
            "avancado": ("Otimizações avançadas", lambda: avancado.menu(estado)),
            "inputlag": ("Reduzir input lag", lambda: inputlag.menu(estado)),
            "otimizar_jogo": ("Otimização por jogo", lambda: otimizar_jogo.menu(estado)),
            "saude": ("Pontuação de saúde", lambda: saude.menu(estado)),
            "perfis": ("Perfis de otimização", lambda: perfis.menu(estado)),
            "desempenho": ("Antes e depois", lambda: desempenho.menu(estado)),
            "relatorio": ("Relatório HTML", lambda: relatorio.menu(estado)),
            "agendador": ("Manutenção automática", lambda: agendador.menu(estado)),
            "simulacao": ("Modo simulação", lambda: _acao_simulacao(estado)),
            "desfazer": ("Desfazer", lambda: _acao_desfazer(estado)),
            "logs": ("Ver logs", lambda: _acao_ver_logs(estado)),
            "atualizacao": ("Verificar atualizações", lambda: atualizacao.verificar(estado)),
        }

        if escolha in acoes:
            rotulo, funcao = acoes[escolha]
            interface.limpar_tela()
            _executar_seguro(rotulo, funcao)


def _sair(estado: config.EstadoApp) -> None:
    """Encerra o programa com uma mensagem amigável."""
    interface.linha_em_branco()
    interface.info(
        "Até a próxima! Seus backups e logs ficam guardados em:\n"
        f"  Backups: {config.PASTA_BACKUPS}\n"
        f"  Logs:    {config.PASTA_LOGS}"
    )
    seguranca.registrar("Programa encerrado pelo usuário.", logging.INFO)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    """Função principal. Retorna o código de saída do processo."""
    # Execução silenciosa pela Tarefa Agendada (manutenção automática): roda a
    # limpeza headless e sai, sem abrir a interface.
    if "--tarefa-limpeza" in sys.argv:
        config.garantir_pastas()
        return agendador.executar_limpeza_headless()

    config.garantir_pastas()
    seguranca.configurar_logging()
    seguranca.registrar(f"Iniciando {config.NOME_APP} v{config.VERSAO_APP}.", logging.INFO)

    estado = config.EstadoApp()

    try:
        # Evita o "congelamento por clique" do console clássico (QuickEdit).
        interface.preparar_console_windows()
        interface.limpar_tela()
        interface.tela_boas_vindas()
        _verificar_ambiente(estado)
        _tratar_privilegios(estado)
        _verificar_atualizacao_inicial(estado)
        _menu_principal(estado)
    except KeyboardInterrupt:
        interface.linha_em_branco()
        interface.info("Encerrado pelo usuário (Ctrl+C).")
    except Exception as exc:  # noqa: BLE001 - último recurso
        seguranca.registrar(
            f"Erro fatal não esperado: {exc}\n{traceback.format_exc()}", logging.CRITICAL
        )
        interface.erro(f"Erro inesperado: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
