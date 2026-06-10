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

import hashlib
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

# O .bat atualizador roda numa janela PRÓPRIA e VISÍVEL: o usuário vê o
# progresso ("aguardando o programa fechar...") e, se algo falhar, vê o motivo
# — antes ele rodava invisível e uma falha parecia "não aconteceu nada".
_CREATE_NEW_CONSOLE = 0x00000010


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
                "Nenhum release público encontrado.\n"
                "Causa mais comum: o repositório no GitHub está PRIVADO — a "
                "verificação de atualização usa a API pública, então o dono "
                "precisa torná-lo público (Settings → Change visibility) para "
                "o auto-update funcionar."
            )
        if exc.code == 403:
            return None, (
                "O GitHub limitou as consultas deste endereço temporariamente "
                "(rate limit). Tente novamente em alguns minutos."
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
    sha256 = ""
    for asset in dados.get("assets", []) or []:
        if str(asset.get("name", "")).lower() == config.NOME_EXECUTAVEL.lower():
            url_download = str(asset.get("browser_download_url", ""))
            tamanho = int(asset.get("size", 0) or 0)
            # O GitHub publica o hash do asset ("digest": "sha256:<hex>") —
            # usamos para conferir a integridade do download.
            digest = str(asset.get("digest", "") or "")
            if digest.lower().startswith("sha256:"):
                sha256 = digest.split(":", 1)[1].strip().lower()
            break

    info = {
        "versao": tag.lstrip("vV") or "0",
        "tag": tag,
        "nome": str(dados.get("name", "") or tag),
        "notas": str(dados.get("body", "") or "").strip(),
        "url_pagina": str(dados.get("html_url", "") or config.URL_PAGINA_RELEASES),
        "url_download": url_download,
        "tamanho": tamanho,
        "sha256": sha256,
    }
    return info, ""


# ---------------------------------------------------------------------------
# Download e troca do executável
# ---------------------------------------------------------------------------
def _validar_download(destino: Path, tamanho_esperado: int, sha256_esperado: str) -> tuple[bool, str]:
    """Valida o arquivo baixado: tamanho, assinatura PE ("MZ") e SHA-256.

    Evita trocar o executável por um download truncado, por uma página de erro
    em HTML ou por um arquivo corrompido/adulterado no caminho.
    """
    try:
        if not destino.exists():
            return False, "O arquivo baixado não foi encontrado."
        if tamanho_esperado and destino.stat().st_size != tamanho_esperado:
            return False, "O arquivo baixado ficou incompleto (tamanho diferente do esperado)."
        with destino.open("rb") as arquivo:
            if arquivo.read(2) != b"MZ":
                return False, "O arquivo baixado não é um executável válido do Windows."
            arquivo.seek(0)
            if sha256_esperado:
                resumo = hashlib.sha256()
                while True:
                    pedaco = arquivo.read(1024 * 1024)
                    if not pedaco:
                        break
                    resumo.update(pedaco)
                if resumo.hexdigest().lower() != sha256_esperado.lower():
                    return False, "A verificação de integridade (SHA-256) do download falhou."
    except OSError as exc:
        return False, f"Não consegui validar o download: {exc}"
    return True, "ok"


def _baixar(
    url: str, destino: Path, tamanho_esperado: int = 0, sha256_esperado: str = ""
) -> tuple[bool, str]:
    """Baixa um arquivo exibindo barra de progresso e valida a integridade."""
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

    ok, msg = _validar_download(destino, tamanho_esperado, sha256_esperado)
    if not ok:
        _remover_silencioso(destino)
        return False, msg
    return True, "Download concluído e verificado."


def _remover_silencioso(caminho: Path) -> None:
    """Remove um arquivo ignorando erros (limpeza best-effort)."""
    try:
        caminho.unlink()
    except OSError:
        pass


def _montar_bat(novo_exe: Path, exe_atual: Path) -> str:
    """Monta o conteúdo do ``.bat`` que aplica a atualização.

    Decisões (corrigem falhas observadas em campo):
        * ``ping -n 2 127.0.0.1`` como pausa de ~1s — o comando ``timeout``
          falha quando o ``.bat`` roda sem console interativo, o que fazia o
          laço antigo virar busy-loop.
        * Limite de 60 tentativas (~1 min): se o executável não liberar (ex.:
          antivírus segurando o arquivo), o atualizador DESISTE com uma
          mensagem clara e reabre a versão atual — nunca fica em laço infinito.
        * Mensagens em ASCII puro (sem acentos) para não depender de codepage.
        * ``del "%~f0" & exit`` na mesma linha: o cmd lê a linha inteira antes
          de o arquivo se autoexcluir.
    """
    return (
        "@echo off\r\n"
        f"title Atualizando {config.NOME_APP}\r\n"
        "echo.\r\n"
        f"echo   Atualizando o {config.NOME_APP}... NAO feche esta janela.\r\n"
        "echo   (aguardando o programa fechar para trocar o executavel)\r\n"
        "set tentativas=0\r\n"
        ":mover\r\n"
        "set /a tentativas+=1\r\n"
        "if %tentativas% gtr 60 goto falhou\r\n"
        "ping -n 2 127.0.0.1 >nul\r\n"
        f'move /y "{novo_exe}" "{exe_atual}" >nul 2>&1\r\n'
        "if errorlevel 1 goto mover\r\n"
        "echo   Atualizacao aplicada com sucesso! Abrindo o programa...\r\n"
        f'start "" "{exe_atual}"\r\n'
        'del "%~f0" & exit\r\n'
        ":falhou\r\n"
        "echo.\r\n"
        "echo   NAO consegui trocar o executavel (antivirus segurando o arquivo?).\r\n"
        f"echo   A nova versao ficou salva em: {novo_exe}\r\n"
        "echo   Voce pode substituir manualmente. Vou reabrir a versao atual.\r\n"
        f'start "" "{exe_atual}"\r\n'
        "pause\r\n"
        'del "%~f0" & exit\r\n'
    )


def _aplicar_autoupdate(novo_exe: Path) -> tuple[bool, str]:
    """Agenda a troca do executável atual pelo novo e reinicia o programa.

    Cria um ``.bat`` que espera este processo terminar (tentando mover em laço
    até conseguir, pois o ``.exe`` fica travado enquanto roda), substitui o
    executável, reabre o programa e se autoexclui. O ``.bat`` roda numa janela
    própria e visível, com limite de tentativas e mensagem de erro clara.
    Só faz sentido com o programa empacotado (frozen) no Windows.
    """
    exe_atual = Path(sys.executable).resolve()
    bat = config.PASTA_EXECUCAO / "_atualizar_otimizador.bat"
    try:
        # ASCII estrito: garante que o cmd interprete igual em qualquer codepage.
        bat.write_text(_montar_bat(novo_exe, exe_atual), encoding="ascii")
    except (OSError, UnicodeEncodeError) as exc:
        return False, f"Não consegui preparar o atualizador: {exc}"

    bandeiras = _CREATE_NEW_CONSOLE if sys.platform.startswith("win") else 0
    try:
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            creationflags=bandeiras,
            close_fds=True,
            cwd=str(config.PASTA_EXECUCAO),
        )
    except OSError as exc:
        return False, f"Não consegui iniciar o atualizador: {exc}"
    seguranca.registrar(f"[atualizacao] atualizador iniciado: {bat}", logging.INFO)
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
    ok, msg = _baixar(info["url_download"], destino, info["tamanho"], info.get("sha256", ""))
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
