"""Tweak: otimizações AVANÇADAS (jogos e desempenho geral).

⚠️  AVISO: esta aba reúne a parte "pesada" da otimização — ajustes de risco
MÉDIO/ALTO, voltados a usuários avançados que querem extrair o máximo de
desempenho, especialmente em jogos. Vários mexem no registro do Windows, no
agendador de CPU/GPU ou na rede, e podem exigir ADMINISTRADOR e/ou REINICIAR.

Fiel ao princípio do programa, o PROCESSO continua seguro: cada ação descreve
o que faz, AVISA os riscos, faz backup (.reg), pede confirmação, respeita o
modo simulação e registra um "desfazer" PRECISO — restaura o valor anterior ou
remove exatamente o que foi criado.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import config
from modulos import interface, seguranca

try:  # pragma: no cover
    import winreg  # type: ignore
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore


# GUID do plano "Desempenho Máximo" (Ultimate Performance) embutido no Windows.
_GUID_ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
_CAMINHO_INTERFACES = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"


def _hive(raiz: str) -> Any:
    """Converte 'HKLM'/'HKCU' na constante de hive do winreg."""
    return winreg.HKEY_LOCAL_MACHINE if raiz.upper() == "HKLM" else winreg.HKEY_CURRENT_USER


# ---------------------------------------------------------------------------
# Snapshot + aplicação de valores de registro (com "desfazer" preciso)
# ---------------------------------------------------------------------------
def _snapshot(raiz: str, subchave: str, nome: str) -> dict[str, Any]:
    """Captura o estado atual de um valor para permitir reverter com precisão."""
    snap: dict[str, Any] = {
        "raiz": raiz, "subchave": subchave, "nome": nome,
        "existia": False, "tipo": None, "dado": None,
    }
    if winreg is None:
        return snap
    try:
        with winreg.OpenKey(_hive(raiz), subchave, 0, winreg.KEY_READ) as chave:
            dado, tipo = winreg.QueryValueEx(chave, nome)
        # Só guardamos tipos serializáveis em JSON (DWORD/QWORD/SZ/MULTI_SZ).
        if isinstance(dado, (int, str, list)):
            snap.update({"existia": True, "tipo": int(tipo), "dado": dado})
        else:
            snap["existia"] = True  # existe, mas não dá para serializar o valor
    except (FileNotFoundError, OSError):
        pass
    return snap


def _definir(raiz: str, subchave: str, nome: str, tipo: int, dado: Any) -> bool:
    """Cria/atualiza um valor no registro (cria a chave se necessário)."""
    if winreg is None:
        return False
    with winreg.CreateKeyEx(_hive(raiz), subchave, 0, winreg.KEY_SET_VALUE) as chave:
        winreg.SetValueEx(chave, nome, 0, tipo, dado)
    return True


def desfazer_reg_valores(dados: dict[str, Any]) -> tuple[bool, str]:
    """Reverte um pacote de valores: restaura os antigos e remove os criados.

    Usado pelo módulo de segurança ao desfazer um ajuste avançado.

    Caso raro tratado: se um valor JÁ EXISTIA mas não pôde ser serializado no
    snapshot (ex.: REG_BINARY), NÃO o apagamos — apagar seria pior do que
    deixar o ajuste aplicado. Ele é contado como "pulado" e informado.
    """
    if winreg is None:
        return False, "Registro do Windows indisponível."
    snaps = dados.get("snapshots", []) or []
    revertidos = falhas = pulados = 0
    for s in snaps:
        try:
            hive = _hive(s.get("raiz", "HKCU"))
            sub, nome = s["subchave"], s["nome"]
            if s.get("existia") and s.get("tipo") is not None:
                with winreg.CreateKeyEx(hive, sub, 0, winreg.KEY_SET_VALUE) as chave:
                    winreg.SetValueEx(chave, nome, 0, int(s["tipo"]), s["dado"])
            elif s.get("existia"):
                # Existia, mas o valor original não é restaurável (tipo binário
                # etc.). Mantemos como está em vez de apagar dado do usuário.
                pulados += 1
                continue
            else:
                # Não existia antes -> remover exatamente o que criamos.
                try:
                    with winreg.OpenKey(hive, sub, 0, winreg.KEY_SET_VALUE) as chave:
                        winreg.DeleteValue(chave, nome)
                except FileNotFoundError:
                    pass
            revertidos += 1
        except OSError:
            falhas += 1
    extra = f" ({pulados} mantido(s): valor original não restaurável)" if pulados else ""
    if falhas == 0:
        return True, f"{revertidos} valor(es) de registro restaurado(s).{extra}"
    if revertidos:
        return True, f"Revertido parcialmente ({revertidos} OK, {falhas} falha(s) — pode exigir administrador).{extra}"
    return False, "Não foi possível reverter (precisa de administrador?)."


def _aplicar_pacote(
    estado: config.EstadoApp,
    *,
    titulo: str,
    descricao: str,
    riscos: str,
    valores: list[tuple[str, str, str, int, Any]],
    exige_reinicio: bool = False,
    modulo: str = "avancado",
    cabecalho_titulo: "str | None" = None,
) -> None:
    """Fluxo seguro padrão para um conjunto de valores de registro.

    valores: lista de ``(raiz, subchave, nome, tipo, dado)``. Reutilizável por
    outros módulos (ex.: otimização por jogo) via ``modulo``/``cabecalho_titulo``.
    """
    interface.cabecalho(
        cabecalho_titulo or f"Avançado · {titulo}",
        "Leia a descrição e os riscos antes de aplicar.",
    )
    interface.info(descricao)
    interface.aviso(
        f"⚠ Riscos:\n{riscos}\n\n"
        "Antes de aplicar é feito backup (.reg) das chaves e um ponto de "
        "restauração. Dá para reverter em 'Desfazer última alteração'."
    )

    if estado.simulacao:
        interface.info(
            "MODO SIMULAÇÃO: nada foi alterado.\n"
            f"Seriam ajustados {len(valores)} valor(es) do registro."
        )
        return
    if not interface.confirmar(f"Aplicar '{titulo}' agora?", padrao=False):
        interface.info("Operação cancelada. Nada foi alterado.")
        return
    if not seguranca.garantir_ponto_restauracao(estado):
        interface.info("Operação cancelada (sem ponto de restauração).")
        return

    # Backup das chaves-pai (.reg) por segurança extra.
    for raiz, sub in {(r, s) for r, s, _n, _t, _d in valores}:
        seguranca.backup_chave_registro(f"{raiz}\\{sub}", modulo)

    # Snapshot preciso de cada valor (para o desfazer).
    snapshots = [_snapshot(r, s, n) for r, s, n, _t, _d in valores]

    aplicados = 0
    negado = False
    for raiz, sub, nome, tipo, dado in valores:
        try:
            if _definir(raiz, sub, nome, tipo, dado):
                aplicados += 1
        except PermissionError:
            negado = True
        except OSError as exc:
            seguranca.registrar(f"[avancado] Falha em {raiz}\\{sub}\\{nome}: {exc}", logging.WARNING)

    if aplicados == 0:
        msg = "Nenhum ajuste pôde ser aplicado."
        if negado:
            msg += " Execute o programa como administrador e tente de novo."
        seguranca.registrar_acao(modulo, f"Avançado: {titulo}", False, "0 aplicados")
        interface.erro(msg)
        return

    seguranca.registrar_desfazer(
        modulo, f"Reverter ajuste: {titulo}", "reg_valores", {"snapshots": snapshots}
    )
    seguranca.registrar_acao(modulo, f"Avançado: {titulo}", True, f"{aplicados} valor(es)")
    extra = "\n🔁 Reinicie o computador para o efeito completo." if exige_reinicio else ""
    aviso_admin = "\n(Alguns valores não puderam ser gravados — exigem administrador.)" if negado else ""
    interface.sucesso(f"'{titulo}' aplicado ({aplicados} valor(es)).{extra}{aviso_admin}")


# ---------------------------------------------------------------------------
# Construtores de valores reutilizáveis (também usados na otimização por jogo)
# ---------------------------------------------------------------------------
def valores_pacote_jogos() -> list[tuple[str, str, str, int, Any]]:
    """Pacote GLOBAL de jogo: Modo Jogo, Game DVR off, MMCSS, HAGS e prioridade.

    Reutilizado pela aba de otimização por jogo para montar o perfil completo.
    """
    base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
    return [
        ("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", winreg.REG_DWORD, 1),
        ("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", winreg.REG_DWORD, 1),
        ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", winreg.REG_DWORD, 0),
        ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", winreg.REG_DWORD, 0),
        ("HKLM", base, "SystemResponsiveness", winreg.REG_DWORD, 10),
        ("HKLM", base + r"\Tasks\Games", "GPU Priority", winreg.REG_DWORD, 8),
        ("HKLM", base + r"\Tasks\Games", "Priority", winreg.REG_DWORD, 6),
        ("HKLM", base + r"\Tasks\Games", "Scheduling Category", winreg.REG_SZ, "High"),
        ("HKLM", base + r"\Tasks\Games", "SFIO Priority", winreg.REG_SZ, "High"),
        ("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", winreg.REG_DWORD, 2),
        ("HKLM", r"SYSTEM\CurrentControlSet\Control\PriorityControl",
         "Win32PrioritySeparation", winreg.REG_DWORD, 38),
    ]


def valores_nagle() -> list[tuple[str, str, str, int, Any]]:
    """Tweaks de latência (desativar Nagle) nas interfaces de rede ativas."""
    from modulos.tweaks import rede

    saida: list[tuple[str, str, str, int, Any]] = []
    for interface_rede in rede._interfaces_ativas():
        guid = interface_rede.get("guid")
        if not guid:
            continue
        sub = f"{_CAMINHO_INTERFACES}\\{guid}"
        saida.append(("HKLM", sub, "TcpAckFrequency", winreg.REG_DWORD, 1))
        saida.append(("HKLM", sub, "TCPNoDelay", winreg.REG_DWORD, 1))
    return saida


# ---------------------------------------------------------------------------
# Ações — 🎮 Jogos
# ---------------------------------------------------------------------------
def _acao_modo_jogo(estado: config.EstadoApp) -> None:
    valores = [
        ("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", winreg.REG_DWORD, 1),
        ("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", winreg.REG_DWORD, 1),
        ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", winreg.REG_DWORD, 0),
        ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", winreg.REG_DWORD, 0),
    ]
    _aplicar_pacote(
        estado,
        titulo="Modo Jogo + desativar Game DVR",
        descricao="Liga o Modo Jogo do Windows e desativa a gravação em segundo "
        "plano (Game DVR / Xbox Game Bar), que consome CPU/GPU durante a partida.",
        riscos="Risco BAIXO–MÉDIO. Você perde a gravação automática de gameplay "
        "(a captura manual da Game Bar continua funcionando). A chave em HKLM "
        "exige administrador.",
        valores=valores,
    )


def _acao_prioridade_jogos(estado: config.EstadoApp) -> None:
    base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
    valores = [
        ("HKLM", base, "SystemResponsiveness", winreg.REG_DWORD, 10),
        ("HKLM", base + r"\Tasks\Games", "GPU Priority", winreg.REG_DWORD, 8),
        ("HKLM", base + r"\Tasks\Games", "Priority", winreg.REG_DWORD, 6),
        ("HKLM", base + r"\Tasks\Games", "Scheduling Category", winreg.REG_SZ, "High"),
        ("HKLM", base + r"\Tasks\Games", "SFIO Priority", winreg.REG_SZ, "High"),
        ("HKLM", r"SYSTEM\CurrentControlSet\Control\PriorityControl",
         "Win32PrioritySeparation", winreg.REG_DWORD, 38),
    ]
    _aplicar_pacote(
        estado,
        titulo="Prioridade do sistema para jogos (MMCSS)",
        descricao="Ajusta o MMCSS e o agendador da CPU para priorizar jogos e "
        "multimídia, deixando o aplicativo em primeiro plano mais responsivo.",
        riscos="Risco MÉDIO. Pode deixar tarefas em segundo plano um pouco mais "
        "lentas. Exige administrador.",
        valores=valores,
    )


def _acao_hags(estado: config.EstadoApp) -> None:
    valores = [
        ("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", winreg.REG_DWORD, 2),
    ]
    _aplicar_pacote(
        estado,
        titulo="Agendamento de GPU por hardware (HAGS)",
        descricao="Ativa o Hardware-Accelerated GPU Scheduling, que pode reduzir "
        "latência e melhorar o desempenho em GPUs e drivers compatíveis.",
        riscos="Risco MÉDIO. Depende de GPU/driver recentes; em alguns sistemas "
        "pode causar instabilidade ou quedas de FPS. EXIGE REINICIAR e administrador.",
        valores=valores,
        exige_reinicio=True,
    )


def _acao_nagle(estado: config.EstadoApp) -> None:
    from modulos.tweaks import rede  # reutiliza a detecção de interfaces ativas

    interfaces = rede._interfaces_ativas()
    guids = [i["guid"] for i in interfaces if i.get("guid")]
    if not guids:
        interface.erro("Nenhuma interface de rede ativa foi encontrada.")
        return
    valores: list[tuple[str, str, str, int, Any]] = []
    for guid in guids:
        sub = f"{_CAMINHO_INTERFACES}\\{guid}"
        valores.append(("HKLM", sub, "TcpAckFrequency", winreg.REG_DWORD, 1))
        valores.append(("HKLM", sub, "TCPNoDelay", winreg.REG_DWORD, 1))
    _aplicar_pacote(
        estado,
        titulo="Reduzir latência de rede (desativar Nagle)",
        descricao="Desativa o algoritmo de Nagle e o atraso de ACK nas interfaces "
        "ativas, reduzindo a latência (ping) em jogos online.",
        riscos="Risco MÉDIO. Em conexões muito lentas pode aumentar levemente o "
        "uso de banda. Exige administrador. Aplicado a: " + ", ".join(guids[:3])
        + ("..." if len(guids) > 3 else "") + ".",
        valores=valores,
    )


# ---------------------------------------------------------------------------
# Ações — ⚡ Desempenho geral
# ---------------------------------------------------------------------------
def _acao_plano_maximo(estado: config.EstadoApp) -> None:
    from modulos.tweaks import energia  # reutiliza leitura/extração de planos

    interface.cabecalho("Avançado · Plano 'Desempenho Máximo'", "Leia os riscos antes de aplicar.")
    interface.info(
        "Cria e ativa o plano oculto 'Desempenho Máximo' (Ultimate Performance) "
        "do Windows, que elimina economias de energia para resposta máxima."
    )
    interface.aviso(
        "⚠ Riscos:\nRisco MÉDIO. Aumenta consumo de energia e temperatura. "
        "NÃO é indicado para notebook na bateria.\n\n"
        "O plano anterior é guardado para o 'Desfazer'."
    )
    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: o plano seria criado e ativado. Nada foi alterado.")
        return
    if not interface.confirmar("Ativar o plano 'Desempenho Máximo' agora?", padrao=False):
        interface.info("Operação cancelada.")
        return
    if not seguranca.garantir_ponto_restauracao(estado):
        interface.info("Operação cancelada (sem ponto de restauração).")
        return

    guid_atual, nome_atual = energia._plano_ativo()
    codigo, saida, erro = seguranca.executar_comando(
        ["powercfg", "-duplicatescheme", _GUID_ULTIMATE], timeout=30
    )
    if codigo != 0:
        interface.erro(f"Não foi possível criar o plano (precisa de administrador?): {erro or codigo}")
        return
    novo = energia._extrair_guid(saida)
    if novo == "-":
        interface.erro("Não consegui identificar o GUID do novo plano.")
        return
    seguranca.executar_comando(
        ["powercfg", "-changename", novo, f"Desempenho Máximo ({config.NOME_APP})",
         "Plano de desempenho máximo criado pelo Otimizador PC"],
        timeout=20,
    )
    cod2, _s, err2 = seguranca.executar_comando(["powercfg", "-setactive", novo], timeout=20)
    if cod2 != 0:
        interface.erro(f"Plano criado, mas falha ao ativar: {err2 or cod2}")
        return
    seguranca.registrar_desfazer(
        "avancado", f"Voltar ao plano de energia: {nome_atual}", "plano_energia",
        {"guid_anterior": guid_atual},
    )
    seguranca.registrar_acao("avancado", "Plano 'Desempenho Máximo' ativado", True, f"de {nome_atual}")
    interface.sucesso("Plano 'Desempenho Máximo' criado e ativado.")


def _acao_power_throttling(estado: config.EstadoApp) -> None:
    valores = [
        ("HKLM", r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling",
         "PowerThrottlingOff", winreg.REG_DWORD, 1),
    ]
    _aplicar_pacote(
        estado,
        titulo="Desativar limitação de energia da CPU",
        descricao="Desliga o Power Throttling do Windows, que reduz a frequência "
        "da CPU para economizar energia — mantém a CPU sempre disponível.",
        riscos="Risco MÉDIO. Aumenta consumo e temperatura. NÃO recomendado em "
        "notebook na bateria. Exige administrador.",
        valores=valores,
    )


def _acao_kernel_ram(estado: config.EstadoApp) -> None:
    valores = [
        ("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
         "DisablePagingExecutive", winreg.REG_DWORD, 1),
    ]
    _aplicar_pacote(
        estado,
        titulo="Manter o kernel na memória RAM",
        descricao="Impede que componentes do kernel sejam enviados ao arquivo de "
        "paginação, melhorando a resposta em PCs com bastante RAM.",
        riscos="Risco MÉDIO. Recomendado apenas com 8 GB+ de RAM. Exige "
        "administrador e reiniciar.",
        valores=valores,
        exige_reinicio=True,
    )


def _acao_hibernacao(estado: config.EstadoApp) -> None:
    interface.cabecalho("Avançado · Desativar hibernação", "Leia os riscos antes de aplicar.")
    interface.info(
        "Desativa a hibernação e remove o arquivo 'hiberfil.sys', liberando "
        "vários GB de disco (normalmente próximo do tamanho da sua RAM)."
    )
    interface.aviso(
        "⚠ Riscos:\nRisco MÉDIO. Desativa também a 'Inicialização Rápida' do "
        "Windows e a opção de hibernar. Exige administrador."
    )
    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: executaria 'powercfg -h off'. Nada foi alterado.")
        return
    if not interface.confirmar("Desativar a hibernação agora?", padrao=False):
        interface.info("Operação cancelada.")
        return
    codigo, _s, err = seguranca.executar_comando(["powercfg", "-h", "off"], timeout=30)
    if codigo == 0:
        seguranca.registrar_desfazer(
            "avancado", "Reativar a hibernação do Windows", "comando",
            {"comando": ["powercfg", "-h", "on"], "ok_msg": "Hibernação reativada."},
        )
        seguranca.registrar_acao("avancado", "Hibernação desativada", True)
        interface.sucesso("Hibernação desativada e 'hiberfil.sys' removido.")
    else:
        interface.erro(f"Falha ao desativar a hibernação (precisa de administrador?): {err}")


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo das otimizações avançadas."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    acoes = {
        "modo_jogo": _acao_modo_jogo,
        "prioridade": _acao_prioridade_jogos,
        "hags": _acao_hags,
        "nagle": _acao_nagle,
        "plano_max": _acao_plano_maximo,
        "throttling": _acao_power_throttling,
        "kernel_ram": _acao_kernel_ram,
        "hibernacao": _acao_hibernacao,
    }

    while True:
        interface.cabecalho(
            "🔥 Otimizações AVANÇADAS",
            "A parte 'pesada': jogos e desempenho máximo — risco médio/alto.",
        )
        interface.aviso(
            "Aqui ficam ajustes AVANÇADOS para extrair o MÁXIMO de desempenho.\n"
            "Tudo é reversível (backup + 'Desfazer última alteração'), mas vários "
            "exigem ADMINISTRADOR e/ou REINICIAR o PC.\n"
            "Na dúvida, ligue o Modo Simulação no menu principal para só visualizar."
        )
        if not estado.eh_admin:
            interface.info(
                "Você não está como administrador. Ajustes em HKLM podem falhar com "
                "'acesso negado' — reabra o programa elevado para aplicá-los."
            )

        opcoes = [
            ("🎮  Modo Jogo + desativar Game DVR", "modo_jogo"),
            ("🎮  Prioridade do sistema para jogos (MMCSS)", "prioridade"),
            ("🎮  Agendamento de GPU por hardware (HAGS) — reinício", "hags"),
            ("🎮  Reduzir latência de rede (desativar Nagle)", "nagle"),
            interface.separador("Desempenho geral"),
            ("⚡  Plano de energia 'Desempenho Máximo'", "plano_max"),
            ("⚡  Desativar limitação de energia da CPU", "throttling"),
            ("🧠  Manter o kernel na memória RAM — reinício", "kernel_ram"),
            ("💽  Desativar hibernação (libera espaço em disco)", "hibernacao"),
            ("↩  Voltar", "voltar"),
        ]
        escolha = interface.menu_selecao("Qual otimização avançada deseja aplicar?", opcoes)
        if escolha in (None, "voltar"):
            return
        funcao = acoes.get(escolha)
        if funcao:
            funcao(estado)
            interface.pausar()
