"""Tweak: gerenciamento de programas de inicialização.

Lista os programas que iniciam com o Windows e permite desativá-los e
reativá-los de forma 100% reversível. Cobre DUAS fontes (escalabilidade para
mais setups reais):
    * Chaves ``Run`` do registro (HKCU/HKLM/Wow6432Node).
    * Pastas de Inicialização (atalhos): a do usuário e a comum do sistema.

Abordagem reversível: ao desativar, NÃO apagamos o item de vez —
    * registro: o valor é movido para a chave de backup
      ``HKCU\\Software\\OtimizadorPC\\InicializacaoDesativada``;
    * pasta: o atalho é movido para ``backups\\inicializacao_pasta\\``.
Reativar é apenas mover de volta. Antes de mexer no registro, exportamos a
chave Run (.reg).
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
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
# Pastas de Inicialização (atalhos) — segunda fonte, além do registro
# ---------------------------------------------------------------------------
def _pastas_startup() -> list[tuple[str, Path]]:
    """Pastas de Inicialização existentes: (rótulo, caminho).

    ``PastaUser`` abre com a sua conta; ``PastaComum`` abre para todos os
    usuários (mexer nela costuma exigir administrador).
    """
    pastas: list[tuple[str, Path]] = []
    appdata = os.environ.get("APPDATA", "")
    programdata = os.environ.get("PROGRAMDATA", "")
    sufixo = Path("Microsoft") / "Windows" / "Start Menu" / "Programs" / "Startup"
    if appdata:
        pastas.append(("PastaUser", Path(appdata) / sufixo))
    if programdata:
        pastas.append(("PastaComum", Path(programdata) / sufixo))
    return [(rotulo, p) for rotulo, p in pastas if p.exists()]


def _pasta_por_rotulo(rotulo: str) -> Optional[Path]:
    for r, p in _pastas_startup():
        if r == rotulo:
            return p
    return None


def _pasta_backup_startup(rotulo: str) -> Path:
    """Pasta (nossa) onde os atalhos desativados ficam guardados."""
    return config.PASTA_BACKUPS / "inicializacao_pasta" / rotulo


def _listar_pastas_ativos() -> list[dict[str, Any]]:
    """Lista os atalhos presentes nas Pastas de Inicialização."""
    itens: list[dict[str, Any]] = []
    for rotulo, pasta in _pastas_startup():
        try:
            arquivos = sorted(pasta.iterdir())
        except OSError:
            continue
        for arq in arquivos:
            if not arq.is_file() or arq.name.lower() == "desktop.ini":
                continue
            itens.append(
                {
                    "nome": arq.name,
                    "comando": str(arq),
                    "rotulo_fonte": rotulo,
                    "prefixo": "Pasta",
                    "metodo": "pasta",
                }
            )
    return itens


def _desativar_pasta(item: dict[str, Any]) -> tuple[bool, str]:
    """Desativa um atalho movendo-o para a nossa pasta de backup."""
    nome = item["nome"]
    rotulo = item["rotulo_fonte"]
    pasta = _pasta_por_rotulo(rotulo)
    if pasta is None:
        return False, "Pasta de inicialização não encontrada."
    origem = pasta / nome
    destino_dir = _pasta_backup_startup(rotulo)
    try:
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / nome
        if destino.exists():
            destino = destino_dir / f"{datetime.now():%Y%m%d%H%M%S}_{nome}"
        shutil.move(str(origem), str(destino))
    except PermissionError:
        return False, "Permissão negada. A pasta comum exige executar como administrador."
    except (OSError, shutil.Error) as exc:
        return False, f"Erro ao desativar: {exc}"

    seguranca.registrar_acao("inicializacao", f"Desativado '{nome}' (pasta)", True, rotulo)
    seguranca.registrar_desfazer(
        "inicializacao",
        f"Reativar inicialização: {nome}",
        "inicializacao",
        {"metodo": "pasta", "rotulo_fonte": rotulo, "nome": nome,
         "origem": str(origem), "backup": str(destino)},
    )
    return True, f"'{nome}' desativado (atalho guardado para reativar quando quiser)."


def _listar_pastas_desativados() -> list[dict[str, Any]]:
    """Lista os atalhos que nós desativamos (guardados no backup)."""
    itens: list[dict[str, Any]] = []
    for rotulo, _pasta in _pastas_startup():
        backup = _pasta_backup_startup(rotulo)
        if not backup.exists():
            continue
        try:
            arquivos = sorted(backup.iterdir())
        except OSError:
            continue
        for arq in arquivos:
            if arq.is_file():
                itens.append({"nome": arq.name, "rotulo_fonte": rotulo,
                              "metodo": "pasta", "backup": str(arq)})
    return itens


def _reativar_pasta(dados: dict[str, Any]) -> tuple[bool, str]:
    """Reativa um atalho movendo-o de volta do backup para a pasta original."""
    nome = dados.get("nome", "")
    rotulo = dados.get("rotulo_fonte", "")
    backup = Path(dados.get("backup", "") or "")
    origem = Path(dados.get("origem", "") or "")
    if not origem.name:
        pasta = _pasta_por_rotulo(rotulo)
        if pasta is None:
            return False, "Pasta de inicialização não encontrada."
        # Remove um eventual prefixo de data/hora usado para evitar colisão.
        nome_original = nome.split("_", 1)[1] if nome[:14].isdigit() and "_" in nome else nome
        origem = pasta / nome_original
    if not backup.exists():
        return False, f"Backup do atalho '{nome}' não encontrado."
    if origem.exists():
        return False, f"Já existe um '{origem.name}' na pasta de inicialização."
    try:
        shutil.move(str(backup), str(origem))
    except PermissionError:
        return False, "Permissão negada. A pasta comum exige executar como administrador."
    except (OSError, shutil.Error) as exc:
        return False, f"Erro ao reativar: {exc}"
    seguranca.registrar_acao("inicializacao", f"Reativado '{origem.name}' (pasta)", True, rotulo)
    return True, f"'{origem.name}' reativado na inicialização."


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
                            "metodo": "registro",
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
    """Desativa um item (registro ou pasta) movendo-o para o backup."""
    if item.get("metodo") == "pasta":
        return _desativar_pasta(item)
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
    """Ponto de entrada usado pelo módulo de segurança para o 'Desfazer'.

    Compatível com os dois métodos: entradas antigas (registro, sem campo
    ``metodo``) continuam funcionando.
    """
    if dados.get("metodo") == "pasta":
        return _reativar_pasta(dados)
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

        ativos = _listar_ativos() + _listar_pastas_ativos()
        desativados = _listar_desativados() + _listar_pastas_desativados()

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
        if item.get("metodo") == "pasta":
            ok, msg = _reativar_pasta(item)
        else:
            ok, msg = _reativar_item(item["rotulo_fonte"], item["nome"])
        (interface.sucesso if ok else interface.erro)(msg)
