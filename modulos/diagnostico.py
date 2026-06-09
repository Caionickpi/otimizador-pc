"""Fase de diagnóstico — detecção de hardware e software (somente leitura).

Coleta um perfil completo da máquina e o devolve como um dicionário, que é
guardado em memória (no ``EstadoApp``) para as etapas de recomendação e de
ajustes. Tudo aqui é somente leitura, portanto seguro de rodar mesmo sem
privilégios de administrador.

A detecção usa ``psutil`` (números de uso/uptime), ``py-cpuinfo`` (modelo de
CPU) e WMI (detalhes de hardware do Windows). Cada coletor é isolado em um
try/except próprio: se um falhar, os demais continuam.
"""

from __future__ import annotations

import logging
import platform
import sys
from datetime import datetime
from typing import Any, Optional

import psutil

from modulos import interface, seguranca

# Importações específicas de Windows são tratadas para não quebrar o import.
try:  # pragma: no cover - depende do SO
    import wmi  # type: ignore
except Exception:  # noqa: BLE001
    wmi = None  # type: ignore

try:  # pragma: no cover
    import cpuinfo  # type: ignore
except Exception:  # noqa: BLE001
    cpuinfo = None  # type: ignore


def _conectar_wmi(namespace: str = "root\\cimv2") -> Optional[Any]:
    """Abre uma conexão WMI no namespace pedido, ou ``None`` se indisponível."""
    if wmi is None or not sys.platform.startswith("win"):
        return None
    try:
        # CoInitialize é tratado internamente pelo pacote wmi na thread atual.
        return wmi.WMI(namespace=namespace)
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar(f"Falha ao conectar no WMI ({namespace}): {exc}", logging.WARNING)
        return None


# ---------------------------------------------------------------------------
# Coletores individuais
# ---------------------------------------------------------------------------
def _coletar_sistema(c: Optional[Any]) -> dict[str, Any]:
    """Coleta dados do sistema operacional."""
    dados: dict[str, Any] = {
        "nome_so": platform.system(),
        "versao": platform.version(),
        "release": platform.release(),
        "arquitetura": platform.machine(),
        "edicao": "-",
        "build": "-",
        "uptime": "-",
    }
    try:
        segundos_ligado = (datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds()
        dados["uptime"] = interface.formatar_tempo(segundos_ligado)
    except Exception:  # noqa: BLE001
        pass

    if c is not None:
        try:
            so = c.Win32_OperatingSystem()[0]
            dados["edicao"] = getattr(so, "Caption", dados["edicao"]) or dados["edicao"]
            dados["build"] = getattr(so, "BuildNumber", dados["build"]) or dados["build"]
            arq = getattr(so, "OSArchitecture", None)
            if arq:
                dados["arquitetura"] = arq
        except Exception as exc:  # noqa: BLE001
            seguranca.registrar(f"Diagnóstico SO via WMI falhou: {exc}", logging.WARNING)
    return dados


def _coletar_cpu(c: Optional[Any]) -> dict[str, Any]:
    """Coleta dados do processador."""
    dados: dict[str, Any] = {
        "modelo": platform.processor() or "-",
        "nucleos_fisicos": psutil.cpu_count(logical=False) or 0,
        "nucleos_logicos": psutil.cpu_count(logical=True) or 0,
        "freq_base_mhz": 0.0,
        "freq_atual_mhz": 0.0,
        "uso_percent": 0.0,
    }
    try:
        # Amostra rápida de uso (intervalo curto para não travar a TUI).
        dados["uso_percent"] = psutil.cpu_percent(interval=0.5)
    except Exception:  # noqa: BLE001
        pass
    try:
        freq = psutil.cpu_freq()
        if freq:
            dados["freq_atual_mhz"] = round(freq.current, 0)
            dados["freq_base_mhz"] = round(freq.max or freq.current, 0)
    except Exception:  # noqa: BLE001
        pass
    if cpuinfo is not None:
        try:
            info = cpuinfo.get_cpu_info()
            if info.get("brand_raw"):
                dados["modelo"] = info["brand_raw"]
        except Exception:  # noqa: BLE001
            pass
    if c is not None and dados["modelo"] in ("", "-"):
        try:
            dados["modelo"] = c.Win32_Processor()[0].Name.strip()
        except Exception:  # noqa: BLE001
            pass
    return dados


def _coletar_memoria(c: Optional[Any]) -> dict[str, Any]:
    """Coleta dados da memória RAM, incluindo velocidade dos módulos via WMI."""
    mem = psutil.virtual_memory()
    dados: dict[str, Any] = {
        "total": mem.total,
        "em_uso": mem.used,
        "disponivel": mem.available,
        "percent": mem.percent,
        "total_gb": round(mem.total / (1024 ** 3), 1),
        "velocidade_mhz": "-",
        "modulos": [],
    }
    if c is not None:
        try:
            velocidades: list[int] = []
            for modulo in c.Win32_PhysicalMemory():
                vel = getattr(modulo, "Speed", None)
                cap = getattr(modulo, "Capacity", None)
                if vel:
                    velocidades.append(int(vel))
                dados["modulos"].append(
                    {
                        "capacidade": int(cap) if cap else 0,
                        "velocidade": int(vel) if vel else 0,
                        "fabricante": (getattr(modulo, "Manufacturer", "") or "").strip(),
                    }
                )
            if velocidades:
                dados["velocidade_mhz"] = max(velocidades)
        except Exception as exc:  # noqa: BLE001
            seguranca.registrar(f"Diagnóstico RAM via WMI falhou: {exc}", logging.WARNING)
    return dados


def _mapa_tipo_midia_fisica(c_storage: Optional[Any]) -> dict[int, dict[str, Any]]:
    """Mapeia o número do disco físico -> tipo de mídia (SSD/HDD) e saúde.

    Usa a classe MSFT_PhysicalDisk (namespace de Storage), disponível no
    Windows 8+/10/11. MediaType: 3 = HDD, 4 = SSD, 5 = SCM. SpindleSpeed 0
    reforça SSD.
    """
    mapa: dict[int, dict[str, Any]] = {}
    if c_storage is None:
        return mapa
    nomes_tipo = {0: "Desconhecido", 3: "HDD", 4: "SSD", 5: "SSD (SCM)"}
    nomes_saude = {0: "Saudável", 1: "Atenção", 2: "Crítico"}
    try:
        for disco in c_storage.MSFT_PhysicalDisk():
            try:
                numero = int(getattr(disco, "DeviceId", -1))
            except (TypeError, ValueError):
                continue
            tipo_codigo = int(getattr(disco, "MediaType", 0) or 0)
            saude_codigo = getattr(disco, "HealthStatus", None)
            mapa[numero] = {
                "tipo": nomes_tipo.get(tipo_codigo, "Desconhecido"),
                "saude": nomes_saude.get(int(saude_codigo) if saude_codigo is not None else -1, "-"),
                "modelo": (getattr(disco, "FriendlyName", "") or "").strip(),
            }
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar(f"MSFT_PhysicalDisk indisponível: {exc}", logging.WARNING)
    return mapa


def _coletar_armazenamento(c: Optional[Any], c_storage: Optional[Any]) -> list[dict[str, Any]]:
    """Coleta as unidades de armazenamento e tenta identificar SSD x HDD.

    Estratégia: pega tamanho/uso/sistema de arquivos das unidades lógicas via
    psutil e cruza com o tipo de mídia (SSD/HDD) do disco físico através das
    associações WMI Win32_DiskDrive -> Partition -> LogicalDisk.
    """
    unidades: list[dict[str, Any]] = []

    # 1) Tabela letra-da-unidade -> tipo/saúde, via associações WMI.
    letra_para_fisico: dict[str, dict[str, Any]] = {}
    mapa_fisico = _mapa_tipo_midia_fisica(c_storage)
    if c is not None:
        try:
            for drive in c.Win32_DiskDrive():
                try:
                    indice = int(getattr(drive, "Index", -1))
                except (TypeError, ValueError):
                    indice = -1
                info_fisico = mapa_fisico.get(indice, {})
                tipo = info_fisico.get("tipo", "-")
                saude = info_fisico.get("saude", "-")
                # Heurística de reserva, caso MSFT_PhysicalDisk não exista.
                if tipo == "-" or tipo == "Desconhecido":
                    modelo = (getattr(drive, "Model", "") or "").upper()
                    if "SSD" in modelo or "NVME" in modelo:
                        tipo = "SSD"
                # Saúde de reserva via Status do Win32_DiskDrive (SMART).
                if saude in ("-", None):
                    status = getattr(drive, "Status", None)
                    saude = "Saudável" if status == "OK" else (status or "-")
                for particao in drive.associators("Win32_DiskDriveToDiskPartition"):
                    for logico in particao.associators("Win32_LogicalDiskToPartition"):
                        letra = getattr(logico, "DeviceID", None)
                        if letra:
                            letra_para_fisico[letra.upper()] = {"tipo": tipo, "saude": saude}
        except Exception as exc:  # noqa: BLE001
            seguranca.registrar(f"Associação de discos via WMI falhou: {exc}", logging.WARNING)

    # 2) Tamanho/uso por unidade lógica (psutil), enriquecido com o tipo.
    for particao in psutil.disk_partitions(all=False):
        try:
            uso = psutil.disk_usage(particao.mountpoint)
        except (PermissionError, OSError):
            # Ex.: leitor de cartão vazio. Ignora silenciosamente.
            continue
        letra = particao.device.rstrip("\\").upper()
        info_fisico = letra_para_fisico.get(letra, {})
        unidades.append(
            {
                "unidade": particao.device,
                "tipo": info_fisico.get("tipo", "-"),
                "saude": info_fisico.get("saude", "-"),
                "sistema_arquivos": particao.fstype or "-",
                "total": uso.total,
                "livre": uso.free,
                "usado": uso.used,
                "percent": uso.percent,
            }
        )
    return unidades


def _coletar_gpu(c: Optional[Any]) -> list[dict[str, Any]]:
    """Coleta as placas de vídeo (modelo, VRAM aproximada e driver)."""
    gpus: list[dict[str, Any]] = []
    if c is None:
        return gpus
    try:
        for video in c.Win32_VideoController():
            vram = getattr(video, "AdapterRAM", None)
            gpus.append(
                {
                    "modelo": (getattr(video, "Name", "") or "-").strip(),
                    # AdapterRAM é uint32 e satura em 4 GB para GPUs maiores;
                    # marcamos como aproximado.
                    "vram": int(vram) if vram and int(vram) > 0 else 0,
                    "driver": (getattr(video, "DriverVersion", "") or "-").strip(),
                }
            )
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar(f"Diagnóstico GPU via WMI falhou: {exc}", logging.WARNING)
    return gpus


def _coletar_placa_mae(c: Optional[Any]) -> dict[str, Any]:
    """Coleta fabricante/modelo da placa-mãe e versão da BIOS."""
    dados: dict[str, Any] = {"fabricante": "-", "modelo": "-", "bios": "-"}
    if c is None:
        return dados
    try:
        placa = c.Win32_BaseBoard()[0]
        dados["fabricante"] = (getattr(placa, "Manufacturer", "") or "-").strip()
        dados["modelo"] = (getattr(placa, "Product", "") or "-").strip()
    except Exception:  # noqa: BLE001
        pass
    try:
        bios = c.Win32_BIOS()[0]
        versao = getattr(bios, "SMBIOSBIOSVersion", "") or getattr(bios, "Version", "")
        dados["bios"] = (versao or "-").strip()
    except Exception:  # noqa: BLE001
        pass
    return dados


def _coletar_rede(c: Optional[Any]) -> list[dict[str, Any]]:
    """Coleta adaptadores de rede ativos com IP e servidores DNS."""
    adaptadores: list[dict[str, Any]] = []
    if c is None:
        return adaptadores
    try:
        for cfg in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
            ips = list(getattr(cfg, "IPAddress", None) or [])
            dns = list(getattr(cfg, "DNSServerSearchOrder", None) or [])
            # Mantém apenas o IPv4 para exibição simples.
            ipv4 = next((ip for ip in ips if ":" not in ip), ips[0] if ips else "-")
            adaptadores.append(
                {
                    "descricao": (getattr(cfg, "Description", "") or "-").strip(),
                    "ip": ipv4,
                    "dns": dns,
                    "mac": getattr(cfg, "MACAddress", "-") or "-",
                }
            )
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar(f"Diagnóstico de rede via WMI falhou: {exc}", logging.WARNING)
    return adaptadores


def _coletar_inicializacao(c: Optional[Any]) -> list[dict[str, Any]]:
    """Lista programas que iniciam com o Windows (via WMI Win32_StartupCommand)."""
    itens: list[dict[str, Any]] = []
    if c is None:
        return itens
    try:
        for cmd in c.Win32_StartupCommand():
            itens.append(
                {
                    "nome": (getattr(cmd, "Name", "") or "-").strip(),
                    "comando": (getattr(cmd, "Command", "") or "-").strip(),
                    "local": (getattr(cmd, "Location", "") or "-").strip(),
                    "usuario": (getattr(cmd, "User", "") or "-").strip(),
                }
            )
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar(f"Diagnóstico de inicialização via WMI falhou: {exc}", logging.WARNING)
    return itens


def _coletar_energia() -> dict[str, Any]:
    """Coleta o plano de energia ativo e se há bateria (notebook x desktop)."""
    dados: dict[str, Any] = {"plano_ativo": "-", "guid_ativo": "-", "tem_bateria": False}
    try:
        bateria = psutil.sensors_battery()
        dados["tem_bateria"] = bateria is not None
    except Exception:  # noqa: BLE001
        pass
    if sys.platform.startswith("win"):
        codigo, saida, _err = seguranca.executar_comando(["powercfg", "/getactivescheme"], timeout=20)
        if codigo == 0 and saida:
            # Exemplo: "Power Scheme GUID: 381b...  (Equilibrado)"
            dados["plano_ativo"] = _extrair_nome_plano(saida)
            dados["guid_ativo"] = _extrair_guid_plano(saida)
    return dados


def _extrair_guid_plano(linha: str) -> str:
    """Extrai o GUID de uma linha de saída do powercfg."""
    partes = linha.split(":", 1)
    if len(partes) == 2:
        resto = partes[1].strip()
        return resto.split()[0] if resto else "-"
    return "-"


def _extrair_nome_plano(linha: str) -> str:
    """Extrai o nome amigável (entre parênteses) de uma linha do powercfg."""
    inicio = linha.find("(")
    fim = linha.rfind(")")
    if 0 <= inicio < fim:
        return linha[inicio + 1 : fim].strip()
    return linha.strip()


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------
def coletar_perfil() -> dict[str, Any]:
    """Coleta o perfil completo da máquina e o retorna como dicionário.

    Mostra uma barra de progresso enquanto executa cada coletor. Nunca lança:
    coletores que falham apenas deixam seus campos com valores neutros.
    """
    seguranca.registrar("Iniciando coleta de diagnóstico.", logging.INFO)
    c = _conectar_wmi("root\\cimv2")
    c_storage = _conectar_wmi("root\\Microsoft\\Windows\\Storage")

    etapas: list[tuple[str, Any]] = [
        ("Sistema operacional", lambda: _coletar_sistema(c)),
        ("Processador", lambda: _coletar_cpu(c)),
        ("Memória RAM", lambda: _coletar_memoria(c)),
        ("Armazenamento", lambda: _coletar_armazenamento(c, c_storage)),
        ("Placa de vídeo", lambda: _coletar_gpu(c)),
        ("Placa-mãe e BIOS", lambda: _coletar_placa_mae(c)),
        ("Rede", lambda: _coletar_rede(c)),
        ("Inicialização", lambda: _coletar_inicializacao(c)),
        ("Energia", _coletar_energia),
    ]

    perfil: dict[str, Any] = {}
    chaves = ["sistema", "cpu", "memoria", "armazenamento", "gpu", "placa_mae", "rede", "inicializacao", "energia"]

    with interface.barra_progresso() as progresso:
        tarefa = progresso.add_task("Diagnosticando o computador", total=len(etapas))
        for (rotulo, funcao), chave in zip(etapas, chaves):
            progresso.update(tarefa, description=f"Analisando: {rotulo}")
            try:
                perfil[chave] = funcao()
            except Exception as exc:  # noqa: BLE001
                seguranca.registrar(f"Coletor '{rotulo}' falhou: {exc}", logging.ERROR)
                perfil[chave] = {} if chave not in ("armazenamento", "gpu", "rede", "inicializacao") else []
            progresso.advance(tarefa)

    perfil["coletado_em"] = datetime.now().isoformat(timespec="seconds")
    seguranca.registrar("Diagnóstico concluído.", logging.INFO)
    return perfil


# ---------------------------------------------------------------------------
# Exibição
# ---------------------------------------------------------------------------
def exibir_perfil(perfil: dict[str, Any]) -> None:
    """Exibe o perfil coletado em tabelas bonitas do rich."""
    if not perfil:
        interface.aviso("Nenhum diagnóstico disponível. Rode a opção de diagnóstico primeiro.")
        return

    sistema = perfil.get("sistema", {})
    interface.tabela_chave_valor(
        "Sistema",
        [
            ("Sistema operacional", interface.escapar(sistema.get("edicao", "-"))),
            ("Versão / Build", f"{sistema.get('release', '-')} (build {sistema.get('build', '-')})"),
            ("Arquitetura", sistema.get("arquitetura", "-")),
            ("Ligado há", sistema.get("uptime", "-")),
        ],
    )

    cpu = perfil.get("cpu", {})
    interface.tabela_chave_valor(
        "Processador (CPU)",
        [
            ("Modelo", interface.escapar(cpu.get("modelo", "-"))),
            ("Núcleos", f"{cpu.get('nucleos_fisicos', '-')} físicos / {cpu.get('nucleos_logicos', '-')} lógicos"),
            ("Frequência", f"{cpu.get('freq_atual_mhz', 0):.0f} MHz (base {cpu.get('freq_base_mhz', 0):.0f} MHz)"),
            ("Uso atual", f"{cpu.get('uso_percent', 0):.0f}%"),
        ],
    )

    mem = perfil.get("memoria", {})
    velocidade = mem.get("velocidade_mhz", "-")
    interface.tabela_chave_valor(
        "Memória RAM",
        [
            ("Total", interface.formatar_bytes(mem.get("total", 0))),
            ("Em uso", f"{interface.formatar_bytes(mem.get('em_uso', 0))} ({mem.get('percent', 0):.0f}%)"),
            ("Disponível", interface.formatar_bytes(mem.get("disponivel", 0))),
            ("Velocidade", f"{velocidade} MHz" if velocidade != "-" else "-"),
        ],
    )

    _exibir_tabela_discos(perfil.get("armazenamento", []))

    gpus = perfil.get("gpu", [])
    if gpus:
        tabela = interface.nova_tabela("Placa(s) de vídeo (GPU)", ["Modelo", "VRAM", "Driver"])
        for gpu in gpus:
            vram = interface.formatar_bytes(gpu.get("vram", 0)) if gpu.get("vram") else "≈ (não reportado)"
            tabela.add_row(
                interface.escapar(gpu.get("modelo", "-")),
                vram,
                interface.escapar(gpu.get("driver", "-")),
            )
        interface.imprimir_tabela(tabela)

    placa = perfil.get("placa_mae", {})
    interface.tabela_chave_valor(
        "Placa-mãe e BIOS",
        [
            ("Fabricante", interface.escapar(placa.get("fabricante", "-"))),
            ("Modelo", interface.escapar(placa.get("modelo", "-"))),
            ("Versão da BIOS", interface.escapar(placa.get("bios", "-"))),
        ],
    )

    redes = perfil.get("rede", [])
    if redes:
        tabela = interface.nova_tabela("Rede", ["Adaptador", "IP", "DNS"])
        for rede in redes:
            tabela.add_row(
                interface.escapar(rede.get("descricao", "-")),
                interface.escapar(rede.get("ip", "-")),
                interface.escapar(", ".join(rede.get("dns", [])) or "-"),
            )
        interface.imprimir_tabela(tabela)

    energia = perfil.get("energia", {})
    tipo_maquina = "Notebook (com bateria)" if energia.get("tem_bateria") else "Desktop (sem bateria)"
    interface.tabela_chave_valor(
        "Energia",
        [
            ("Tipo de máquina", tipo_maquina),
            ("Plano de energia ativo", energia.get("plano_ativo", "-")),
        ],
    )

    inicializacao = perfil.get("inicializacao", [])
    interface.texto(
        f"\nProgramas na inicialização do Windows: {len(inicializacao)} encontrados.",
        "dim",
    )
    if inicializacao:
        tabela = interface.nova_tabela("Inicialização (resumo)", ["Programa", "Local"])
        for item in inicializacao[:15]:
            tabela.add_row(interface.escapar(item.get("nome", "-")), interface.escapar(item.get("local", "-")))
        interface.imprimir_tabela(tabela)
        if len(inicializacao) > 15:
            interface.texto(f"... e mais {len(inicializacao) - 15} item(ns).", "dim")


def _exibir_tabela_discos(discos: list[dict[str, Any]]) -> None:
    """Exibe a tabela de armazenamento com cores conforme o espaço livre."""
    if not discos:
        return
    tabela = interface.nova_tabela(
        "Armazenamento",
        ["Unidade", "Tipo", "Sistema", "Total", "Livre", "Uso", "Saúde"],
    )
    for disco in discos:
        percent = disco.get("percent", 0)
        # Cor do uso: verde < 75%, amarelo 75-90%, vermelho > 90%.
        if percent >= 90:
            cor_uso = "red"
        elif percent >= 75:
            cor_uso = "yellow"
        else:
            cor_uso = "green"
        tabela.add_row(
            disco.get("unidade", "-"),
            disco.get("tipo", "-"),
            disco.get("sistema_arquivos", "-"),
            interface.formatar_bytes(disco.get("total", 0)),
            interface.formatar_bytes(disco.get("livre", 0)),
            f"[{cor_uso}]{percent:.0f}%[/{cor_uso}]",
            disco.get("saude", "-"),
        )
    interface.imprimir_tabela(tabela)
