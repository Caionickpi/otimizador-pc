"""Gera o ícone do Otimizador PC (``dados/icone.ico`` + ``dados/icone.png``).

Desenho 100% por código (reprodutível, sem depender de arte externa): uma
engrenagem com gradiente ciano→azul — a marca do app — sobre um fundo escuro
arredondado, com um leve brilho. Renderizado em alta resolução e reduzido com
suavização para ficar nítido em todos os tamanhos do ``.ico``.

Uso:
    python dados/gerar_icone.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# Paleta da marca (mesma de config.py / gui/tema.py).
FUNDO_TOPO = (14, 20, 32)      # #0e1420
FUNDO_BASE = (8, 11, 16)       # #080b10
CIANO = (57, 208, 216)         # #39d0d8
AZUL = (31, 111, 235)          # #1f6feb

SS = 4                         # supersampling (anti-serrilhado)
TAM = 256                      # tamanho-base do ícone
G = TAM * SS                   # tela de render


def _gradiente_vertical(tam: int, topo: tuple[int, int, int], base: tuple[int, int, int]) -> Image.Image:
    """Cria um gradiente vertical (topo→base) em RGBA."""
    grad = Image.new("RGB", (1, tam))
    for y in range(tam):
        t = y / max(1, tam - 1)
        grad.putpixel((0, y), tuple(int(topo[i] + (base[i] - topo[i]) * t) for i in range(3)))
    return grad.resize((tam, tam)).convert("RGBA")


def _mascara_arredondada(tam: int, raio: int) -> Image.Image:
    """Máscara (L) de um quadrado de cantos arredondados."""
    m = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, tam - 1, tam - 1], radius=raio, fill=255)
    return m


def _poligono_engrenagem(cx: float, cy: float, r_tip: float, r_root: float,
                         dentes: int, frac_dente: float = 0.5) -> list[tuple[float, float]]:
    """Pontos de uma engrenagem (alternando ponta/raiz dos dentes)."""
    pts: list[tuple[float, float]] = []
    passos = dentes * 4
    for i in range(passos):
        ang = (i / passos) * 2 * math.pi
        fase = (i % 4) / 4.0
        r = r_tip if fase < frac_dente else r_root
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def gerar(destino: Path) -> None:
    # --- Fundo arredondado com gradiente escuro ---
    base = Image.new("RGBA", (G, G), (0, 0, 0, 0))
    fundo = _gradiente_vertical(G, FUNDO_TOPO, FUNDO_BASE)
    base.paste(fundo, (0, 0), _mascara_arredondada(G, int(G * 0.22)))

    cx = cy = G / 2

    # --- Brilho suave atrás da engrenagem (profundidade premium) ---
    brilho = Image.new("RGBA", (G, G), (0, 0, 0, 0))
    bd = ImageDraw.Draw(brilho)
    rb = G * 0.40
    bd.ellipse([cx - rb, cy - rb, cx + rb, cy + rb], fill=(57, 208, 216, 70))
    brilho = brilho.filter(ImageFilter.GaussianBlur(G * 0.05))
    base = Image.alpha_composite(base, brilho)

    # --- Engrenagem (máscara) ---
    masc = Image.new("L", (G, G), 0)
    md = ImageDraw.Draw(masc)
    md.polygon(_poligono_engrenagem(cx, cy, G * 0.36, G * 0.28, dentes=8), fill=255)
    md.ellipse([cx - G * 0.205, cy - G * 0.205, cx + G * 0.205, cy + G * 0.205], fill=255)
    # Furo central (vazado).
    md.ellipse([cx - G * 0.105, cy - G * 0.105, cx + G * 0.105, cy + G * 0.105], fill=0)

    # --- Preenche a engrenagem com o gradiente ciano→azul ---
    grad_marca = _gradiente_vertical(G, CIANO, AZUL)
    engrenagem = Image.new("RGBA", (G, G), (0, 0, 0, 0))
    engrenagem.paste(grad_marca, (0, 0), masc)
    base = Image.alpha_composite(base, engrenagem)

    # --- Reduz com suavização e salva PNG + ICO multi-tamanho ---
    final = base.resize((TAM, TAM), Image.LANCZOS)
    final.save(destino.with_suffix(".png"))
    final.save(
        destino.with_suffix(".ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Ícone gerado: {destino.with_suffix('.ico')} e {destino.with_suffix('.png')}")


if __name__ == "__main__":
    gerar(Path(__file__).resolve().parent / "icone")
