"""Tweak: otimização de rede.

Oferece ações seguras de rede:
    * Liberar cache DNS (flush) — sempre seguro.
    * Renovar IP (release/renew) — derruba a conexão por instantes.
    * Resetar Winsock — pode exigir reinício do computador.
    * Definir DNS mais rápido (Cloudflare/Google) — guardando o DNS anterior
      para reverter.

O DNS anterior é lido do registro (valor NameServer da interface), o que
permite reverter com precisão para 'automático (DHCP)' ou para o DNS estático
que existia antes.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

import config
from modulos import interface, seguranca

try:  # pragma: no cover
    import winreg  # type: ignore
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore

try:  # pragma: no cover
    import wmi  # type: ignore
except Exception:  # noqa: BLE001
    wmi = None  # type: ignore

# DNS públicos conhecidos por serem rápidos e confiáveis.
_DNS_CONHECIDOS = {
    "cloudflare": ("1.1.1.1", "1.0.0.1"),
    "google": ("8.8.8.8", "8.8.4.4"),
    "quad9": ("9.9.9.9", "149.112.112.112"),
}

_CAMINHO_INTERFACES = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"


def _interfaces_ativas() -> list[dict[str, Any]]:
    """Lista as interfaces de rede conectadas (nome amigável + GUID + DNS atual)."""
    interfaces: list[dict[str, Any]] = []
    if wmi is None or not sys.platform.startswith("win"):
        return interfaces
    try:
        c = wmi.WMI()
        # Adaptadores realmente conectados (NetConnectionStatus == 2).
        for adaptador in c.Win32_NetworkAdapter(NetConnectionStatus=2):
            indice = getattr(adaptador, "Index", None)
            nome = getattr(adaptador, "NetConnectionID", None)
            if indice is None or not nome:
                continue
            cfgs = c.Win32_NetworkAdapterConfiguration(Index=indice)
            setting_id = getattr(cfgs[0], "SettingID", "") if cfgs else ""
            dns_atual = list(getattr(cfgs[0], "DNSServerSearchOrder", None) or []) if cfgs else []
            interfaces.append(
                {
                    "nome": nome,
                    "guid": setting_id,
                    "dns_atual": dns_atual,
                    "descricao": getattr(adaptador, "Name", nome),
                }
            )
    except Exception as exc:  # noqa: BLE001
        seguranca.registrar(f"Falha ao listar interfaces de rede: {exc}")
    return interfaces


def _dns_original(guid: str) -> Any:
    """Lê o DNS configurado no registro para reverter com precisão.

    Returns:
        Lista de endereços se havia DNS estático; a string 'dhcp' se estava
        em automático.
    """
    if winreg is None or not guid:
        return "dhcp"
    try:
        caminho = f"{_CAMINHO_INTERFACES}\\{guid}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, caminho, 0, winreg.KEY_READ) as chave:
            try:
                valor, _tipo = winreg.QueryValueEx(chave, "NameServer")
            except FileNotFoundError:
                return "dhcp"
        valor = (valor or "").strip()
        if not valor:
            return "dhcp"
        # NameServer pode separar por vírgula ou espaço.
        separador = "," if "," in valor else " "
        return [p for p in valor.split(separador) if p]
    except OSError:
        return "dhcp"


def _aplicar_dns(nome_if: str, primario: str, secundario: str) -> tuple[bool, str]:
    """Define DNS estático na interface (primário + secundário)."""
    codigo, _s, erro = seguranca.executar_comando(
        ["netsh", "interface", "ip", "set", "dns", f"name={nome_if}", "static", primario, "primary"],
        timeout=30,
    )
    if codigo != 0:
        if "negado" in erro.lower() or "denied" in erro.lower():
            return False, "Acesso negado — execute como administrador."
        return False, erro or "Falha ao definir o DNS primário."
    seguranca.executar_comando(
        ["netsh", "interface", "ip", "add", "dns", f"name={nome_if}", secundario, "index=2"],
        timeout=30,
    )
    return True, ""


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de otimização de rede."""
    if not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    while True:
        interface.cabecalho("Otimização de rede", "Ações seguras de rede e DNS.")
        opcoes = [
            ("Liberar cache DNS (flush) — seguro", "flush"),
            ("Renovar IP (release/renew) — cai a conexão por instantes", "renovar"),
            ("Resetar Winsock — pode exigir reiniciar o PC", "winsock"),
            ("Definir DNS mais rápido (Cloudflare/Google/Quad9)", "dns"),
            ("Voltar", "voltar"),
        ]
        escolha = interface.menu_selecao("O que deseja fazer?", opcoes)
        if escolha in (None, "voltar"):
            return
        if escolha == "flush":
            _acao_flush(estado)
        elif escolha == "renovar":
            _acao_renovar(estado)
        elif escolha == "winsock":
            _acao_winsock(estado)
        elif escolha == "dns":
            _acao_dns(estado)


def _acao_flush(estado: config.EstadoApp) -> None:
    """Libera o cache de DNS."""
    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: executaria 'ipconfig /flushdns'.")
        return
    codigo, _s, erro = seguranca.executar_comando(["ipconfig", "/flushdns"], timeout=30)
    if codigo == 0:
        seguranca.registrar_acao("rede", "Flush DNS", True)
        interface.sucesso("Cache de DNS liberado.")
    else:
        interface.erro(f"Falha ao liberar o cache de DNS: {erro}")


def _acao_renovar(estado: config.EstadoApp) -> None:
    """Renova o endereço IP (release + renew)."""
    interface.aviso("Sua conexão pode cair por alguns segundos durante a renovação.")
    if not interface.confirmar("Renovar o IP agora?", padrao=False):
        return
    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: executaria 'ipconfig /release' e '/renew'.")
        return
    seguranca.executar_comando(["ipconfig", "/release"], timeout=40)
    codigo, _s, erro = seguranca.executar_comando(["ipconfig", "/renew"], timeout=60)
    if codigo == 0:
        seguranca.registrar_acao("rede", "Renovar IP", True)
        interface.sucesso("IP renovado.")
    else:
        interface.erro(f"Falha ao renovar o IP: {erro}")


def _acao_winsock(estado: config.EstadoApp) -> None:
    """Reseta o catálogo Winsock."""
    interface.aviso(
        "Resetar o Winsock pode corrigir problemas de conexão, mas normalmente "
        "exige REINICIAR o computador para concluir."
    )
    if not interface.confirmar("Resetar o Winsock agora?", padrao=False):
        return
    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: executaria 'netsh winsock reset'.")
        return
    codigo, _s, erro = seguranca.executar_comando(["netsh", "winsock", "reset"], timeout=40)
    if codigo == 0:
        seguranca.registrar_acao("rede", "Reset Winsock", True)
        interface.sucesso("Winsock resetado. Reinicie o computador para concluir.")
    else:
        interface.erro(f"Falha ao resetar o Winsock: {erro}")


def _acao_dns(estado: config.EstadoApp) -> None:
    """Define um DNS público mais rápido, guardando o anterior para reverter."""
    interfaces = _interfaces_ativas()
    if not interfaces:
        interface.erro("Nenhuma interface de rede conectada foi encontrada.")
        return

    # Escolhe a interface.
    op_if = [(f"{i['nome']}  ({i['descricao']})", idx) for idx, i in enumerate(interfaces)]
    op_if.append(("Cancelar", None))
    idx_if = interface.menu_selecao("Em qual interface aplicar o DNS?", op_if)
    if idx_if is None:
        return
    alvo = interfaces[idx_if]

    # Escolhe o provedor de DNS.
    op_dns = [
        ("Cloudflare (1.1.1.1 / 1.0.0.1)", "cloudflare"),
        ("Google (8.8.8.8 / 8.8.4.4)", "google"),
        ("Quad9 (9.9.9.9 / 149.112.112.112)", "quad9"),
        ("Cancelar", None),
    ]
    provedor = interface.menu_selecao("Qual DNS usar?", op_dns)
    if provedor is None:
        return
    primario, secundario = _DNS_CONHECIDOS[provedor]

    dns_anterior = _dns_original(alvo["guid"])
    desc_anterior = "automático (DHCP)" if dns_anterior == "dhcp" else ", ".join(dns_anterior)
    interface.aviso(
        f"Interface: {alvo['nome']}\n"
        f"DNS atual: {desc_anterior}\n"
        f"Novo DNS: {primario} / {secundario}\n\n"
        "O DNS atual será guardado para você poder desfazer."
    )

    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: o DNS seria alterado. Nada foi feito.")
        return
    if not interface.confirmar("Aplicar o novo DNS?", padrao=False):
        interface.info("Operação cancelada.")
        return

    seguranca.garantir_ponto_restauracao(estado)
    ok, msg = _aplicar_dns(alvo["nome"], primario, secundario)
    if ok:
        seguranca.registrar_desfazer(
            "rede",
            f"Restaurar DNS da interface {alvo['nome']} ({desc_anterior})",
            "dns",
            {"interface": alvo["nome"], "dns_original": dns_anterior},
        )
        seguranca.registrar_acao("rede", f"DNS -> {provedor}", True, alvo["nome"])
        seguranca.executar_comando(["ipconfig", "/flushdns"], timeout=30)
        interface.sucesso(f"DNS da interface '{alvo['nome']}' definido para {primario} / {secundario}.")
    else:
        seguranca.registrar_acao("rede", "Alterar DNS", False, msg)
        interface.erro(msg)
