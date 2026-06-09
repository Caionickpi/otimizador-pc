"""Tweak: gerenciamento de programas de inicialização.

Lista os programas que iniciam com o Windows (chaves Run do registro) e
permite desativá-los/reativá-los de forma 100% reversível.

Abordagem reversível: ao desativar, NÃO apagamos o item de vez — movemos seu
valor para uma chave de backup nossa
(``HKCU\\Software\\OtimizadorPC\\InicializacaoDesativada``). Reativar é apenas
mover de volta. Antes de qualquer mudança, exportamos a chave Run (.reg).
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

import config
from modulos import interface, seguranca

# winreg só existe no Windows; o import é tratado para não quebrar fora dele.
try:  # pragma: no cover
    import winreg  # type: ignore
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore


# Fontes de inicialização: (prefixo_reg, hive, subchave, rótulo_interno)
def _fontes() -> list[tuple[str, Any, str, str]]:
    if winreg is None:
        return []
    return [
        ("HKCU", winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU_Run"),
        ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM_Run"),
        ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM_Run32"),
    ]


def _fonte_por_rotulo(rotulo: str) -> Optional[tuple[str, Any, str, str]]:
    for fonte in _fontes():
        if fonte[3] == rotulo:
            return fonte
    return None


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def _listar_ativos() -> list[dict[str, Any]]:
    """Lista os itens de inicialização atualmente ativos nas chaves Run."""
    itens: list[dict[str, Any]] = []
    if winreg is None:
        return itens
    for prefixo, hive, subchave, rotulo in _fontes():
        try:
            with winreg.OpenKey(hive, subchave, 0, winreg.KEY_READ) as chave:
                indice = 0
                while True:
                    try:
                        nome, dado, tipo = winreg.EnumValue(chave, indice)
                    except OSError:
                        break
                    itens.append(
                        {
                            "nome": nome,
                            "comando": str(dado),
                            "tipo_reg": tipo,
                            "rotulo_fonte": rotulo,
                            "prefixo": prefixo,
                            "caminho_reg": f"{prefixo}\\{subchave}",
                        }
                    )
                    indice += 1
        except FileNotFoundError:
            continue
        except OSError as exc:
            seguranca.registrar(f"Falha ao ler {rotulo}: {exc}", logging.WARNING)
    return itens


def _listar_desativados() -> list[dict[str, Any]]:
    """Lista os itens que nós desativamos (guardados na chave de backup)."""
    desativados: list[dict[str, Any]] = []
    if winreg is None:
        return desativados
    for _prefixo, _hive, _subchave, rotulo in _fontes():
        backup_sub = f"{config.CHAVE_BACKUP_INICIALIZACAO}\\{rotulo}"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, backup_sub, 0, winreg.KEY_READ) as chave:
                indice = 0
                while True:
                    try:
                        nome, dado, tipo = winreg.EnumValue(chave, indice)
                    except OSError:
                        break
                    desativados.append(
                        {"nome": nome, "comando": str(dado), "tipo_reg": tipo, "rotulo_fonte": rotulo}
                    )
                    indice += 1
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return desativados


# ---------------------------------------------------------------------------
# Desativar / reativar
# ---------------------------------------------------------------------------
def _desativar_item(item: dict[str, Any], estado: config.EstadoApp) -> tuple[bool, str]:
    """Desativa um item movendo-o para a chave de backup."""
    if winreg is None:
        return False, "Registro do Windows indisponível."

    fonte = _fonte_por_rotulo(item["rotulo_fonte"])
    if not fonte:
        return False, "Fonte de inicialização desconhecida."
    _prefixo, hive, subchave, rotulo = fonte
    nome = item["nome"]

    # 1) Backup da chave Run inteira (.reg) por segurança extra.
    seguranca.backup_chave_registro(item["caminho_reg"], f"inicializacao_{rotulo}")

    try:
        # 2) Lê o valor atual (preservando o tipo).
        with winreg.OpenKey(hive, subchave, 0, winreg.KEY_READ) as origem:
            dado, tipo = winreg.QueryValueEx(origem, nome)

        # 3) Grava na chave de backup (sempre em HKCU, que não exige admin).
        backup_sub = f"{config.CHAVE_BACKUP_INICIALIZACAO}\\{rotulo}"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, backup_sub, 0, winreg.KEY_WRITE) as bkp:
            winreg.SetValueEx(bkp, nome, 0, tipo, dado)

        # 4) Remove da chave Run de origem (HKLM exige administrador).
        with winreg.OpenKey(hive, subchave, 0, winreg.KEY_SET_VALUE) as origem:
            winreg.DeleteValue(origem, nome)

    except PermissionError:
        return False, "Permissão negada. Itens em HKLM exigem executar como administrador."
    except OSError as exc:
        return False, f"Erro ao desativar: {exc}"

    seguranca.registrar_acao("inicializacao", f"Desativado '{nome}'", True, rotulo)
    seguranca.registrar_desfazer(
        "inicializacao",
        f"Reativar inicialização: {nome}",
        "inicializacao",
        {"rotulo_fonte": rotulo, "nome": nome},
    )
    return True, f"'{nome}' desativado (e guardado para reativar quando quiser)."


def _reativar_item(rotulo_fonte: str, nome: str) -> tuple[bool, str]:
    """Reativa um item movendo-o de volta da chave de backup para a Run."""
    if winreg is None:
        return False, "Registro do Windows indisponível."

    fonte = _fonte_por_rotulo(rotulo_fonte)
    if not fonte:
        return False, "Fonte de inicialização desconhecida."
    _prefixo, hive, subchave, rotulo = fonte
    backup_sub = f"{config.CHAVE_BACKUP_INICIALIZACAO}\\{rotulo}"

    try:
        # Lê o valor guardado no backup.
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, backup_sub, 0, winreg.KEY_READ) as bkp:
            dado, tipo = winreg.QueryValueEx(bkp, nome)

        # Reescreve na chave Run original (HKLM exige administrador).
        with winreg.CreateKeyEx(hive, subchave, 0, winreg.KEY_SET_VALUE) as origem:
            winreg.SetValueEx(origem, nome, 0, tipo, dado)

        # Remove do backup.
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, backup_sub, 0, winreg.KEY_SET_VALUE) as bkp:
            winreg.DeleteValue(bkp, nome)

    except FileNotFoundError:
        return False, f"Item '{nome}' não encontrado no backup."
    except PermissionError:
        return False, "Permissão negada. Itens em HKLM exigem executar como administrador."
    except OSError as exc:
        return False, f"Erro ao reativar: {exc}"

    seguranca.registrar_acao("inicializacao", f"Reativado '{nome}'", True, rotulo)
    return True, f"'{nome}' reativado na inicialização."


def reativar_por_dados(dados: dict[str, Any]) -> tuple[bool, str]:
    """Ponto de entrada usado pelo módulo de segurança para o 'Desfazer'."""
    return _reativar_item(dados.get("rotulo_fonte", ""), dados.get("nome", ""))


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Conduz o fluxo de gerenciamento de inicialização."""
    if winreg is None or not sys.platform.startswith("win"):
        interface.erro("Este recurso só está disponível no Windows.")
        return

    while True:
        interface.cabecalho(
            "Gerenciamento de inicialização",
            "Ative/desative programas que abrem junto com o Windows (reversível).",
        )

        ativos = _listar_ativos()
        desativados = _listar_desativados()

        tabela = interface.nova_tabela("Inicialização atual", ["#", "Programa", "Origem", "Comando"])
        for indice, item in enumerate(ativos, start=1):
            comando = item["comando"]
            comando_curto = comando if len(comando) <= 50 else comando[:47] + "..."
            tabela.add_row(
                str(indice),
                interface.escapar(item["nome"]),
                item["prefixo"],
                interface.escapar(comando_curto),
            )
        interface.imprimir_tabela(tabela)
        if desativados:
            interface.texto(f"Itens desativados por você: {len(desativados)}.", config.COR_AVISO)

        opcoes = [
            ("Desativar um programa da inicialização", "desativar"),
            ("Reativar um programa desativado", "reativar"),
            ("Voltar", "voltar"),
        ]
        escolha = interface.menu_selecao("O que deseja fazer?", opcoes)

        if escolha in (None, "voltar"):
            return
        if escolha == "desativar":
            _fluxo_desativar(ativos, estado)
        elif escolha == "reativar":
            _fluxo_reativar(desativados)


def _fluxo_desativar(ativos: list[dict[str, Any]], estado: config.EstadoApp) -> None:
    """Submenu para escolher e desativar itens de inicialização."""
    if not ativos:
        interface.info("Não há programas de inicialização nas chaves Run.")
        return

    opcoes: list[tuple[str, Any]] = [
        (f"{item['nome']}  ({item['prefixo']})", indice) for indice, item in enumerate(ativos)
    ]
    selecionados = interface.menu_multiplo(
        "Marque os programas para DESATIVAR (Espaço marca, Enter confirma):", opcoes
    )
    if not selecionados:
        interface.info("Nenhum item selecionado.")
        return

    escolhidos = [ativos[i] for i in selecionados]
    resumo = "\n".join(f"  • {item['nome']} ({item['prefixo']})" for item in escolhidos)
    interface.aviso(
        f"Serão desativados (de forma reversível):\n{resumo}\n\n"
        "Para reativar depois: menu de inicialização › 'Reativar', ou "
        "'Desfazer última alteração' no menu principal."
    )

    if estado.simulacao:
        interface.info("MODO SIMULAÇÃO: nada foi alterado.")
        return
    if not interface.confirmar("Confirmar a desativação destes itens?", padrao=False):
        interface.info("Operação cancelada.")
        return

    seguranca.garantir_ponto_restauracao(estado)
    for item in escolhidos:
        ok, msg = _desativar_item(item, estado)
        (interface.sucesso if ok else interface.erro)(msg)


def _fluxo_reativar(desativados: list[dict[str, Any]]) -> None:
    """Submenu para reativar itens que foram desativados."""
    if not desativados:
        interface.info("Não há itens desativados para reativar.")
        return

    opcoes: list[tuple[str, Any]] = [
        (f"{item['nome']}  ({item['rotulo_fonte']})", indice) for indice, item in enumerate(desativados)
    ]
    selecionados = interface.menu_multiplo("Marque os programas para REATIVAR:", opcoes)
    if not selecionados:
        interface.info("Nenhum item selecionado.")
        return

    for i in selecionados:
        item = desativados[i]
        ok, msg = _reativar_item(item["rotulo_fonte"], item["nome"])
        (interface.sucesso if ok else interface.erro)(msg)
