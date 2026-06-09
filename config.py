"""Constantes e configurações globais do Otimizador PC.

Este módulo centraliza nomes, versões, caminhos de pastas e o esquema de
cores usado em toda a interface. Também define a estrutura de estado da
aplicação (``EstadoApp``), compartilhada entre os módulos durante a execução.

Tudo aqui é seguro de importar em qualquer sistema operacional (não há
dependências de Windows neste arquivo), para que o programa consiga ao menos
iniciar e exibir mensagens amigáveis mesmo fora do ambiente-alvo.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Identidade do programa
# ---------------------------------------------------------------------------
NOME_APP: str = "Otimizador PC"
VERSAO_APP: str = "1.4.0"
DESCRICAO_APP: str = "Diagnóstico e ajustes seguros para Windows 10 e 11"

# Nome do executável distribuído (asset do release e alvo da auto-atualização).
NOME_EXECUTAVEL: str = "OtimizadorPC.exe"

# ---------------------------------------------------------------------------
# Atualização automática (GitHub Releases)
# ---------------------------------------------------------------------------
# O programa consulta a API PÚBLICA de releases do GitHub para saber se há uma
# versão mais nova e, quando empacotado (.exe), pode baixar e se atualizar
# sozinho. Isso exige que o repositório/releases sejam PÚBLICOS — em repositório
# privado a API responde 404 e o programa apenas avisa que não conseguiu checar.
GITHUB_OWNER: str = "Caionickpi"
GITHUB_REPO: str = "otimizador-pc"
URL_API_RELEASE_RECENTE: str = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
URL_PAGINA_RELEASES: str = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
# Quando empacotado pelo PyInstaller (sys.frozen), os recursos somente-leitura
# ficam em sys._MEIPASS, mas as pastas graváveis (logs/backups) precisam ficar
# ao lado do executável. Fora do empacotamento, tudo fica na raiz do projeto.
if getattr(sys, "frozen", False):  # pragma: no cover - só vale no .exe final
    PASTA_EXECUCAO: Path = Path(sys.executable).resolve().parent
    PASTA_RECURSOS: Path = Path(getattr(sys, "_MEIPASS", PASTA_EXECUCAO))
else:
    PASTA_EXECUCAO = Path(__file__).resolve().parent
    PASTA_RECURSOS = PASTA_EXECUCAO

PASTA_LOGS: Path = PASTA_EXECUCAO / "logs"
PASTA_BACKUPS: Path = PASTA_EXECUCAO / "backups"
PASTA_DADOS: Path = PASTA_RECURSOS / "dados"

ARQUIVO_SERVICOS_SEGUROS: Path = PASTA_DADOS / "servicos_seguros.json"
ARQUIVO_HISTORICO_DESFAZER: Path = PASTA_BACKUPS / "historico_desfazer.json"

# Chave de registro usada por nós para guardar itens de inicialização que o
# usuário desativou (abordagem reversível: movemos o valor para cá em vez de
# apagá-lo de vez).
CHAVE_BACKUP_INICIALIZACAO: str = r"Software\OtimizadorPC\InicializacaoDesativada"


def caminho_recurso(relativo: str) -> Path:
    """Resolve o caminho de um recurso somente-leitura empacotado.

    Funciona tanto em desenvolvimento quanto dentro do ``.exe`` gerado pelo
    PyInstaller.
    """
    return PASTA_RECURSOS / relativo


def garantir_pastas() -> None:
    """Cria as pastas graváveis (logs e backups) se ainda não existirem."""
    for pasta in (PASTA_LOGS, PASTA_BACKUPS):
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Sem permissão de escrita: o programa ainda funciona em modo
            # leitura; o módulo de segurança tratará a ausência de logs.
            pass


# ---------------------------------------------------------------------------
# Esquema de cores (estilos do rich)
#   verde   = seguro / concluído
#   amarelo = atenção
#   vermelho= cuidado / crítico
# ---------------------------------------------------------------------------
COR_OK: str = "green"
COR_AVISO: str = "yellow"
COR_ERRO: str = "red"
COR_INFO: str = "cyan"
COR_TITULO: str = "bold cyan"
COR_DESTAQUE: str = "bold white"
COR_NEUTRA: str = "white"

# Mapeia o nível de risco textual para uma cor consistente.
COR_POR_RISCO: dict[str, str] = {
    "baixo": COR_OK,
    "medio": COR_AVISO,
    "médio": COR_AVISO,
    "alto": COR_ERRO,
}

# Mapeia prioridade de recomendação para cor.
COR_POR_PRIORIDADE: dict[str, str] = {
    "alta": COR_ERRO,
    "media": COR_AVISO,
    "média": COR_AVISO,
    "baixa": COR_INFO,
}

# ---------------------------------------------------------------------------
# Limiares usados pela análise de recomendações
# ---------------------------------------------------------------------------
LIMIAR_RAM_BAIXA_GB: float = 8.0          # RAM <= este valor é considerada baixa
LIMIAR_DISCO_LIVRE_PCT: float = 15.0      # % livre abaixo disso => alerta
LIMIAR_DISCO_LIVRE_GB: float = 20.0       # GB livres abaixo disso => alerta
LIMIAR_MUITOS_STARTUP: int = 8           # acima disso, inicialização é "cheia"

# GUIDs dos planos de energia internos do Windows (estáveis entre versões).
GUID_PLANO_EQUILIBRADO: str = "381b4222-f694-41f0-9685-ff5bb260df2e"
GUID_PLANO_ALTO_DESEMPENHO: str = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
GUID_PLANO_ECONOMIA: str = "a1841308-3541-4fab-bc81-f71556f20b4a"


@dataclass
class EstadoApp:
    """Estado compartilhado durante uma sessão do programa.

    Atributos:
        perfil: dicionário com o diagnóstico completo da máquina.
        simulacao: quando ``True``, nenhuma alteração real é aplicada
            (modo dry-run / simulação).
        eh_admin: indica se o processo está elevado como administrador.
        ponto_restauracao_criado: garante que o ponto de restauração do
            sistema seja criado apenas uma vez por sessão.
        windows: ``True`` se estamos de fato rodando no Windows.
    """

    perfil: dict[str, Any] = field(default_factory=dict)
    simulacao: bool = False
    eh_admin: bool = False
    ponto_restauracao_criado: bool = False
    windows: bool = sys.platform.startswith("win")

    def diagnostico_pronto(self) -> bool:
        """Retorna ``True`` se o diagnóstico já foi coletado nesta sessão."""
        return bool(self.perfil)
