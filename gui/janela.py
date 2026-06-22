"""Janela principal do Otimizador PC (PySide6) — sem moldura, premium.

Estrutura visual:
    ┌──────────────────────────────────────────────────────────┐
    │  barra de título própria (logo · nome · min/max/fechar)    │
    ├───────────┬──────────────────────────────────────────────┤
    │  barra    │  cabeçalho (título + simulação + admin)       │
    │  lateral  ├──────────────────────────────────────────────┤
    │  (nav)    │  conteúdo: Painel ou página de Operação       │
    ├───────────┴──────────────────────────────────────────────┤
    │  rodapé (status + progresso + alça de redimensionar)      │
    └──────────────────────────────────────────────────────────┘

A janela é *frameless* com cantos arredondados (visual de produto pago); o
arraste/maximização usam as APIs nativas (preserva o "snap" do Windows). A
barra lateral espelha o menu da TUI; o "Painel" é nativo (anel de saúde
animado + indicadores). As demais opções abrem a página de "Operação", que
executa o fluxo do backend numa thread, mostrando a saída colorida do ``rich``
e abrindo diálogos nativos quando o backend pede uma escolha.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
import main as app_principal
from gui import tema
from gui.nucleo import Ponte, Trabalhador
from gui.widgets import AnelSaude, BarraTitulo, Cartao, EstatChip, ToggleSwitch
from modulos import elevacao, saude

# Estrutura do menu: (seção, [(rótulo, chave, subtítulo)])
_SECOES: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("Visão geral", [
        ("📊  Painel", "painel", "Saúde do PC e ações rápidas"),
        ("🔍  Diagnóstico", "diagnostico", "Hardware e sistema em detalhe"),
        ("💡  Recomendações", "recomendacoes", "Sugestões com base no seu PC"),
    ]),
    ("Ajustes", [
        ("🧹  Limpeza", "limpeza", "Remover arquivos temporários"),
        ("🚀  Inicialização", "inicializacao", "Programas que abrem com o Windows"),
        ("🛠  Serviços", "servicos", "Otimizar serviços do Windows"),
        ("🔋  Energia", "energia", "Plano de energia"),
        ("🌐  Rede", "rede", "Otimização de rede e DNS"),
        ("✨  Efeitos visuais", "visual", "Visual x desempenho"),
        ("💽  Disco", "disco", "Otimização de disco"),
    ]),
    ("Avançado", [
        ("🔥  Otimizações avançadas", "avancado", "Jogos e desempenho (risco médio)"),
        ("🖱  Input lag", "inputlag", "Mouse, teclado e monitor"),
        ("🎯  Otimizar por jogo", "otimizar_jogo", "Detecta jogos instalados"),
    ]),
    ("Premium", [
        ("⚡  Perfis (1 clique)", "perfis", "Pacotes prontos e seguros"),
        ("📈  Antes e depois", "desempenho", "Medir o ganho de desempenho"),
        ("📄  Relatório (HTML)", "relatorio", "Gerar relatório do PC"),
        ("🗓  Manutenção automática", "agendador", "Agendar limpeza periódica"),
    ]),
    ("Ferramentas", [
        ("↩  Desfazer última", "desfazer", "Reverter a última alteração"),
        ("⏮  Reverter tudo", "reverter_tudo", "Desfazer todas as alterações"),
        ("⚙  Preferências", "preferencias", "Ajustes do programa"),
        ("📜  Ver logs", "logs", "Histórico do dia"),
        ("🔄  Atualizações", "atualizacao", "Verificar nova versão"),
    ]),
]


class JanelaPrincipal(QMainWindow):
    """Janela principal: orquestra navegação, execução e exibição."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{config.NOME_APP}  ·  v{config.VERSAO_APP}")
        self.resize(1140, 760)
        self.setMinimumSize(960, 640)

        # Janela sem moldura + fundo translúcido (cantos arredondados suaves).
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.estado = config.EstadoApp()
        self.estado.eh_admin = elevacao.eh_administrador()
        self.ponte = Ponte(self)
        self._trabalhador: Optional[Trabalhador] = None
        self._alvos: dict[str, Callable[[], Any]] = self._montar_alvos()
        self._subtitulos: dict[str, str] = {}
        self._chave_atual = "painel"
        self._pix = self._carregar_pixmap()
        self._ja_apareceu = False
        self._maximizado = False
        self._geo_normal = None
        self._anim_pag: Optional[QPropertyAnimation] = None
        self._anim_janela: Optional[QPropertyAnimation] = None

        self._montar_ui()
        self.ponte.sig_saida.connect(self._anexar_console)
        self.ponte.sig_status.connect(self._atualizar_status)
        self._verificar_update_inicial()

    # ------------------------------------------------------------------ UI
    def _carregar_pixmap(self) -> QPixmap:
        try:
            caminho = config.caminho_recurso("dados/icone.ico")
            if caminho.exists():
                return QPixmap(str(caminho))
        except Exception:  # noqa: BLE001
            pass
        return QPixmap()

    def _montar_ui(self) -> None:
        self._frame = QFrame()
        self._frame.setObjectName("frameJanela")
        fl = QVBoxLayout(self._frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        # Barra de título própria.
        self._barra_titulo = BarraTitulo(self, config.NOME_APP, self._pix)
        self._barra_titulo.btn_min.clicked.connect(self.showMinimized)
        self._barra_titulo.btn_max.clicked.connect(self.alternar_maximizar)
        self._barra_titulo.btn_fechar.clicked.connect(self.close)
        fl.addWidget(self._barra_titulo)

        # Corpo: barra lateral + área principal.
        corpo = QWidget()
        ch = QHBoxLayout(corpo)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(0)
        ch.addWidget(self._montar_barra_lateral())
        ch.addWidget(self._montar_area_principal(), 1)
        fl.addWidget(corpo, 1)

        # Rodapé.
        fl.addWidget(self._montar_rodape())

        self.setCentralWidget(self._frame)

    def _montar_barra_lateral(self) -> QWidget:
        lateral = QWidget()
        lateral.setObjectName("barraLateral")
        lateral.setFixedWidth(252)
        v = QVBoxLayout(lateral)
        v.setContentsMargins(0, 16, 0, 12)
        v.setSpacing(2)

        # Marca: ícone + nome.
        topo = QHBoxLayout()
        topo.setContentsMargins(16, 0, 16, 0)
        topo.setSpacing(10)
        if not self._pix.isNull():
            logo = QLabel()
            logo.setPixmap(self._pix.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
            topo.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        marca = QLabel(config.NOME_APP)
        marca.setObjectName("marca")
        versao = QLabel(f"v{config.VERSAO_APP}  ·  Windows 10/11")
        versao.setObjectName("marcaVersao")
        col.addWidget(marca)
        col.addWidget(versao)
        topo.addLayout(col)
        topo.addStretch(1)
        v.addLayout(topo)
        v.addSpacing(6)

        # Navegação rolável.
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        interno = QWidget()
        nav = QVBoxLayout(interno)
        nav.setContentsMargins(0, 2, 0, 4)
        nav.setSpacing(1)

        self._grupo_nav = QButtonGroup(self)
        self._grupo_nav.setExclusive(True)
        for secao, itens in _SECOES:
            titulo = QLabel(secao.upper())
            titulo.setObjectName("tituloSecao")
            nav.addWidget(titulo)
            for rotulo, chave, subtitulo in itens:
                self._subtitulos[chave] = subtitulo
                botao = QPushButton(rotulo)
                botao.setObjectName("nav")
                botao.setCheckable(True)
                botao.setCursor(Qt.CursorShape.PointingHandCursor)
                botao.clicked.connect(lambda _c=False, k=chave: self._navegar(k))
                self._grupo_nav.addButton(botao)
                botao.setProperty("chave", chave)
                nav.addWidget(botao)
                if chave == "painel":
                    botao.setChecked(True)
        nav.addStretch(1)
        area.setWidget(interno)
        v.addWidget(area, 1)
        return lateral

    def _montar_area_principal(self) -> QWidget:
        area = QWidget()
        v = QVBoxLayout(area)
        v.setContentsMargins(26, 20, 26, 14)
        v.setSpacing(16)

        # Cabeçalho persistente.
        cab = QHBoxLayout()
        cab.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(2)
        self._titulo = QLabel("Painel")
        self._titulo.setObjectName("tituloPagina")
        self._subtitulo = QLabel("Saúde do PC e ações rápidas")
        self._subtitulo.setObjectName("subtituloPagina")
        col.addWidget(self._titulo)
        col.addWidget(self._subtitulo)
        cab.addLayout(col, 1)

        # Interruptor de simulação.
        caixa_sim = QWidget()
        ls = QHBoxLayout(caixa_sim)
        ls.setContentsMargins(0, 0, 0, 0)
        ls.setSpacing(8)
        rot_sim = QLabel("🧪  Simulação")
        rot_sim.setObjectName("rotuloSim")
        self._toggle_sim = ToggleSwitch()
        self._toggle_sim.setToolTip("Modo simulação: mostra o que seria feito, sem alterar nada.")
        self._toggle_sim.toggled.connect(self._alternar_simulacao)
        ls.addWidget(rot_sim)
        ls.addWidget(self._toggle_sim)
        cab.addWidget(caixa_sim, 0, Qt.AlignmentFlag.AlignVCenter)

        self._chip_admin = QPushButton()
        self._chip_admin.setObjectName("pill")
        self._chip_admin.setCursor(Qt.CursorShape.PointingHandCursor)
        self._atualizar_chip_admin()
        self._chip_admin.clicked.connect(self._reabrir_admin)
        cab.addWidget(self._chip_admin, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(cab)

        # Pilha: 0 = Painel, 1 = Operação.
        self._pilha = QStackedWidget()
        self._pilha.addWidget(self._montar_painel())
        self._pilha.addWidget(self._montar_operacao())
        v.addWidget(self._pilha, 1)
        return area

    def _montar_painel(self) -> QWidget:
        pag = QWidget()
        v = QVBoxLayout(pag)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(16)

        # Linha de cima: anel de saúde + ações rápidas.
        topo = QHBoxLayout()
        topo.setSpacing(16)

        cartao_saude = Cartao()
        ls = cartao_saude.layout_conteudo()
        t = QLabel("Saúde do PC")
        t.setObjectName("cartaoTitulo")
        ls.addWidget(t)
        linha_anel = QHBoxLayout()
        linha_anel.setSpacing(14)
        self._anel = AnelSaude()
        linha_anel.addWidget(self._anel)
        col_info = QVBoxLayout()
        col_info.setSpacing(6)
        self._saude_resumo = QLabel("Rode um diagnóstico para calcular a nota do seu PC.")
        self._saude_resumo.setObjectName("cartaoDesc")
        self._saude_resumo.setWordWrap(True)
        self._saude_resumo.setAlignment(Qt.AlignmentFlag.AlignTop)
        col_info.addWidget(self._saude_resumo)
        col_info.addStretch(1)
        linha_anel.addLayout(col_info, 1)
        ls.addLayout(linha_anel)
        topo.addWidget(cartao_saude, 3)

        cartao_acoes = Cartao()
        la = cartao_acoes.layout_conteudo()
        ta = QLabel("Ações rápidas")
        ta.setObjectName("cartaoTitulo")
        la.addWidget(ta)
        for rotulo, chave, primario in [
            ("🔍  Diagnosticar agora", "diagnostico", True),
            ("🧹  Limpeza de temporários", "limpeza", False),
            ("⚡  Perfis (1 clique)", "perfis", False),
            ("📄  Gerar relatório", "relatorio", False),
            ("🔄  Verificar atualização", "atualizacao", False),
        ]:
            b = QPushButton(rotulo)
            if primario:
                b.setObjectName("primario")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=chave: self._navegar(k, executar=True))
            la.addWidget(b)
        la.addStretch(1)
        topo.addWidget(cartao_acoes, 2)
        v.addLayout(topo)

        # Indicadores (KPIs) do hardware.
        grade = QGridLayout()
        grade.setSpacing(12)
        self._kpis = {
            "ram": EstatChip("Memória RAM", "🧠"),
            "disco": EstatChip("Espaço livre (pior disco)", "💽"),
            "ssd": EstatChip("Disco do sistema", "⚡"),
            "inicio": EstatChip("Programas na inicialização", "🚀"),
        }
        for i, chip in enumerate(self._kpis.values()):
            grade.addWidget(chip, 0, i)
        v.addLayout(grade)
        v.addStretch(1)
        return pag

    def _montar_operacao(self) -> QWidget:
        pag = QWidget()
        v = QVBoxLayout(pag)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        linha = QHBoxLayout()
        self._op_desc = QLabel("")
        self._op_desc.setObjectName("cartaoDesc")
        self._op_desc.setWordWrap(True)
        linha.addWidget(self._op_desc, 1)
        self._botao_exec = QPushButton("▶  Executar")
        self._botao_exec.setObjectName("primario")
        self._botao_exec.setCursor(Qt.CursorShape.PointingHandCursor)
        self._botao_exec.clicked.connect(self._executar_atual)
        linha.addWidget(self._botao_exec, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(linha)

        titulo_console = QLabel("ATIVIDADE")
        titulo_console.setObjectName("consoleTitulo")
        v.addWidget(titulo_console)

        self._console = QTextEdit()
        self._console.setObjectName("console")
        self._console.setReadOnly(True)
        v.addWidget(self._console, 1)
        return pag

    def _montar_rodape(self) -> QWidget:
        rod = QWidget()
        rod.setObjectName("rodape")
        rod.setFixedHeight(34)
        rl = QHBoxLayout(rod)
        rl.setContentsMargins(16, 0, 6, 0)
        rl.setSpacing(10)
        self._status_texto = QLabel("Pronto.")
        self._status_texto.setObjectName("statusTexto")
        self._status_barra = QProgressBar()
        self._status_barra.setMaximumWidth(220)
        self._status_barra.setVisible(False)
        rl.addWidget(self._status_texto, 1)
        rl.addWidget(self._status_barra)
        grip = QSizeGrip(rod)
        rl.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        return rod

    # ------------------------------------------------------- janela (frameless)
    def alternar_maximizar(self) -> None:
        """Maximiza/restaura usando a área DISPONÍVEL (nunca cobre a taskbar)."""
        if self._maximizado:
            self._maximizado = False
            if self._geo_normal is not None:
                self.setGeometry(self._geo_normal)
            self._aplicar_radius(False)
            self._barra_titulo.btn_max.setText("☐")
        else:
            self._geo_normal = self.geometry()
            tela = self.screen() or QApplication.primaryScreen()
            if tela is not None:
                self.setGeometry(tela.availableGeometry())
            self._maximizado = True
            self._aplicar_radius(True)
            self._barra_titulo.btn_max.setText("❐")

    def _aplicar_radius(self, maximizado: bool) -> None:
        self._frame.setProperty("maximizado", "true" if maximizado else "false")
        self._frame.style().unpolish(self._frame)
        self._frame.style().polish(self._frame)

    def showEvent(self, evento) -> None:  # noqa: N802
        super().showEvent(evento)
        if not self._ja_apareceu:
            self._ja_apareceu = True
            self._fade_janela()
            self._atualizar_painel()  # mostra "–" formatado já na abertura

    def _fade_janela(self) -> None:
        """Fade-in suave da janela ao abrir."""
        try:
            self.setWindowOpacity(0.0)
            a = QPropertyAnimation(self, b"windowOpacity", self)
            a.setDuration(280)
            a.setStartValue(0.0)
            a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.start()
            self._anim_janela = a
        except Exception:  # noqa: BLE001
            self.setWindowOpacity(1.0)

    def _fade_pagina(self) -> None:
        """Transição de fade ao trocar de página (removida ao terminar)."""
        try:
            efeito = QGraphicsOpacityEffect(self._pilha)
            self._pilha.setGraphicsEffect(efeito)
            a = QPropertyAnimation(efeito, b"opacity", self)
            a.setDuration(200)
            a.setStartValue(0.0)
            a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.finished.connect(lambda: self._pilha.setGraphicsEffect(None))
            a.start()
            self._anim_pag = a
        except Exception:  # noqa: BLE001
            self._pilha.setGraphicsEffect(None)

    # ------------------------------------------------------- navegação
    def _navegar(self, chave: str, executar: bool = False) -> None:
        for b in self._grupo_nav.buttons():
            b.setChecked(b.property("chave") == chave)

        self._chave_atual = chave
        self._titulo.setText(self._rotulo_limpo(chave))
        self._subtitulo.setText(self._subtitulos.get(chave, ""))

        if chave == "painel":
            self._pilha.setCurrentIndex(0)
            self._fade_pagina()
            return

        self._pilha.setCurrentIndex(1)
        self._fade_pagina()
        self._op_desc.setText(self._subtitulos.get(chave, ""))
        self._console.clear()
        self._console.setHtml(
            f"<div style='color:{tema.TEXTO_FRACO}'>Clique em <b>Executar</b> "
            f"para iniciar. Nada é alterado sem a sua confirmação.</div>"
        )
        if executar:
            self._executar_atual()

    def _rotulo_limpo(self, chave: str) -> str:
        for _secao, itens in _SECOES:
            for rotulo, c, _sub in itens:
                if c == chave:
                    return rotulo.split("  ", 1)[-1].strip()
        return chave

    # ------------------------------------------------------- execução
    def _executar_atual(self) -> None:
        self._executar(self._chave_atual)

    def _executar(self, chave: str) -> None:
        alvo = self._alvos.get(chave)
        if alvo is None:
            return
        self._pilha.setCurrentIndex(1)
        self._botao_exec.setEnabled(False)
        self._botao_exec.setText("⏳  Executando...")
        self._iniciar_worker(alvo, self._rotulo_limpo(chave), chave)

    def _iniciar_worker(self, alvo: Callable[[], Any], rotulo: str, chave: str = "") -> bool:
        """Inicia uma tarefa no worker. Retorna ``False`` se já houver uma rodando."""
        if self._trabalhador is not None and self._trabalhador.isRunning():
            self._status_texto.setText("Aguarde a tarefa atual terminar...")
            self._botao_exec.setEnabled(True)
            self._botao_exec.setText("▶  Executar")
            return False
        self._status_barra.setVisible(True)
        self._status_barra.setRange(0, 0)
        self._trabalhador = Trabalhador(self.ponte, alvo, rotulo)
        self._trabalhador.sig_fim.connect(lambda _r, k=chave: self._tarefa_terminou(k))
        self._trabalhador.start()
        return True

    def _tarefa_terminou(self, chave: str) -> None:
        self._botao_exec.setEnabled(True)
        self._botao_exec.setText("▶  Executar novamente")
        self._status_barra.setVisible(False)
        self._status_texto.setText("Concluído.")
        if chave in ("diagnostico", "recomendacoes", "limpeza", "perfis") and self.estado.diagnostico_pronto():
            self._atualizar_painel()

    # ------------------------------------------------------- alvos (backend)
    def _montar_alvos(self) -> dict[str, Callable[[], Any]]:
        e = self.estado
        from modulos import agendador, atualizacao, desempenho, preferencias, recomendacoes, relatorio
        from modulos.tweaks import (
            avancado, disco, energia, inicializacao, inputlag, limpeza,
            otimizar_jogo, perfis, rede, servicos, visual,
        )
        return {
            "diagnostico": lambda: app_principal._acao_diagnostico(e),
            "recomendacoes": lambda: app_principal._acao_recomendacoes(e),
            "limpeza": lambda: limpeza.menu(e),
            "inicializacao": lambda: inicializacao.menu(e),
            "servicos": lambda: servicos.menu(e),
            "energia": lambda: energia.menu(e),
            "rede": lambda: rede.menu(e),
            "visual": lambda: visual.menu(e),
            "disco": lambda: disco.menu(e),
            "avancado": lambda: avancado.menu(e),
            "inputlag": lambda: inputlag.menu(e),
            "otimizar_jogo": lambda: otimizar_jogo.menu(e),
            "saude": lambda: saude.menu(e),
            "perfis": lambda: perfis.menu(e),
            "desempenho": lambda: desempenho.menu(e),
            "relatorio": lambda: relatorio.menu(e),
            "agendador": lambda: agendador.menu(e),
            "desfazer": lambda: app_principal._acao_desfazer(e),
            "reverter_tudo": lambda: app_principal._acao_reverter_tudo(e),
            "preferencias": lambda: preferencias.menu(e),
            "logs": lambda: app_principal._acao_ver_logs(e),
            "atualizacao": lambda: atualizacao.verificar(e),
        }

    # ------------------------------------------------------- painel/saúde
    def _atualizar_painel(self) -> None:
        perfil = self.estado.perfil
        if not perfil:
            return
        try:
            res = saude.calcular(perfil)
        except Exception:  # noqa: BLE001
            return
        self._anel.definir(res["pontuacao"], res["nota"])
        problemas = res.get("problemas", [])
        if problemas:
            itens = "<br>".join(f"•&nbsp; {p['fator']}" for p in problemas[:4])
            self._saude_resumo.setText(f"<b>O que está custando pontos:</b><br>{itens}")
        else:
            self._saude_resumo.setText("Seu PC está em ótima forma! 🎉")
        self._atualizar_kpis(perfil)

    def _atualizar_kpis(self, perfil: dict[str, Any]) -> None:
        from modulos.interface import formatar_bytes

        mem = perfil.get("memoria", {})
        self._kpis["ram"].definir_valor(formatar_bytes(mem.get("total", 0)))

        discos = perfil.get("armazenamento", []) or []
        if discos:
            pior = min(discos, key=lambda d: 100 - float(d.get("percent", 0) or 0))
            self._kpis["disco"].definir_valor(f"{100 - float(pior.get('percent', 0) or 0):.0f}%")
            tem_ssd = any("SSD" in (d.get("tipo", "") or "").upper() for d in discos)
            self._kpis["ssd"].definir_valor("SSD ✓" if tem_ssd else "HDD")
        self._kpis["inicio"].definir_valor(str(len(perfil.get("inicializacao", []) or [])))

    # ------------------------------------------------------- estado/topo
    def _atualizar_chip_admin(self) -> None:
        if self.estado.eh_admin:
            self._chip_admin.setText("✔  Administrador")
            self._chip_admin.setToolTip("O programa está elevado: todos os ajustes podem ser aplicados.")
            self._chip_admin.setEnabled(False)
        else:
            self._chip_admin.setText("●  Usuário comum — elevar")
            self._chip_admin.setToolTip("Clique para reabrir como administrador (UAC).")

    def _reabrir_admin(self) -> None:
        if self.estado.eh_admin:
            return
        if elevacao.reabrir_como_administrador():
            self.close()

    def _alternar_simulacao(self, ligado: bool) -> None:
        self.estado.simulacao = ligado
        self._status_texto.setText(
            "Modo simulação LIGADO — nada será alterado de verdade." if ligado else "Pronto."
        )

    # ------------------------------------------------------- console/status
    def _anexar_console(self, html: str) -> None:
        self._console.moveCursor(QTextCursor.MoveOperation.End)
        self._console.insertHtml(f"<pre style='margin:0;white-space:pre-wrap'>{html}</pre>")
        self._console.moveCursor(QTextCursor.MoveOperation.End)
        barra = self._console.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _atualizar_status(self, texto: str, pct: int) -> None:
        if not texto:
            self._status_texto.setText("Pronto.")
            self._status_barra.setVisible(False)
            return
        self._status_texto.setText(texto)
        self._status_barra.setVisible(True)
        if pct < 0:
            self._status_barra.setRange(0, 0)
        else:
            self._status_barra.setRange(0, 100)
            self._status_barra.setValue(pct)

    # ------------------------------------------------------- updates
    def _verificar_update_inicial(self) -> None:
        try:
            from modulos import atualizacao, preferencias

            if not preferencias.obter("verificar_atualizacao_inicio"):
                return
        except Exception:  # noqa: BLE001
            return
        self._iniciar_worker(
            lambda: atualizacao.verificar(self.estado, no_inicio=True),
            "Verificar atualizações",
        )

    def closeEvent(self, evento) -> None:  # noqa: N802
        if self._trabalhador is not None and self._trabalhador.isRunning():
            self._trabalhador.wait(2000)
        super().closeEvent(evento)
