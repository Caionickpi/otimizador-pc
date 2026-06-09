"""Mecanismos de segurança — a parte mais importante do programa.

Responsabilidades:
    * Logging completo de todas as ações (sucesso/erro).
    * Criação de ponto de restauração do sistema antes de qualquer alteração.
    * Backup de chaves do registro (.reg) antes de editá-las.
    * Execução tratada de comandos do sistema.
    * Pilha de "desfazer" (rollback) persistida em disco.

Princípios:
    * Abordagem por whitelist: só tocamos no que é explicitamente conhecido.
    * Nada irreversível sem confirmação e backup prévio.
    * Uma falha aqui nunca pode derrubar o programa: tudo é tratado.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import config
from modulos import interface

# Flag para evitar abrir janelas de console a cada subprocesso (só no Windows).
_SEM_JANELA = 0x08000000 if sys.platform.startswith("win") else 0  # CREATE_NO_WINDOW

_logger: Optional[logging.Logger] = None


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def configurar_logging() -> logging.Logger:
    """Configura e retorna o logger principal (arquivo + memória).

    Cada execução grava em ``logs/otimizador_AAAA-MM-DD.log``. Se a pasta de
    logs não puder ser criada, cai para um logger só de console, sem quebrar.
    """
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("otimizador_pc")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    formato = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config.garantir_pastas()
    try:
        nome_arquivo = config.PASTA_LOGS / f"otimizador_{datetime.now():%Y-%m-%d}.log"
        manipulador_arquivo = logging.FileHandler(nome_arquivo, encoding="utf-8")
        manipulador_arquivo.setFormatter(formato)
        manipulador_arquivo.setLevel(logging.DEBUG)
        logger.addHandler(manipulador_arquivo)
    except OSError:
        # Sem permissão de escrita: seguimos só com log em memória/console.
        pass

    _logger = logger
    return logger


def obter_logger() -> logging.Logger:
    """Retorna o logger já configurado (configurando-o se necessário)."""
    return _logger or configurar_logging()


def registrar(mensagem: str, nivel: int = logging.INFO) -> None:
    """Registra uma mensagem no log com o nível indicado."""
    obter_logger().log(nivel, mensagem)


def registrar_acao(modulo: str, acao: str, sucesso: bool, detalhe: str = "") -> None:
    """Registra uma ação modificadora de forma padronizada.

    Args:
        modulo: nome do tweak/categoria (ex.: 'limpeza').
        acao: descrição curta do que foi feito.
        sucesso: se a operação foi bem-sucedida.
        detalhe: informações extras (caminhos, valores, erro).
    """
    estado = "SUCESSO" if sucesso else "ERRO"
    nivel = logging.INFO if sucesso else logging.ERROR
    msg = f"[{modulo}] {acao} -> {estado}"
    if detalhe:
        msg += f" | {detalhe}"
    registrar(msg, nivel)


# ---------------------------------------------------------------------------
# Execução de comandos do sistema
# ---------------------------------------------------------------------------
def _codepage_oem() -> Optional[str]:
    """Retorna o code page OEM do console no Windows (ex.: 'cp850'), se houver.

    As ferramentas de console (powercfg, sc, ipconfig...) escrevem nesse code
    page — usá-lo primeiro evita acentos trocados (ex.: nomes de planos de
    energia). Fora do Windows, retorna ``None``.
    """
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes

        return f"cp{int(ctypes.windll.kernel32.GetOEMCP())}"  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return None


# Ordem de tentativa: o code page real do console primeiro (Windows), depois
# UTF-8 e os ANSI/OEM comuns. ``dict.fromkeys`` remove duplicatas mantendo a
# ordem (caso o OEM já seja um dos demais).
_CODIFICACOES_SAIDA: tuple[str, ...] = tuple(
    dict.fromkeys(
        cp for cp in (_codepage_oem(), "utf-8", "cp1252", "cp850", "latin-1") if cp
    )
)


def _decodificar(dados: bytes) -> str:
    """Decodifica a saída de comandos tentando os code pages do Windows em ordem.

    Ferramentas de console do Windows costumam usar o code page OEM (ex.: cp850
    em pt-BR), não UTF-8. Tentamos em cascata para que textos acentuados
    apareçam corretos.
    """
    if not dados:
        return ""
    for codificacao in _CODIFICACOES_SAIDA:
        try:
            return dados.decode(codificacao)
        except (UnicodeDecodeError, LookupError):
            continue
    return dados.decode("utf-8", errors="replace")


def executar_comando(
    comando: list[str] | str,
    *,
    shell: bool = False,
    timeout: int = 120,
    powershell: bool = False,
) -> tuple[int, str, str]:
    """Executa um comando do sistema de forma tratada.

    Args:
        comando: lista de argumentos (preferível) ou string.
        shell: se ``True``, executa via shell (use com cautela).
        timeout: tempo máximo em segundos.
        powershell: se ``True``, encapsula o comando no PowerShell.

    Returns:
        Tupla ``(codigo_retorno, saida_padrao, saida_erro)``. Em falha de
        execução, ``codigo_retorno`` é -1 e a mensagem vai em ``saida_erro``.
    """
    try:
        if powershell:
            cmd: list[str] | str = [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                comando if isinstance(comando, str) else " ".join(comando),
            ]
            usar_shell = False
        else:
            cmd = comando
            usar_shell = shell

        # Captura em bytes e decodifica manualmente (code page do Windows varia).
        resultado = subprocess.run(
            cmd,
            shell=usar_shell,
            capture_output=True,
            text=False,
            timeout=timeout,
            creationflags=_SEM_JANELA,
        )
        return (
            resultado.returncode,
            _decodificar(resultado.stdout).strip(),
            _decodificar(resultado.stderr).strip(),
        )
    except subprocess.TimeoutExpired:
        registrar(f"Comando excedeu o tempo limite: {comando}", logging.ERROR)
        return -1, "", "Tempo limite excedido."
    except FileNotFoundError as exc:
        registrar(f"Comando não encontrado: {comando} ({exc})", logging.ERROR)
        return -1, "", f"Comando não encontrado: {exc}"
    except Exception as exc:  # noqa: BLE001 - nunca deixar uma falha vazar
        registrar(f"Falha ao executar comando {comando}: {exc}", logging.ERROR)
        return -1, "", str(exc)


# ---------------------------------------------------------------------------
# Ponto de restauração do sistema
# ---------------------------------------------------------------------------
def garantir_restauracao_habilitada() -> None:
    """Tenta habilitar a Restauração do Sistema na unidade C: (best-effort)."""
    if not sys.platform.startswith("win"):
        return
    executar_comando(
        'Enable-ComputerRestore -Drive "C:\\"',
        powershell=True,
        timeout=60,
    )


def criar_ponto_restauracao(descricao: str) -> bool:
    """Cria um ponto de restauração do sistema.

    Usa o cmdlet ``Checkpoint-Computer`` do PowerShell. O Windows limita a
    criação a uma vez a cada 24h por padrão, então uma "falha" pode apenas
    significar que já existe um ponto recente — o chamador trata isso.

    Returns:
        ``True`` se o ponto foi criado com sucesso; ``False`` caso contrário.
    """
    if not sys.platform.startswith("win"):
        registrar("Ponto de restauração ignorado (não é Windows).", logging.WARNING)
        return False

    garantir_restauracao_habilitada()
    descricao_segura = descricao.replace('"', "'")
    codigo, _saida, erro = executar_comando(
        f'Checkpoint-Computer -Description "{descricao_segura}" '
        f'-RestorePointType "MODIFY_SETTINGS"',
        powershell=True,
        timeout=180,
    )
    if codigo == 0:
        registrar_acao("seguranca", "Ponto de restauração criado", True, descricao)
        return True
    registrar_acao("seguranca", "Ponto de restauração", False, erro or "retorno != 0")
    return False


def garantir_ponto_restauracao(estado: config.EstadoApp) -> bool:
    """Garante um ponto de restauração antes de alterações nesta sessão.

    Cria o ponto apenas uma vez por sessão. Em modo simulação, não faz nada.
    Se a criação falhar, avisa e pede confirmação explícita para continuar
    (conforme exigido pelas regras de segurança).

    Returns:
        ``True`` se é seguro prosseguir; ``False`` se o usuário decidiu parar.
    """
    if estado.simulacao:
        return True
    if estado.ponto_restauracao_criado:
        return True

    interface.texto("Criando ponto de restauração do sistema (pode levar um momento)...", "dim")
    with interface.spinner("Criando ponto de restauração") as progresso:
        tarefa = progresso.add_task("Criando ponto de restauração", total=None)
        ok = criar_ponto_restauracao(f"{config.NOME_APP} - antes de alterações")
        progresso.update(tarefa, completed=1)

    if ok:
        estado.ponto_restauracao_criado = True
        interface.sucesso("Ponto de restauração criado com sucesso.")
        return True

    interface.aviso(
        "Não foi possível criar o ponto de restauração agora.\n"
        "Isso pode ocorrer se a Restauração do Sistema estiver desativada ou "
        "se já existe um ponto criado nas últimas 24 horas.\n"
        "Mesmo assim, esta ferramenta cria backups (.reg) antes de cada alteração."
    )
    return interface.confirmar(
        "Deseja continuar mesmo sem um novo ponto de restauração?",
        padrao=False,
    )


# ---------------------------------------------------------------------------
# Backup de registro (.reg)
# ---------------------------------------------------------------------------
def _carimbo_data_hora() -> str:
    """Retorna um carimbo de data/hora seguro para nomes de arquivo."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def backup_chave_registro(caminho_chave: str, rotulo: str) -> Optional[Path]:
    """Exporta uma chave do registro para a pasta de backups antes de editá-la.

    Args:
        caminho_chave: caminho completo, ex.: ``HKCU\\Control Panel\\Desktop``.
        rotulo: rótulo curto usado no nome do arquivo (ex.: 'efeitos_visuais').

    Returns:
        O ``Path`` do arquivo ``.reg`` gerado, ou ``None`` em caso de falha.
    """
    if not sys.platform.startswith("win"):
        return None

    config.garantir_pastas()
    rotulo_limpo = "".join(c if c.isalnum() or c in "-_" else "_" for c in rotulo)
    destino = config.PASTA_BACKUPS / f"{rotulo_limpo}_{_carimbo_data_hora()}.reg"

    codigo, _saida, erro = executar_comando(
        ["reg", "export", caminho_chave, str(destino), "/y"],
        timeout=60,
    )
    if codigo == 0 and destino.exists():
        registrar_acao("seguranca", "Backup de registro", True, str(destino))
        return destino

    registrar_acao("seguranca", "Backup de registro", False, f"{caminho_chave} | {erro}")
    return None


def restaurar_backup_registro(arquivo_reg: str | Path) -> bool:
    """Reimporta um arquivo ``.reg`` previamente exportado."""
    if not sys.platform.startswith("win"):
        return False
    arquivo = Path(arquivo_reg)
    if not arquivo.exists():
        registrar_acao("seguranca", "Restaurar registro", False, f"arquivo ausente: {arquivo}")
        return False
    codigo, _saida, erro = executar_comando(["reg", "import", str(arquivo)], timeout=60)
    sucesso = codigo == 0
    registrar_acao("seguranca", "Restaurar registro", sucesso, str(arquivo) if sucesso else erro)
    return sucesso


# ---------------------------------------------------------------------------
# Pilha de desfazer (rollback)
# ---------------------------------------------------------------------------
def _ler_pilha_desfazer() -> list[dict[str, Any]]:
    """Lê a pilha de desfazer do disco (lista de entradas, mais antiga primeiro)."""
    arquivo = config.ARQUIVO_HISTORICO_DESFAZER
    if not arquivo.exists():
        return []
    try:
        with arquivo.open("r", encoding="utf-8") as fp:
            dados = json.load(fp)
        if isinstance(dados, list):
            return dados
    except (OSError, json.JSONDecodeError) as exc:
        registrar(f"Falha ao ler histórico de desfazer: {exc}", logging.WARNING)
    return []


def _gravar_pilha_desfazer(pilha: list[dict[str, Any]]) -> None:
    """Grava a pilha de desfazer no disco."""
    config.garantir_pastas()
    try:
        with config.ARQUIVO_HISTORICO_DESFAZER.open("w", encoding="utf-8") as fp:
            json.dump(pilha, fp, ensure_ascii=False, indent=2)
    except OSError as exc:
        registrar(f"Falha ao gravar histórico de desfazer: {exc}", logging.ERROR)


def registrar_desfazer(
    modulo: str,
    descricao: str,
    tipo: str,
    dados: dict[str, Any],
) -> None:
    """Adiciona uma entrada à pilha de desfazer.

    Args:
        modulo: categoria da ação (ex.: 'servicos').
        descricao: texto legível mostrado ao usuário no "Desfazer".
        tipo: identificador do tipo de rollback. Tipos suportados:
            'reg_import'   -> dados['arquivo']
            'servico'      -> dados['nome'], dados['start_original']
            'dns'          -> dados['interface'], dados['dns_original']
            'plano_energia'-> dados['guid_anterior']
            'inicializacao'-> dados['nome'], dados['raiz'], dados['valor'], ...
        dados: payload necessário para reverter.
    """
    pilha = _ler_pilha_desfazer()
    pilha.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "modulo": modulo,
            "descricao": descricao,
            "tipo": tipo,
            "dados": dados,
        }
    )
    _gravar_pilha_desfazer(pilha)
    registrar_acao(modulo, f"Registrado para desfazer: {descricao}", True, tipo)


def ha_acoes_para_desfazer() -> bool:
    """Indica se existe ao menos uma ação reversível registrada."""
    return len(_ler_pilha_desfazer()) > 0


def descrever_ultima_acao() -> Optional[str]:
    """Retorna a descrição da última ação reversível, se houver."""
    pilha = _ler_pilha_desfazer()
    if not pilha:
        return None
    ultima = pilha[-1]
    return f"{ultima.get('descricao', '?')}  ({ultima.get('timestamp', '?')})"


def desfazer_ultima_acao() -> tuple[bool, str]:
    """Desfaz a última ação registrada na pilha.

    Returns:
        Tupla ``(sucesso, mensagem)`` descrevendo o resultado.
    """
    pilha = _ler_pilha_desfazer()
    if not pilha:
        return False, "Não há nenhuma alteração para desfazer."

    entrada = pilha[-1]
    descricao = entrada.get("descricao", "ação desconhecida")
    sucesso, msg = _aplicar_desfazer(entrada)

    if sucesso:
        # Só remove da pilha se conseguiu reverter de fato.
        pilha.pop()
        _gravar_pilha_desfazer(pilha)
        registrar_acao(entrada.get("modulo", "desfazer"), f"Desfeito: {descricao}", True)
        return True, f"Alteração desfeita: {descricao}\n{msg}".strip()

    registrar_acao(entrada.get("modulo", "desfazer"), f"Falha ao desfazer: {descricao}", False, msg)
    return False, f"Não foi possível desfazer: {descricao}\n{msg}".strip()


def _aplicar_desfazer(entrada: dict[str, Any]) -> tuple[bool, str]:
    """Despacha o rollback conforme o tipo da entrada."""
    tipo = entrada.get("tipo", "")
    dados = entrada.get("dados", {}) or {}

    try:
        if tipo == "reg_import":
            # Aceita um único arquivo ('arquivo') ou vários ('arquivos').
            arquivos = dados.get("arquivos") or [dados.get("arquivo", "")]
            arquivos = [a for a in arquivos if a]
            if not arquivos:
                return False, "Nenhum arquivo de backup associado a esta ação."
            resultados = [restaurar_backup_registro(a) for a in arquivos]
            if all(resultados):
                return True, f"Registro restaurado a partir de {len(arquivos)} backup(s)."
            if any(resultados):
                return True, "Registro restaurado parcialmente (alguns backups falharam)."
            return False, "Falha ao reimportar o(s) backup(s) do registro."

        if tipo == "servico":
            return _desfazer_servico(dados)

        if tipo == "dns":
            return _desfazer_dns(dados)

        if tipo == "plano_energia":
            guid = dados.get("guid_anterior", "")
            codigo, _s, err = executar_comando(["powercfg", "/setactive", guid], timeout=30)
            if codigo == 0:
                return True, "Plano de energia anterior reativado."
            return False, f"Falha ao reativar o plano anterior: {err}"

        if tipo == "inicializacao":
            return _desfazer_inicializacao(dados)

        return False, f"Tipo de desfazer desconhecido: {tipo}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Erro inesperado ao desfazer: {exc}"


def _desfazer_servico(dados: dict[str, Any]) -> tuple[bool, str]:
    """Restaura o tipo de inicialização original de um serviço."""
    nome = dados.get("nome", "")
    start_original = dados.get("start_original", "demand")
    # Mapeia o StartMode (WMI) para o argumento do 'sc config'.
    mapa = {
        "auto": "auto",
        "automatic": "auto",
        "manual": "demand",
        "demand": "demand",
        "disabled": "disabled",
        "boot": "boot",
        "system": "system",
    }
    arg = mapa.get(str(start_original).lower(), "demand")
    codigo, _s, err = executar_comando(["sc", "config", nome, "start=", arg], timeout=30)
    if codigo == 0:
        return True, f"Serviço '{nome}' restaurado para '{arg}'."
    return False, f"Falha ao restaurar o serviço '{nome}': {err}"


def _desfazer_dns(dados: dict[str, Any]) -> tuple[bool, str]:
    """Restaura a configuração de DNS anterior de uma interface."""
    nome_if = dados.get("interface", "")
    dns_original = dados.get("dns_original", "dhcp")

    if dns_original == "dhcp" or not dns_original:
        codigo, _s, err = executar_comando(
            ["netsh", "interface", "ip", "set", "dns", f"name={nome_if}", "dhcp"],
            timeout=30,
        )
        if codigo == 0:
            return True, f"DNS da interface '{nome_if}' voltou para automático (DHCP)."
        return False, f"Falha ao restaurar DNS automático: {err}"

    # dns_original é uma lista de endereços estáticos.
    enderecos = dns_original if isinstance(dns_original, list) else [dns_original]
    codigo, _s, err = executar_comando(
        ["netsh", "interface", "ip", "set", "dns", f"name={nome_if}", "static", enderecos[0], "primary"],
        timeout=30,
    )
    if codigo != 0:
        return False, f"Falha ao restaurar DNS estático: {err}"
    for indice, end in enumerate(enderecos[1:], start=2):
        executar_comando(
            ["netsh", "interface", "ip", "add", "dns", f"name={nome_if}", end, f"index={indice}"],
            timeout=30,
        )
    return True, f"DNS estático anterior restaurado na interface '{nome_if}'."


def _desfazer_inicializacao(dados: dict[str, Any]) -> tuple[bool, str]:
    """Reativa um item de inicialização que havíamos desativado.

    A reativação é feita pelo próprio módulo de inicialização para manter a
    lógica de registro em um só lugar; aqui apenas a chamamos.
    """
    try:
        from modulos.tweaks import inicializacao

        return inicializacao.reativar_por_dados(dados)
    except Exception as exc:  # noqa: BLE001
        return False, f"Falha ao reativar item de inicialização: {exc}"
