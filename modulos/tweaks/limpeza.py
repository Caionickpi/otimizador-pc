"""Tweak: limpeza de arquivos temporários.

Remove apenas locais de cache/temporários conhecidos e seguros:
%TEMP%, C:\\Windows\\Temp, cache do Windows Update (SoftwareDistribution\\Download),
Lixeira, cache de miniaturas e relatórios de erro (WER).

NUNCA toca em documentos, fotos, downloads ou área de trabalho do usuário.
Calcula e mostra o espaço a ser liberado ANTES de executar e pede confirmação.
São arquivos descartáveis por natureza, então não há backup (o Windows os
recria conforme necessário) — e por isso também não criamos ponto de
restauração aqui (ele não recuperaria temporários e só atrasaria a operação).

Robustez anti-travamento (após relato de congelamento em campo):
    * O cálculo de tamanho tem ORÇAMENTO DE TEMPO por pasta — em pastas
      gigantes ele para no prazo e mostra "≥ X" em vez de varrer para sempre.
    * As chamadas de Lixeira (consultar/esvaziar) são feitas em thread com
      timeout: um drive lento/desconectado não congela mais o programa.
    * Quando o programa roda como .exe (PyInstaller onefile), a pasta de
      execução dele (sys._MEIPASS, dentro de %TEMP%) é EXCLUÍDA da limpeza —
      antes, o programa apagava os próprios módulos e podia quebrar/travar.
    * Cada fase é registrada no log ([limpeza] fase: ...) para que um eventual
      problema fique visível em logs/otimizador_*.log.
"""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable, Optional

import config
from modulos import interface, seguranca

# Orçamentos de tempo (segundos). Garantem que NENHUMA etapa fique pendurada:
# preferimos um número aproximado ("≥ X") a uma interface congelada.
_PRAZO_CALCULO_PASTA = 8.0     # varredura de tamanho por pasta
_PRAZO_CONSULTA_LIXEIRA = 5.0  # SHQueryRecycleBinW (todos os drives)
_PRAZO_ESVAZIAR_LIXEIRA = 60.0  # SHEmptyRecycleBinW


# ---------------------------------------------------------------------------
# Execução com timeout (blindagem contra chamadas do shell que travam)
# ---------------------------------------------------------------------------
def _executar_com_timeout(funcao: Callable[[], Any], timeout: float) -> tuple[bool, Any]:
    """Roda ``funcao`` numa thread daemon e espera até ``timeout`` segundos.

    Returns:
        ``(terminou, resultado)``. Se estourar o tempo, ``terminou`` é False e
        a thread fica abandonada (daemon) — ela morre junto com o processo e,
        no caso da Lixeira, o Windows continua o trabalho em segundo plano.
    """
    caixa: dict[str, Any] = {}

    def alvo() -> None:
        try:
            caixa["r"] = funcao()
        except Exception as exc:  # noqa: BLE001 - nunca derrubar a thread
            caixa["erro"] = exc

    fio = threading.Thread(target=alvo, daemon=True)
    fio.start()
    fio.join(timeout)
    if fio.is_alive():
        return False, None
    if "erro" in caixa:
        seguranca.registrar(f"[limpeza] chamada falhou: {caixa['erro']}", logging.WARNING)
        return True, None
    return True, caixa.get("r")


# ---------------------------------------------------------------------------
# Lixeira (via API do Shell)
# ---------------------------------------------------------------------------
class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("i64Size", ctypes.c_int64),
        ("i64NumItems", ctypes.c_int64),
    ]


def _tamanho_lixeira_bloqueante() -> int:
    """Consulta o tamanho da Lixeira (pode bloquear — use via timeout)."""
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
    resultado = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))  # type: ignore[attr-defined]
    return int(info.i64Size) if resultado == 0 else 0


def _tamanho_lixeira() -> int:
    """Tamanho total da Lixeira em bytes (0 se indisponível ou demorou demais)."""
    if not sys.platform.startswith("win"):
        return 0
    terminou, tamanho = _executar_com_timeout(
        _tamanho_lixeira_bloqueante, _PRAZO_CONSULTA_LIXEIRA
    )
    if not terminou:
        seguranca.registrar(
            "[limpeza] consulta da Lixeira excedeu o tempo (drive lento?). Seguindo sem ela.",
            logging.WARNING,
        )
        return 0
    return int(tamanho or 0)


def _esvaziar_lixeira_bloqueante() -> bool:
    """Esvazia a Lixeira (pode bloquear — use via timeout)."""
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI = 0x00000002
    SHERB_NOSOUND = 0x00000004
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    resultado = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)  # type: ignore[attr-defined]
    # S_OK (0) = esvaziou; alguns sistemas retornam erro se já estava vazia.
    return resultado == 0


def _esvaziar_lixeira() -> Optional[bool]:
    """Esvazia a Lixeira com timeout.

    Returns:
        ``True`` sucesso, ``False`` falha, ``None`` se excedeu o tempo (o
        Windows pode continuar esvaziando em segundo plano).
    """
    if not sys.platform.startswith("win"):
        return False
    terminou, ok = _executar_com_timeout(
        _esvaziar_lixeira_bloqueante, _PRAZO_ESVAZIAR_LIXEIRA
    )
    if not terminou:
        return None
    return bool(ok)


# ---------------------------------------------------------------------------
# Cálculo e remoção de pastas de cache
# ---------------------------------------------------------------------------
def _pastas_protegidas() -> set[str]:
    """Caminhos que NUNCA podem ser apagados (normalizados p/ comparação).

    Inclui a pasta de extração do próprio executável (PyInstaller onefile fica
    em %TEMP%\\_MEIxxxx): apagá-la removeria módulos ainda não carregados do
    programa em execução, causando erros ou travamento no meio da limpeza.
    """
    protegidas: set[str] = set()
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        protegidas.add(os.path.normcase(os.path.abspath(meipass)))
    return protegidas


def _esta_protegido(caminho: str | Path, protegidas: set[str]) -> bool:
    """Verifica se ``caminho`` é (ou está dentro de) um local protegido."""
    alvo = os.path.normcase(os.path.abspath(str(caminho)))
    for prot in protegidas:
        if alvo == prot or alvo.startswith(prot + os.sep):
            return True
    return False


def _tamanho_pasta(
    caminho: Path,
    prazo: float = _PRAZO_CALCULO_PASTA,
    protegidas: Optional[set[str]] = None,
) -> tuple[int, bool]:
    """Calcula o tamanho do conteúdo de uma pasta com ORÇAMENTO DE TEMPO.

    Returns:
        ``(bytes, completo)``. Se a varredura estourar o prazo (pasta gigante),
        retorna o acumulado até ali com ``completo=False`` — o chamador exibe
        "≥ X" em vez de deixar a interface parada por minutos.
    """
    total = 0
    if not caminho.exists():
        return 0, True
    protegidas = protegidas or set()
    limite = time.monotonic() + max(prazo, 0.1)
    for raiz, dirs, arquivos in os.walk(caminho):
        # Poda subpastas protegidas (ex.: _MEIPASS do próprio .exe).
        if protegidas:
            dirs[:] = [
                d for d in dirs if not _esta_protegido(os.path.join(raiz, d), protegidas)
            ]
        for nome in arquivos:
            try:
                total += os.stat(os.path.join(raiz, nome)).st_size
            except OSError:
                continue
        if time.monotonic() > limite:
            return total, False
    return total, True


def _locais_limpeza() -> list[dict[str, Any]]:
    """Monta a lista de locais de limpeza conhecidos e existentes."""
    locais: list[dict[str, Any]] = []
    protegidas = _pastas_protegidas()

    temp_usuario = os.environ.get("TEMP") or os.environ.get("TMP")
    windir = os.environ.get("WINDIR", r"C:\Windows")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    candidatos: list[tuple[str, Optional[str], str]] = [
        ("Temporários do usuário (%TEMP%)", temp_usuario, "pasta"),
        ("Temporários do Windows", f"{windir}\\Temp", "pasta"),
        ("Cache do Windows Update", f"{windir}\\SoftwareDistribution\\Download", "pasta"),
        ("Cache de miniaturas", f"{localappdata}\\Microsoft\\Windows\\Explorer" if localappdata else None, "miniaturas"),
        ("Relatórios de erro (WER)", f"{localappdata}\\Microsoft\\Windows\\WER" if localappdata else None, "pasta"),
    ]

    for nome, caminho_str, tipo in candidatos:
        if not caminho_str:
            continue
        caminho = Path(caminho_str)
        if not caminho.exists():
            continue
        seguranca.registrar(f"[limpeza] fase: medindo '{nome}' ({caminho})", logging.DEBUG)
        if tipo == "miniaturas":
            tamanho = _tamanho_miniaturas(caminho)
            completo = True
        else:
            tamanho, completo = _tamanho_pasta(caminho, protegidas=protegidas)
        locais.append(
            {
                "nome": nome,
                "caminho": caminho,
                "tipo": tipo,
                "tamanho": tamanho,
                "completo": completo,
            }
        )

    # Lixeira (tratada via API com timeout, não por caminho).
    seguranca.registrar("[limpeza] fase: consultando a Lixeira", logging.DEBUG)
    locais.append(
        {
            "nome": "Lixeira",
            "caminho": None,
            "tipo": "lixeira",
            "tamanho": _tamanho_lixeira(),
            "completo": True,
        }
    )
    return locais


def _tamanho_miniaturas(caminho: Path) -> int:
    """Soma o tamanho dos caches de miniaturas/ícones (arquivos conhecidos)."""
    total = 0
    for padrao in ("thumbcache_*.db", "iconcache_*.db"):
        for arq in caminho.glob(padrao):
            try:
                if arq.is_file():
                    total += arq.stat().st_size
            except OSError:
                continue
    return total


def _limpar_conteudo_pasta(
    caminho: Path,
    apenas_padrao: Optional[list[str]] = None,
    protegidas: Optional[set[str]] = None,
) -> None:
    """Apaga o conteúdo de uma pasta (mantendo a própria pasta).

    Itens protegidos (ex.: a pasta _MEIPASS do próprio .exe) e itens em uso
    são pulados. ``shutil.rmtree`` cuida das subpastas — inclusive junções,
    que ele remove sem segui-las (sem risco de laço infinito).
    """
    if not caminho.exists():
        return
    protegidas = protegidas or set()

    if apenas_padrao:
        for padrao in apenas_padrao:
            for arquivo in caminho.glob(padrao):
                try:
                    if arquivo.is_file():
                        arquivo.unlink()
                except OSError:
                    continue  # arquivo em uso: ignora
        return

    for item in caminho.iterdir():
        if _esta_protegido(item, protegidas):
            continue
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
        except OSError:
            # Arquivo/pasta em uso (ex.: travado pelo Windows). Ignora.
            continue


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de limpeza de arquivos temporários."""
    interface.cabecalho(
        "Limpeza de arquivos temporários",
        "Remove apenas cache/temporários conhecidos. Não toca em arquivos pessoais.",
    )

    seguranca.registrar("[limpeza] fase: cálculo de espaço iniciado", logging.INFO)
    with interface.spinner("Calculando o espaço que pode ser liberado") as progresso:
        tarefa = progresso.add_task("Calculando", total=None)
        locais = _locais_limpeza()
        progresso.update(tarefa, completed=1)
    seguranca.registrar("[limpeza] fase: cálculo de espaço concluído", logging.INFO)

    total = sum(item["tamanho"] for item in locais)
    houve_parcial = any(not item["completo"] for item in locais)

    tabela = interface.nova_tabela("Locais que serão limpos", ["Local", "Espaço a liberar"])
    for item in locais:
        valor = interface.formatar_bytes(item["tamanho"])
        if not item["completo"]:
            valor = f"≥ {valor}"
        tabela.add_row(item["nome"], valor)
    prefixo_total = "≥ " if houve_parcial else ""
    tabela.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold {config.COR_OK}]{prefixo_total}{interface.formatar_bytes(total)}[/]",
    )
    interface.imprimir_tabela(tabela)
    if houve_parcial:
        interface.texto(
            "≥ = pasta muito grande; parei de medir no prazo para não te deixar "
            "esperando. A limpeza remove tudo normalmente.",
            config.COR_DIM,
        )

    if total == 0:
        interface.info("Nada para limpar — já está tudo enxuto por aqui!")
        return

    if estado.simulacao:
        interface.info(
            "MODO SIMULAÇÃO: nada foi apagado.\n"
            f"Seriam liberados aproximadamente {prefixo_total}{interface.formatar_bytes(total)}."
        )
        return

    interface.aviso(
        "Estes são arquivos temporários e de cache, seguros para remover. "
        "Como são descartáveis, não há backup nem ponto de restauração — o "
        "Windows os recria quando precisar. Programas abertos podem manter "
        "alguns arquivos travados; esses serão ignorados."
    )
    if not interface.confirmar(
        f"Liberar {prefixo_total}{interface.formatar_bytes(total)} agora?", padrao=False
    ):
        interface.info("Limpeza cancelada. Nada foi alterado.")
        return

    protegidas = _pastas_protegidas()
    liberado_total = 0
    lixeira_em_andamento = False
    with interface.barra_progresso() as progresso:
        tarefa = progresso.add_task("Limpando", total=len(locais))
        for item in locais:
            progresso.update(tarefa, description=f"Limpando: {item['nome']}")
            seguranca.registrar(f"[limpeza] fase: limpando '{item['nome']}'", logging.INFO)
            liberado, pendente = _executar_limpeza_item(item, protegidas)
            liberado_total += liberado
            lixeira_em_andamento = lixeira_em_andamento or pendente
            progresso.advance(tarefa)

    seguranca.registrar_acao(
        "limpeza",
        "Limpeza de temporários concluída",
        True,
        f"liberado ~{interface.formatar_bytes(liberado_total)}",
    )
    extra = (
        "\nA Lixeira era grande e o Windows continua esvaziando-a em segundo plano."
        if lixeira_em_andamento
        else ""
    )
    interface.sucesso(
        f"Limpeza concluída! Espaço liberado: ~{interface.formatar_bytes(liberado_total)}.{extra}"
    )


def _executar_limpeza_item(item: dict[str, Any], protegidas: set[str]) -> tuple[int, bool]:
    """Executa a limpeza de um item.

    Returns:
        ``(bytes_liberados, lixeira_pendente)`` — o segundo valor indica que a
        Lixeira excedeu o tempo e segue esvaziando em segundo plano.
    """
    tipo = item["tipo"]
    try:
        if tipo == "lixeira":
            resultado = _esvaziar_lixeira()
            if resultado is None:  # excedeu o tempo; Windows continua sozinho
                return 0, True
            return (item.get("tamanho", 0), False) if resultado else (0, False)

        if tipo == "miniaturas":
            antes = item.get("tamanho", 0)
            _limpar_conteudo_pasta(item["caminho"], ["thumbcache_*.db", "iconcache_*.db"])
            depois = _tamanho_miniaturas(item["caminho"])
            return max(antes - depois, 0), False

        antes = item.get("tamanho", 0)
        _limpar_conteudo_pasta(item["caminho"], protegidas=protegidas)
        depois, _completo = _tamanho_pasta(item["caminho"], protegidas=protegidas)
        return max(antes - depois, 0), False
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar_acao("limpeza", f"Falha em {item['nome']}", False, str(exc))
        return 0, False
