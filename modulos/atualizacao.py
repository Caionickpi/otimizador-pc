"""Atualização automática via GitHub Releases.

Consulta a API PÚBLICA de releases do GitHub, compara com a versão atual e,
quando o programa está empacotado como ``.exe`` (PyInstaller), pode baixar a
nova versão e se atualizar sozinho — fechando, trocando o executável e
reabrindo por meio de um pequeno script ``.bat`` auxiliar.

Princípios do projeto mantidos:
    * Nada acontece sem confirmação do usuário (respeita o modo simulação).
    * Toda falha é tratada: sem internet, sem release, repositório privado
      (API 404) ou antivírus nunca derrubam o programa — no máximo avisamos e
      oferecemos abrir a página de download manualmente.
    * Sem dependências novas: usa apenas a biblioteca padrão (``urllib``).

Observação: o download automático exige que o repositório/releases sejam
PÚBLICOS. Em repositório privado, a API pública responde 404 e caímos no aviso.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

import config
from modulos import interface, seguranca

# Tempos de espera (segundos): curto na checagem automática do início, um pouco
# maior na verificação manual pedida pelo usuário.
_TIMEOUT_INICIO = 5
_TIMEOUT_MANUAL = 8
_USER_AGENT = f"{config.NOME_APP}/{config.VERSAO_APP} (auto-update)"

# Flags do Windows para desacoplar o processo do .bat atualizador.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200


# ---------------------------------------------------------------------------
# Comparação de versões
# ---------------------------------------------------------------------------
def _versao_tupla(texto: str) -> tuple[int, ...]:
    """Converte 'v1.4.0' / '1.4' / '1.10.2-rc1' em uma tupla comparável.

    Mantém apenas a parte numérica de cada segmento e para no primeiro
    caractere não numérico. Ex.: '1.4.0' -> (1, 4, 0); 'v1.10.2-rc1' -> (1, 10, 2).
    """
    limpo = (texto or "").strip().lstrip("vV")
    partes: list[int] = []
    for segmento in limpo.split("."):
        digitos = ""
        for caractere in segmento:
            if caractere.isdigit():
                digitos += caractere
            else:
                break
        if not digitos:
            break
        partes.append(int(digitos))
    return tuple(partes) or (0,)


def _e_mais_nova(remota: str, atual: str) -> bool:
    """Retorna ``True`` se a versão remota for estritamente maior que a atual."""
    return _versao_tupla(remota) > _versao_tupla(atual)


# ---------------------------------------------------------------------------
# Consulta ao GitHub
# ---------------------------------------------------------------------------
def obter_release_recente(timeout: int = _TIMEOUT_MANUAL) -> tuple[Optional[dict[str, Any]], str]:
    """Busca o release mais recente na API pública do GitHub.

    Returns:
        ``(info, erro)``. Em sucesso, ``info`` é um dicionário com as chaves
        ``versao``, ``tag``, ``nome``, ``notas``, ``url_pagina``,
        ``url_download`` e ``tamanho``; ``erro`` é "". Em falha, ``info`` é
        ``None`` e ``erro`` descreve o problema (sem internet, 404 etc.).
    """
    requisicao = urlrequest.Request(
        config.URL_API_RELEASE_RECENTE,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlrequest.urlopen(requisicao, timeout=timeout) as resposta:
            dados = json.loads(resposta.read().decode("utf-8", errors="replace"))
    except urlerror.HTTPError as exc:
        if exc.code == 404:
            return None, (
                "Nenhum release público encontrado (o repositório pode estar "
                "privado ou ainda não há versões publicadas)."
            )
        return None, f"Falha ao consultar atualizações (HTTP {exc.code})."
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        return None, f"Sem conexão para verificar atualizações ({exc})."
    except (ValueError, json.JSONDecodeError):
        return None, "Resposta inesperada do servidor de atualizações."

    tag = str(dados.get("tag_name", "")).strip()
    # Localiza o asset do executável pelo nome (robusto a maiúsc./minúsc.).
    url_download = ""
    tamanho = 0
    for asset in dados.get("assets", []) or []:
        if str(asset.get("name", "")).lower() == config.NOME_EXECUTAVEL.lower():
            url_download = str(asset.get("browser_download_url", ""))
            tamanho = int(asset.get("size", 0) or 0)
            break

    info = {
        "versao": tag.lstrip("vV") or "0",
        "tag": tag,
        "nome": str(dados.get("name", "") or tag),
        "notas": str(dados.get("body", "") or "").strip(),
        "url_pagina": str(dados.get("html_url", "") or config.URL_PAGINA_RELEASES),
        "url_download": url_download,
        "tamanho": tamanho,
    }
    return info, ""


# ---------------------------------------------------------------------------
# Download e troca do executável
# ---------------------------------------------------------------------------
def _baixar(url: str, destino: Path, tamanho_esperado: int = 0) -> tuple[bool, str]:
    """Baixa um arquivo exibindo barra de progresso. Retorna ``(sucesso, msg)``."""
    requisicao = urlrequest.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlrequest.urlopen(requisicao, timeout=30) as resposta:
            total = int(resposta.headers.get("Content-Length") or tamanho_esperado or 0)
            baixado = 0
            with interface.barra_progresso() as progresso:
                tarefa = progresso.add_task("Baixando atualização", total=total or None)
                with destino.open("wb") as arquivo:
                    while True:
                        pedaco = resposta.read(256 * 1024)
                        if not pedaco:
                            break
                        arquivo.write(pedaco)
                        baixado += len(pedaco)
                        progresso.update(tarefa, completed=baixado)
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        _remover_silencioso(destino)
        return False, f"Falha no download: {exc}"

    # Confere o tamanho anunciado pelo release (proteção contra download truncado).
    if tamanho_esperado and destino.exists() and destino.stat().st_size != tamanho_esperado:
        _remover_silencioso(destino)
        return False, "O arquivo baixado ficou incompleto (tamanho diferente do esperado)."
    return True, "Download concluído."


def _remover_silencioso(caminho: Path) -> None:
    """Remove um arquivo ignorando erros (limpeza best-effort)."""
    try:
        caminho.unlink()
    except OSError:
        pass


def _aplicar_autoupdate(novo_exe: Path) -> tuple[bool, str]:
    """Agenda a troca do executável atual pelo novo e reinicia o programa.

    Cria um ``.bat`` que espera este processo terminar (tentando mover em laço
    até conseguir, pois o ``.exe`` fica travado enquanto roda), substitui o
    executável, reabre o programa e se autoexclui. Só faz sentido com o
    programa empacotado (frozen) no Windows.
    """
    exe_atual = Path(sys.executable).resolve()
    bat = config.PASTA_EXECUCAO / "_atualizar_otimizador.bat"
    # "%~f0" dentro do .bat = o próprio arquivo (usado para autoexclusão).
    conteudo = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        f"title Atualizando {config.NOME_APP}\r\n"
        "echo.\r\n"
        f"echo   Atualizando {config.NOME_APP}... aguarde alguns segundos.\r\n"
        ":mover\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        f'move /y "{novo_exe}" "{exe_atual}" >nul 2>&1\r\n'
        "if errorlevel 1 goto mover\r\n"
        f'start "" "{exe_atual}"\r\n'
        'del "%~f0"\r\n'
    )
    try:
        bat.write_text(conteudo, encoding="utf-8")
    except OSError as exc:
        return False, f"Não consegui preparar o atualizador: {exc}"

    bandeiras = (_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP) if sys.platform.startswith("win") else 0
    try:
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            creationflags=bandeiras,
            close_fds=True,
            cwd=str(config.PASTA_EXECUCAO),
        )
    except OSError as exc:
        return False, f"Não consegui iniciar o atualizador: {exc}"
    return True, "ok"


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def _abrir_pagina(url: str) -> None:
    """Abre a página de download no navegador; se falhar, imprime o link."""
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 - abrir navegador nunca deve quebrar o fluxo
        interface.texto(url, config.COR_INFO)


def verificar(estado: config.EstadoApp, *, no_inicio: bool = False) -> None:
    """Verifica se há atualização e conduz o fluxo (consulta + auto-update).

    Args:
        estado: estado da aplicação (usado para respeitar o modo simulação).
        no_inicio: quando ``True``, é a checagem automática silenciosa do início
            (timeout curto; não incomoda quem está offline ou já atualizado).
    """
    if not no_inicio:
        interface.cabecalho("🔄 Verificar atualizações", f"Versão atual: v{config.VERSAO_APP}")

    timeout = _TIMEOUT_INICIO if no_inicio else _TIMEOUT_MANUAL
    if no_inicio:
        info, erro = obter_release_recente(timeout)
    else:
        with interface.spinner("Consultando o GitHub") as progresso:
            tarefa = progresso.add_task("Consultando", total=None)
            info, erro = obter_release_recente(timeout)
            progresso.update(tarefa, completed=1)

    if info is None:
        # Sem release/sem internet: silencioso no início, informativo no manual.
        if no_inicio:
            seguranca.registrar(f"[atualizacao] checagem no início: {erro}", logging.INFO)
            return
        interface.aviso(f"{erro}\n\nVeja as versões disponíveis em:\n{config.URL_PAGINA_RELEASES}")
        return

    if not _e_mais_nova(info["versao"], config.VERSAO_APP):
        if not no_inicio:
            interface.sucesso(f"Você já está na versão mais recente (v{config.VERSAO_APP}). 🎉")
        return

    # ---- Há versão nova ----
    notas = info["notas"]
    if len(notas) > 600:
        notas = notas[:600].rstrip() + "..."
    interface.info(
        f"Nova versão disponível: [bold]v{info['versao']}[/bold] "
        f"(você tem v{config.VERSAO_APP})."
        + (f"\n\n[dim]Novidades:[/dim]\n{interface.escapar(notas)}" if notas else "")
    )

    empacotado = bool(getattr(sys, "frozen", False))
    pode_auto = empacotado and bool(info["url_download"]) and sys.platform.startswith("win")

    if not pode_auto:
        motivo = (
            "rodando a partir do código-fonte, não do .exe" if not empacotado
            else "disponível apenas no Windows" if not sys.platform.startswith("win")
            else "o release não traz o OtimizadorPC.exe"
        )
        interface.aviso(
            f"Atualização automática indisponível ({motivo}).\n"
            "Posso abrir a página de download para você baixar manualmente."
        )
        if interface.confirmar("Abrir a página de download agora?", padrao=True):
            _abrir_pagina(info["url_pagina"])
        return

    tamanho = interface.formatar_bytes(info["tamanho"]) if info["tamanho"] else "?"
    interface.aviso(
        "Vou baixar a nova versão e me atualizar sozinho: o programa vai FECHAR, "
        f"trocar o executável (~{tamanho}) e reabrir automaticamente.\n"
        "Salve o que precisar antes. Na 1ª vez, o antivírus pode pedir confirmação."
    )
    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: eu baixaria e aplicaria a atualização. Nada foi alterado.")
        return
    if not interface.confirmar(f"Baixar e instalar a v{info['versao']} agora?", padrao=True):
        interface.info("Atualização cancelada. Você continua na versão atual.")
        return

    destino = config.PASTA_EXECUCAO / (config.NOME_EXECUTAVEL + ".novo")
    ok, msg = _baixar(info["url_download"], destino, info["tamanho"])
    if not ok:
        interface.erro(f"{msg}\nVou abrir a página para download manual.")
        _abrir_pagina(info["url_pagina"])
        return
    seguranca.registrar_acao("atualizacao", f"Download da v{info['versao']}", True, str(destino))

    ok, msg = _aplicar_autoupdate(destino)
    if not ok:
        interface.erro(f"{msg}\nVou abrir a página para download manual.")
        _remover_silencioso(destino)
        _abrir_pagina(info["url_pagina"])
        return

    interface.sucesso(
        "Atualização baixada! O programa vai fechar agora e reabrir já atualizado.\n"
        "Se ele não reabrir sozinho, é só abrir de novo o OtimizadorPC.exe."
    )
    seguranca.registrar(f"Reiniciando para aplicar atualização v{info['versao']}.", logging.INFO)
    interface.pausar("Pressione Enter para fechar e atualizar...")
    # Encerra imediatamente para liberar o lock do .exe — o .bat fará a troca.
    os._exit(0)
