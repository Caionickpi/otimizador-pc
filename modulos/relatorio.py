"""Premium: relatório exportável em HTML.

Gera um arquivo HTML autônomo (tema escuro, sem dependências externas) com o
diagnóstico, a pontuação de saúde e as recomendações — pronto para guardar,
imprimir ou enviar para alguém. É só leitura: não altera o sistema.
"""

from __future__ import annotations

import html
import logging
import webbrowser
from datetime import datetime
from typing import Any

import config
from modulos import interface, recomendacoes, saude, seguranca


def _linha(rotulo: str, valor: str) -> str:
    return f"<tr><th>{html.escape(rotulo)}</th><td>{html.escape(str(valor))}</td></tr>"


def montar_html(perfil: dict[str, Any]) -> str:
    """Monta o HTML completo do relatório a partir do perfil coletado."""
    sistema = perfil.get("sistema", {})
    cpu = perfil.get("cpu", {})
    mem = perfil.get("memoria", {})
    discos = perfil.get("armazenamento", []) or []
    energia = perfil.get("energia", {})
    res_saude = saude.calcular(perfil)
    recs = recomendacoes.gerar_recomendacoes(perfil)
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Mapeia a cor do tema (rich) para um HEX seguro de CSS.
    cor_nota = {"A": "#3fb950", "B": "#3fb950", "C": "#d29922", "D": "#d29922", "F": "#f85149"}.get(
        res_saude["nota"], "#58a6ff"
    )

    sis_rows = "".join([
        _linha("Sistema", sistema.get("edicao", "-")),
        _linha("Versão / Build", f"{sistema.get('release', '-')} (build {sistema.get('build', '-')})"),
        _linha("Processador", cpu.get("modelo", "-")),
        _linha("Núcleos", f"{cpu.get('nucleos_fisicos', '-')} físicos / {cpu.get('nucleos_logicos', '-')} lógicos"),
        _linha("Memória RAM", f"{interface.formatar_bytes(mem.get('total', 0))} ({mem.get('velocidade_mhz', '-')} MHz)"),
        _linha("Tipo de máquina", "Notebook" if energia.get("eh_portatil", energia.get("tem_bateria")) else "Desktop"),
        _linha("Plano de energia", energia.get("plano_ativo", "-")),
        _linha("Ligado há", sistema.get("uptime", "-")),
    ])

    disco_rows = "".join(
        f"<tr><td>{html.escape(d.get('unidade', '-'))}</td>"
        f"<td>{html.escape(d.get('tipo', '-'))}</td>"
        f"<td>{interface.formatar_bytes(d.get('total', 0))}</td>"
        f"<td>{interface.formatar_bytes(d.get('livre', 0))}</td>"
        f"<td>{d.get('percent', 0):.0f}%</td>"
        f"<td>{html.escape(d.get('saude', '-'))}</td></tr>"
        for d in discos
    ) or "<tr><td colspan='6'>Sem dados de disco.</td></tr>"

    problemas = "".join(
        f"<li><b>{html.escape(p['fator'])}</b> — {html.escape(p['detalhe'])}</li>"
        for p in res_saude["problemas"]
    ) or "<li>Nenhum problema relevante. 🎉</li>"

    cor_prio = {"alta": "#f85149", "media": "#d29922", "baixa": "#58a6ff"}
    rec_rows = "".join(
        f"<tr><td><span class='tag' style='background:{cor_prio.get(r['prioridade'], '#58a6ff')}'>"
        f"{html.escape(r['prioridade'].upper())}</span></td>"
        f"<td><b>{html.escape(r['titulo'])}</b><br><span class='dim'>{html.escape(r['descricao'])}</span></td>"
        f"<td>{html.escape(r['impacto'])}</td></tr>"
        for r in recs
    ) or "<tr><td colspan='3'>Sem recomendações.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório — {config.NOME_APP}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background:#0d1117; color:#c9d1d9;
         margin:0; padding:0 16px 48px; }}
  .wrap {{ max-width: 900px; margin: 0 auto; }}
  header {{ text-align:center; padding:32px 0 8px; }}
  header h1 {{ margin:0; color:#fff; }}
  header .sub {{ color:#6e7681; }}
  .score {{ display:flex; align-items:center; justify-content:center; gap:24px;
            background:#161b22; border:1px solid #30363d; border-radius:16px; padding:24px; margin:24px 0; }}
  .score .num {{ font-size:64px; font-weight:800; color:{cor_nota}; line-height:1; }}
  .score .grade {{ font-size:20px; color:{cor_nota}; font-weight:700; }}
  h2 {{ color:#58a6ff; border-bottom:1px solid #30363d; padding-bottom:6px; margin-top:36px; }}
  table {{ width:100%; border-collapse:collapse; background:#161b22; border-radius:12px; overflow:hidden; }}
  th, td {{ text-align:left; padding:10px 14px; border-bottom:1px solid #21262d; vertical-align:top; }}
  th {{ color:#8b949e; font-weight:600; width:34%; }}
  td .dim, .dim {{ color:#8b949e; font-size:.92em; }}
  .tag {{ color:#fff; padding:2px 10px; border-radius:999px; font-size:.78em; font-weight:700; }}
  ul {{ background:#161b22; border:1px solid #30363d; border-radius:12px; padding:16px 16px 16px 32px; }}
  li {{ margin:6px 0; }}
  footer {{ text-align:center; color:#6e7681; margin-top:40px; font-size:.85em; }}
</style></head>
<body><div class="wrap">
  <header>
    <h1>⚙ {config.NOME_APP}</h1>
    <div class="sub">Relatório do computador · {agora} · v{config.VERSAO_APP}</div>
  </header>

  <div class="score">
    <div><div class="num">{res_saude['pontuacao']}</div></div>
    <div>
      <div class="grade">Nota {res_saude['nota']}</div>
      <div class="dim">Pontuação de saúde (0–100)</div>
    </div>
  </div>

  <h2>🖥 Sistema</h2>
  <table>{sis_rows}</table>

  <h2>💽 Armazenamento</h2>
  <table>
    <tr><th>Unidade</th><th>Tipo</th><th>Total</th><th>Livre</th><th>Uso</th><th>Saúde</th></tr>
    {disco_rows}
  </table>

  <h2>🔧 O que está custando pontos</h2>
  <ul>{problemas}</ul>

  <h2>💡 Recomendações</h2>
  <table>
    <tr><th>Prioridade</th><th>Recomendação</th><th>Impacto</th></tr>
    {rec_rows}
  </table>

  <footer>Gerado pelo {config.NOME_APP}. Diagnóstico somente-leitura — nada foi alterado.</footer>
</div></body></html>"""


def gerar(perfil: dict[str, Any]) -> "tuple[bool, str]":
    """Gera o arquivo HTML do relatório. Retorna (sucesso, caminho_ou_erro)."""
    config.garantir_pastas()
    nome = f"relatorio_otimizadorpc_{datetime.now():%Y-%m-%d_%H-%M-%S}.html"
    destino = config.PASTA_EXECUCAO / nome
    try:
        destino.write_text(montar_html(perfil), encoding="utf-8")
    except OSError as exc:
        seguranca.registrar(f"[relatorio] falha ao gerar: {exc}", logging.WARNING)
        return False, str(exc)
    return True, str(destino)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
def menu(estado: config.EstadoApp) -> None:
    """Gera o relatório HTML (coleta o diagnóstico se necessário) e oferece abrir."""
    from modulos import diagnostico

    interface.cabecalho("📄 Relatório do computador (HTML)",
                        "Um arquivo bonito com diagnóstico, nota e recomendações.")
    if not estado.diagnostico_pronto():
        interface.info("Preciso do diagnóstico para montar o relatório (é rápido).")
        if not interface.confirmar("Coletar o diagnóstico agora?", padrao=True):
            return
        estado.perfil = diagnostico.coletar_perfil()

    ok, resultado = gerar(estado.perfil)
    if not ok:
        interface.erro(f"Não consegui gerar o relatório: {resultado}")
        return
    seguranca.registrar_acao("relatorio", "Relatório HTML gerado", True, resultado)
    interface.sucesso(f"Relatório gerado em:\n{resultado}")
    if interface.confirmar("Abrir o relatório no navegador agora?", padrao=True):
        try:
            webbrowser.open(f"file:///{resultado}")
        except Exception:  # noqa: BLE001
            interface.texto(resultado, config.COR_INFO)
