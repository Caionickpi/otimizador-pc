"""Interface gráfica (GUI) premium do Otimizador PC — PySide6.

Esta camada é uma *casca* visual sobre o backend já existente: ela NÃO
reimplementa a lógica de otimização. Em vez disso, reaproveita 100% dos
módulos (``modulos/...``) por meio de uma "ponte" que substitui apenas as
primitivas de interação do módulo :mod:`modulos.interface` (confirmações,
menus, progresso e o console do ``rich``) por equivalentes gráficos.

Vantagens dessa abordagem:
    * Zero duplicação de regra de negócio — os mesmos fluxos ``menu(estado)``
      testados em produção rodam por trás da janela.
    * Toda a segurança (backups, ponto de restauração, desfazer) continua
      valendo, pois é o mesmo código.
    * A saída colorida do ``rich`` é preservada (exportada como HTML).

Ponto de entrada: :func:`gui.app.iniciar`.
"""

from __future__ import annotations
