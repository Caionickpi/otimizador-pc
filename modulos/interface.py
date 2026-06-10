"""Componentes reutilizáveis da interface de terminal (TUI).

Centraliza o uso do ``rich`` (tabelas, painéis, cores, barras de progresso) e
do ``questionary`` (menus e confirmações) para que todos os módulos tenham um
visual e um comportamento consistentes.

Padrão de cores (definido em :mod:`config`):
    verde   -> seguro / concluído
    amarelo -> atenção
    vermelho-> cuidado / crítico
"""

from __future__ import annotations

import os
import sys

# Profundidade de cor MÁXIMA no menu (prompt_toolkit). Sem isto, o console do
# Windows costuma cair para 16 cores e a interface fica "lavada". Precisa ser
# definido ANTES de o prompt_toolkit detectar a saída — por isso fica no topo.
os.environ.setdefault("PROMPT_TOOLKIT_COLOR_DEPTH", "DEPTH_24_BIT")

from typing import Any, Iterable, Optional, Sequence

import questionary
from questionary import Separator, Style
from rich import box
from rich.align import Align
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

import config

# Console único compartilhado. No Windows, forçamos cor de 24 bits (ANSI/VT) em
# vez do caminho "legacy" de 16 cores — é o que faz as cores aparecerem vivas
# em vez de "apagadas". O rich aproxima sozinho onde houver menos cores.
if sys.platform.startswith("win"):
    console: Console = Console(color_system="truecolor", legacy_windows=False)
else:
    console = Console()


def preparar_console_windows() -> None:
    """Desativa o modo QuickEdit do console (melhor esforço; só no Windows).

    No console clássico do Windows, QUALQUER clique dentro da janela ativa o
    modo de seleção (QuickEdit) e CONGELA o programa inteiro até o usuário
    apertar Esc/Enter — parece travamento e já causou relato de "freeze" em
    campo. Desligamos o QuickEdit logo no início; o prompt_toolkit preserva
    esse modo entre os menus. Qualquer falha aqui é ignorada (não é crítico).
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        STD_INPUT_HANDLE = -10
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080
        alca = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        modo = ctypes.c_uint32()
        if kernel32.GetConsoleMode(alca, ctypes.byref(modo)):
            novo = (modo.value | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE
            kernel32.SetConsoleMode(alca, novo)
    except Exception:  # noqa: BLE001 - proteção extra nunca pode quebrar a abertura
        pass

# Tema do menu (questionary/prompt_toolkit). IMPORTANTE: o questionary pinta
# TODAS as linhas não selecionadas com a classe "text" e a linha atual com
# "highlighted" — então damos cor às duas para o menu nunca ficar "morto".
# As categorias (separadores) usam "separator".
_ESTILO_QUESTIONARY = Style(
    [
        ("qmark", "fg:#58a6ff bold"),                   # símbolo da pergunta
        ("question", "fg:#ffffff bold"),                # texto da pergunta
        ("answer", "fg:#39d0d8 bold"),                  # resposta escolhida
        ("pointer", "fg:#58a6ff bold"),                 # seta ▶ da linha atual
        ("highlighted", "fg:#ffffff bg:#1f6feb bold"),  # barra de seleção (viva)
        ("selected", "fg:#3fb950 bold"),                # itens marcados (checkbox)
        ("separator", "fg:#d29922 bold"),               # rótulos de categoria
        ("text", "fg:#c9d1d9"),                         # TODAS as demais linhas
        ("instruction", "fg:#6e7681 italic"),           # dica "(use as setas...)"
        ("disabled", "fg:#6e7681 italic"),
    ]
)


# ---------------------------------------------------------------------------
# Utilidades de formatação
# ---------------------------------------------------------------------------
def formatar_bytes(quantidade: float) -> str:
    """Formata uma quantidade de bytes em uma string legível (KB, MB, GB...)."""
    try:
        valor = float(quantidade)
    except (TypeError, ValueError):
        return "-"
    if valor < 0:
        return "-"
    unidades = ["B", "KB", "MB", "GB", "TB", "PB"]
    indice = 0
    while valor >= 1024 and indice < len(unidades) - 1:
        valor /= 1024.0
        indice += 1
    if indice == 0:
        return f"{int(valor)} {unidades[indice]}"
    return f"{valor:.2f} {unidades[indice]}"


def formatar_tempo(segundos: float) -> str:
    """Converte uma duração em segundos para algo como '3d 04h 12m'."""
    try:
        total = int(segundos)
    except (TypeError, ValueError):
        return "-"
    if total < 0:
        return "-"
    dias, resto = divmod(total, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, _ = divmod(resto, 60)
    partes: list[str] = []
    if dias:
        partes.append(f"{dias}d")
    if horas or dias:
        partes.append(f"{horas:02d}h")
    partes.append(f"{minutos:02d}m")
    return " ".join(partes)


# ---------------------------------------------------------------------------
# Telas e mensagens
# ---------------------------------------------------------------------------
def escapar(valor: object) -> str:
    """Escapa colchetes para que dados externos não sejam lidos como markup.

    Use ao colocar texto vindo do sistema (caminhos, comandos, nomes do
    registro/WMI) em tabelas ou painéis, evitando erros de markup do rich.
    """
    return escape(str(valor))


def _render(mensagem: str, base: str = "") -> Text:
    """Converte uma string em ``Text`` interpretando markup com segurança.

    Permite ênfases intencionais (ex.: ``[bold]``), mas se o conteúdo tiver
    colchetes inválidos, cai para texto literal em vez de lançar erro.
    """
    try:
        return Text.from_markup(mensagem, style=base)
    except Exception:  # noqa: BLE001 - markup malformado nunca deve quebrar a TUI
        return Text(mensagem, style=base)


def limpar_tela() -> None:
    """Limpa o terminal de forma compatível com Windows e outros sistemas."""
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        # Se não der para limpar, apenas segue (não é crítico).
        pass


def tela_boas_vindas() -> None:
    """Exibe a tela inicial com o nome do programa e o aviso de segurança."""
    titulo = Text(justify="center")
    titulo.append("⚙  ", style=config.COR_ACENTO)
    titulo.append(config.NOME_APP, style=config.COR_DESTAQUE)
    titulo.append(f"   v{config.VERSAO_APP}", style=config.COR_DIM)

    corpo = Text(justify="center")
    corpo.append("\n")
    corpo.append(f"{config.DESCRICAO_APP}\n\n", style=config.COR_INFO)
    corpo.append("🛡  ", style=config.COR_OK)
    corpo.append("Sempre faz backup e pede confirmação — ", style=config.COR_OK)
    corpo.append("nada muda sem você aprovar.\n", style=config.COR_DESTAQUE)
    corpo.append("Tudo é reversível em ", style=config.COR_NEUTRA)
    corpo.append("“Desfazer última alteração”.", style=config.COR_ACENTO)

    console.print(
        Panel(
            Align.center(Text.assemble(titulo, "\n", corpo)),
            border_style=config.COR_ACENTO,
            box=box.HEAVY,
            padding=(1, 6),
        )
    )

    # Dica de emojis coloridos: o console clássico (conhost) os mostra em P&B; o
    # Windows Terminal mostra coloridos. Só sugerimos quando faz sentido.
    if sys.platform.startswith("win") and not os.environ.get("WT_SESSION"):
        console.print(
            Text(
                "  dica: abra no Windows Terminal para ver os emojis coloridos.",
                style=f"italic {config.COR_DIM}",
            )
        )


def cabecalho(titulo: str, subtitulo: Optional[str] = None) -> None:
    """Imprime um cabeçalho de seção destacado."""
    texto = _render(titulo, config.COR_DESTAQUE)
    if subtitulo:
        texto.append("\n")
        texto.append_text(_render(subtitulo, config.COR_DIM))
    console.print(
        Panel(texto, border_style=config.COR_ACENTO, box=box.HEAVY, padding=(0, 2), expand=True)
    )


def _painel(mensagem: str, titulo: str, cor: str) -> None:
    console.print(
        Panel(
            _render(mensagem, cor),
            title=titulo,
            border_style=cor,
            title_align="left",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def sucesso(mensagem: str) -> None:
    """Mensagem de sucesso (verde)."""
    _painel(mensagem, "✔ Concluído", config.COR_OK)


def aviso(mensagem: str) -> None:
    """Mensagem de atenção (amarelo)."""
    _painel(mensagem, "⚠ Atenção", config.COR_AVISO)


def erro(mensagem: str) -> None:
    """Mensagem de erro (vermelho)."""
    _painel(mensagem, "✖ Erro", config.COR_ERRO)


def info(mensagem: str) -> None:
    """Mensagem informativa (ciano)."""
    _painel(mensagem, "ℹ Informação", config.COR_INFO)


def texto(mensagem: str, estilo: str = config.COR_NEUTRA) -> None:
    """Imprime uma linha simples de texto com um estilo opcional."""
    console.print(Text(mensagem, style=estilo))


def linha_em_branco() -> None:
    """Imprime uma linha em branco (espaçamento)."""
    console.print()


# ---------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------
def nova_tabela(titulo: Optional[str] = None, colunas: Optional[Sequence[str]] = None) -> Table:
    """Cria uma tabela do rich já estilizada com o nosso padrão."""
    tabela = Table(
        title=titulo,
        title_style=config.COR_TITULO,
        title_justify="left",
        header_style=config.COR_DESTAQUE,
        border_style=config.COR_INFO,
        box=box.ROUNDED,
        expand=False,
    )
    for coluna in colunas or []:
        tabela.add_column(coluna)
    return tabela


def imprimir_tabela(tabela: Table) -> None:
    """Imprime uma tabela já montada."""
    console.print(tabela)


def tabela_chave_valor(titulo: str, itens: Iterable[tuple[str, str]]) -> None:
    """Atalho para exibir uma tabela de duas colunas (Propriedade/Valor)."""
    tabela = Table(
        title=titulo,
        title_style=config.COR_TITULO,
        title_justify="left",
        show_header=False,
        box=box.ROUNDED,
        border_style=config.COR_INFO,
        expand=False,
    )
    tabela.add_column("Propriedade", style=config.COR_INFO, no_wrap=True)
    tabela.add_column("Valor", style=config.COR_NEUTRA)
    for chave, valor in itens:
        tabela.add_row(str(chave), str(valor))
    console.print(tabela)


# ---------------------------------------------------------------------------
# Barras de progresso
# ---------------------------------------------------------------------------
def barra_progresso() -> Progress:
    """Cria uma barra de progresso para operações demoradas (uso com 'with')."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


def spinner(descricao: str) -> Progress:
    """Cria um spinner simples (sem total conhecido) para tarefas indefinidas."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


# ---------------------------------------------------------------------------
# Interação (menus e confirmações)
# ---------------------------------------------------------------------------
def separador(texto: str = "") -> Separator:
    """Cria um separador visual para agrupar itens dentro de um menu.

    Itens ``Separator`` não são selecionáveis; servem só para organizar
    visualmente as opções (ex.: agrupar 'Ajustes' e 'Ferramentas').
    """
    return Separator(f"─── {texto} ───" if texto else "───────────")


def menu_selecao(titulo: str, opcoes: Sequence[Any]) -> Optional[object]:
    """Exibe um menu de seleção única e retorna o valor escolhido.

    Args:
        titulo: pergunta/título do menu.
        opcoes: lista de pares ``(rótulo_exibido, valor_retornado)``. Também
            aceita objetos ``Separator`` (via :func:`separador`) para agrupar
            visualmente as opções.

    Returns:
        O valor associado à opção escolhida, ou ``None`` se o usuário
        cancelar (Ctrl+C / Esc).
    """
    escolhas: list[Any] = []
    for opcao in opcoes:
        if isinstance(opcao, Separator):
            escolhas.append(opcao)
            continue
        rotulo, valor = opcao
        escolhas.append(questionary.Choice(title=rotulo, value=valor))
    try:
        resposta = questionary.select(
            titulo,
            choices=escolhas,
            style=_ESTILO_QUESTIONARY,
            qmark="»",
            pointer="▶",
            instruction="(use as setas, Enter para confirmar)",
        ).ask()
    except (KeyboardInterrupt, EOFError):
        return None
    return resposta


def menu_multiplo(titulo: str, opcoes: Sequence[tuple[str, object]]) -> list[object]:
    """Exibe um menu de seleção múltipla (checkbox) e retorna a lista escolhida.

    Returns:
        Lista de valores marcados (pode ser vazia). Retorna lista vazia se o
        usuário cancelar.
    """
    escolhas = [questionary.Choice(title=rotulo, value=valor) for rotulo, valor in opcoes]
    try:
        resposta = questionary.checkbox(
            titulo,
            choices=escolhas,
            style=_ESTILO_QUESTIONARY,
            qmark="»",
            pointer="▶",
            instruction="(Espaço marca/desmarca, Enter confirma)",
        ).ask()
    except (KeyboardInterrupt, EOFError):
        return []
    return resposta or []


def confirmar(pergunta: str, padrao: bool = False) -> bool:
    """Pede uma confirmação sim/não. Retorna ``False`` se cancelado."""
    try:
        resposta = questionary.confirm(
            pergunta,
            default=padrao,
            style=_ESTILO_QUESTIONARY,
            qmark="?",
            auto_enter=False,
        ).ask()
    except (KeyboardInterrupt, EOFError):
        return False
    return bool(resposta)


def pedir_texto(pergunta: str, padrao: str = "") -> str:
    """Pede uma entrada de texto livre. Retorna string vazia se cancelado."""
    try:
        resposta = questionary.text(
            pergunta, default=padrao, style=_ESTILO_QUESTIONARY, qmark="✏"
        ).ask()
    except (KeyboardInterrupt, EOFError):
        return ""
    return (resposta or "").strip()


def pausar(mensagem: str = "Pressione Enter para continuar...") -> None:
    """Pausa a execução até o usuário pressionar Enter."""
    try:
        console.print(Text(f"\n{mensagem}", style="dim"), end="")
        input()
    except (KeyboardInterrupt, EOFError):
        # Apenas segue adiante; não é um ponto crítico.
        pass
