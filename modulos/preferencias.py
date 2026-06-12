"""Preferências persistentes do usuário (escalabilidade de uso).

Guarda escolhas simples em ``preferencias.json`` ao lado do executável, para
que o programa se adapte a cada usuário entre sessões — sem tocar no registro
do Windows. Leitura/gravação 100% tolerante a falhas: sem arquivo (ou com
arquivo corrompido), valem os padrões.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import config
from modulos import interface, seguranca

_ARQUIVO = config.PASTA_EXECUCAO / "preferencias.json"

# Padrões de fábrica. Toda preferência nova DEVE entrar aqui com seu padrão.
PADROES: dict[str, Any] = {
    # Checagem silenciosa de atualização ao abrir o programa.
    "verificar_atualizacao_inicio": True,
    # Dica "abra no Windows Terminal" na tela inicial (console clássico).
    "mostrar_dica_terminal": True,
}

_ROTULOS = {
    "verificar_atualizacao_inicio": "Verificar atualizações ao abrir",
    "mostrar_dica_terminal": "Mostrar dica do Windows Terminal na abertura",
}


def _carregar() -> dict[str, Any]:
    """Lê o arquivo de preferências (ou retorna vazio em qualquer falha)."""
    try:
        if _ARQUIVO.exists():
            with _ARQUIVO.open("r", encoding="utf-8") as fp:
                dados = json.load(fp)
            if isinstance(dados, dict):
                return dados
    except (OSError, json.JSONDecodeError) as exc:
        seguranca.registrar(f"[preferencias] falha ao ler: {exc}", logging.WARNING)
    return {}


def _gravar(dados: dict[str, Any]) -> bool:
    config.garantir_pastas()
    try:
        with _ARQUIVO.open("w", encoding="utf-8") as fp:
            json.dump(dados, fp, ensure_ascii=False, indent=2)
        return True
    except OSError as exc:
        seguranca.registrar(f"[preferencias] falha ao gravar: {exc}", logging.WARNING)
        return False


def obter(chave: str) -> Any:
    """Retorna o valor da preferência (ou o padrão de fábrica)."""
    return _carregar().get(chave, PADROES.get(chave))


def definir(chave: str, valor: Any) -> bool:
    """Define e persiste uma preferência."""
    dados = _carregar()
    dados[chave] = valor
    return _gravar(dados)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Liga/desliga as preferências do programa."""
    while True:
        interface.cabecalho("⚙️ Preferências", "Ajuste o programa do seu jeito (salvo entre sessões).")
        opcoes: list[tuple[str, Any]] = []
        for chave in PADROES:
            ligado = bool(obter(chave))
            # Texto puro: o questionary não interpreta markup do rich — se
            # colocássemos [verde]...[/], apareceria o código literal na tela.
            estado_txt = "● ligado" if ligado else "○ desligado"
            opcoes.append((f"{_ROTULOS.get(chave, chave)}  —  {estado_txt}", chave))
        opcoes.append(("↩  Voltar", "voltar"))

        escolha = interface.menu_selecao("Escolha uma preferência para alternar:", opcoes)
        if escolha in (None, "voltar"):
            return
        novo = not bool(obter(escolha))
        if definir(escolha, novo):
            interface.sucesso(
                f"'{_ROTULOS.get(escolha, escolha)}' agora está "
                f"{'LIGADO' if novo else 'DESLIGADO'}."
            )
        else:
            interface.erro("Não consegui salvar a preferência (sem permissão de escrita?).")
