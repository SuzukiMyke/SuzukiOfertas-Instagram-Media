"""Camadas estáticas Pillow (PNG com alfa) e diagramação dentro da margem segura.

Cada camada guarda geometria, janela de tempo e animação; o FFmpeg aplica o
movimento. A quebra de linha usa a largura REAL da fonte (``getlength``).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from . import brand
from .motion import slide_offsets
from .rules import resolve_buttons, scene_label


@dataclass
class Layer:
    name: str
    path: str
    x: int
    y: int
    w: int
    h: int
    t_in: float
    t_out: float            # instante local em que a camada termina de sumir (ou fim do segmento)
    anim: str = "none"      # slide_up | slide_left | fade | none | static
    slide_px: int = 0
    fade_in: float = 0.0
    fade_out: float = 0.0
    role: str = "body"      # title | body | label | logo
    font_px: int = 0
    text: str = ""
    contrast: float | None = None
    meta: dict = field(default_factory=dict)

    def motion_bbox(self) -> tuple[int, int, int, int]:
        """Retângulo que cobre a posição inicial e final da animação."""
        dx, dy = slide_offsets(self.anim, self.slide_px)
        return self.x, self.y, self.x + self.w + max(dx, 0), self.y + self.h + max(dy, 0)

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------ contraste
def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = rgb[:3]
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def blend(fg, bg, alpha: float):
    return tuple(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg[:3], bg[:3]))


def worst_contrast(text_rgb, panel_rgb, panel_alpha: float, bg_extremes) -> float:
    """Pior contraste do texto sobre o painel semitransparente aplicado a qualquer fundo."""
    vals = []
    for bg in bg_extremes:
        eff = blend(panel_rgb, bg, panel_alpha) if panel_rgb is not None else bg
        vals.append(contrast_ratio(text_rgb, eff))
    return min(vals)


def bg_extremes(img: Image.Image) -> list[tuple[int, int, int]]:
    """Pixels mais escuro e mais claro (por luminância aproximada) da imagem de fundo."""
    small = img.convert("RGB").resize((108, 192))
    raw = small.tobytes()
    px = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
    lum = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px]
    return [px[lum.index(min(lum))], px[lum.index(max(lum))]]


# ------------------------------------------------------------ texto
def wrap(text: str, fnt, max_w: float) -> list[str]:
    """Quebra por palavras usando a largura real; palavra longa demais é quebrada por caractere."""
    lines: list[str] = []
    cur = ""
    # travessão/meia-risca ficam presos à palavra anterior (nunca começam linha)
    text = re.sub(r"\s+([—–])", "\u00a0\\1", text.strip())
    for word in [w for w in re.split(r"[ \t\n]+", text) if w]:
        cand = f"{cur} {word}".strip()
        if fnt.getlength(cand) <= max_w:
            cur = cand
            continue
        if cur:
            lines.append(cur)
        if fnt.getlength(word) <= max_w:
            cur = word
        else:  # quebra forçada
            piece = ""
            for ch in word:
                if fnt.getlength(piece + ch) > max_w and piece:
                    lines.append(piece)
                    piece = ch
                else:
                    piece += ch
            cur = piece
    if cur:
        lines.append(cur)
    return lines


def wrap_balanced(text: str, fnt, max_w: float) -> list[str]:
    """Mesmo número de linhas de ``wrap``, mas com larguras equilibradas (evita palavra órfã)."""
    lines = wrap(text, fnt, max_w)
    if len(lines) < 2:
        return lines
    lo, hi = max(fnt.getlength(w) for w in " ".join(lines).split(" ")), max_w
    best = lines
    for _ in range(14):  # busca binária pela menor largura que mantém o nº de linhas
        mid = (lo + hi) / 2
        cand = wrap(text, fnt, mid)
        if len(cand) <= len(lines):
            best, hi = cand, mid
        else:
            lo = mid
    return best


@dataclass
class Run:
    """Uma linha lógica de texto (antes da quebra) com fonte e cor próprias."""
    text: str
    font_spec: str
    size: int
    color: tuple


def text_block(runs: list[Run], max_w: int, panel_rgb, panel_alpha: float, radius: int,
               pad: tuple[int, int], align: str = "left", line_gap: float = 0.18, min_w: int = 0):
    """Renderiza bloco (painel opcional + linhas). Retorna (imagem, linhas_quebradas)."""
    pad_x, pad_y = pad
    inner = max_w - 2 * pad_x
    rows = []  # (texto, fonte, cor, altura_linha, ascent)
    for r in runs:
        f = brand.font(r.font_spec, r.size)
        asc, desc = f.getmetrics()
        for ln in wrap_balanced(r.text, f, inner):
            rows.append((ln, f, r.color, asc + desc, asc))
    widths = [f.getlength(t) for t, f, *_ in rows]
    content_w = max(int(max(widths) + 0.999) if widths else 0, min_w - 2 * pad_x)
    gaps = [round(rows[i][3] * line_gap) for i in range(len(rows) - 1)]
    content_h = sum(r[3] for r in rows) + sum(gaps)
    w, h = content_w + 2 * pad_x, content_h + 2 * pad_y
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if panel_rgb is not None and panel_alpha > 0:
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                            fill=tuple(panel_rgb) + (round(255 * panel_alpha),))
    y = pad_y
    for i, (t, f, col, lh, _asc) in enumerate(rows):
        lw = widths[i]
        x = pad_x + (content_w - lw) / 2 if align == "center" else pad_x
        d.text((x, y), t, font=f, fill=tuple(col) + (255,))
        y += lh + (gaps[i] if i < len(gaps) else 0)
    return img, [r[0] for r in rows]


# ------------------------------------------------------------ diagramação
class Layout:
    """Fábrica de camadas para um segmento (gera PNGs em ``work_dir``)."""

    def __init__(self, cfg: dict, work_dir: Path, seg, bg_img: Image.Image | None):
        self.cfg = cfg
        self.seg = seg
        self.work = Path(work_dir)
        self.work.mkdir(parents=True, exist_ok=True)
        o, sz = cfg["output"], cfg["safe_zone"]
        self.W, self.H = o["width"], o["height"]
        self.L, self.T = sz["left"], sz["top"]
        self.R, self.B = self.W - sz["right"], self.H - sz["bottom"]
        self.CW = self.R - self.L
        self.CX = (self.L + self.R) // 2  # centro da área segura (margens laterais assimétricas)
        th = cfg["theme"]
        self.sizes = th["sizes"]
        self.fonts = th["font"]
        self.panel = th["panel"]
        self.anim = cfg["animation"]
        self.extremes = bg_extremes(bg_img) if bg_img is not None else None
        self.layers: list[Layer] = []
        self.errors: list[str] = []

    def c(self, name):
        return brand.color(self.cfg, name)

    def save(self, img: Image.Image, name: str) -> str:
        p = self.work / f"{self.seg.key}__{name}.png"
        img.save(p, optimize=False, compress_level=6)
        return str(p)

    def add_block(self, name, runs, x, y, *, max_w=None, panel=None, panel_alpha=None, role="body",
                  t_in=0.0, t_out=None, anim="none", align="left", anchor="topleft", pad=None, radius=None, min_w=0):
        panel_rgb = self.c(panel) if panel else None
        alpha = self.panel["opacity"] if panel_alpha is None else panel_alpha
        img, lines = text_block(runs, max_w or self.CW, panel_rgb, alpha,
                                self.panel["radius"] if radius is None else radius,
                                tuple(pad or self.panel["padding"]), align=align, min_w=min_w)
        if anchor == "bottomleft":
            y = y - img.height
        elif anchor == "topcenter":
            x = x - img.width // 2
        elif anchor == "bottomcenter":
            x, y = x - img.width // 2, y - img.height
        contrast = None
        if self.extremes is not None:
            contrast = min(worst_contrast(r.color, panel_rgb, alpha if panel_rgb else 0, self.extremes)
                           for r in runs)
        lay = Layer(name, self.save(img, name), int(x), int(y), img.width, img.height, t_in,
                    self.seg.duration if t_out is None else t_out, anim,
                    self.anim["slide_px"] if anim in ("slide_up", "slide_left") else 0,
                    self.anim["fade_in"] if anim != "static" else 0.0,
                    self.anim["fade_out"] if (anim != "static" and t_out is not None) else 0.0,
                    role, max(r.size for r in runs), " / ".join(lines), contrast,
                    {"lines": lines})
        self.layers.append(lay)
        return lay

    def add_logo(self, size, x, y, name="logo", t_in=0.0, anim="static", anchor="topleft"):
        lg = self.cfg["logo"]
        img = brand.logo_image(lg["path"], size, lg["opacity"], lg["mask"])
        if anchor == "topcenter":
            x -= img.width // 2
        fade = self.anim["fade_in"] if anim != "static" else 0.0
        lay = Layer(name, self.save(img, name), int(x), int(y), img.width, img.height, t_in,
                    self.seg.duration, anim, 0, fade, 0.0, "logo", 0, "",
                    meta={"source_aspect": brand.source_aspect(lg["path"]),
                          "size_px": size, "mask": lg["mask"], "opacity": lg["opacity"]})
        self.layers.append(lay)
        return lay

    # ---------------------------------------------------- blocos comuns
    def header(self, label: str | None, show_logo: bool):
        """Logo discreto + rótulo (demonstração / ilustrativa) no topo da área segura."""
        lg = self.cfg["logo"]
        bottom = self.T
        lx = None
        if show_logo:
            s = lg["size_px"]
            lx = self.L if lg["position"] == "top_left" else self.R - s
            logo = self.add_logo(s, lx, self.T)
            bottom = logo.y + logo.h
        if label:
            if show_logo and lg["position"] == "top_left":
                x, max_w = self.L + lg["size_px"] + 16, self.CW - lg["size_px"] - 16
            elif show_logo:
                x, max_w = self.L, self.CW - lg["size_px"] - 16
            else:
                x, max_w = self.L, self.CW
            run = Run(label, self.fonts["label"], self.sizes["label"], self.c("accent"))
            lay = self.add_block("label", [run], x, self.T, max_w=max_w, panel="bg", panel_alpha=0.9,
                                 role="label", anim="static", pad=(20, 14), radius=18)
            if show_logo and lay.h < lg["size_px"]:  # centraliza verticalmente com o logo
                lay.y = self.T + (lg["size_px"] - lay.h) // 2
            bottom = max(bottom, lay.y + lay.h)
        return bottom


def layout_hook(cfg, seg, bg_img, work_dir, label) -> Layout:
    lo = Layout(cfg, work_dir, seg, bg_img)
    lo.header(label, cfg["logo"]["show_on_scenes"])
    hook = cfg["hook"]
    anim = hook["animation"]
    styles = [("primary", "text"), ("accent", "text_dark")]
    blocks = []
    for i, line in enumerate(hook["lines"]):
        panel, txt = styles[i % len(styles)]
        run = Run(line, cfg["theme"]["font"]["bold"], lo.sizes["hook"], lo.c(txt))
        img, lines = text_block([run], lo.CW, lo.c(panel), 1.0, lo.panel["radius"], (32, 22), align="center")
        blocks.append((img, lines, panel, run))
    gap = 22
    total = sum(b[0].height for b in blocks) + gap * (len(blocks) - 1)
    y = lo.T + (lo.B - lo.T - total) // 2
    t0 = lo.anim["text_delay"]
    for i, (img, lines, panel, run) in enumerate(blocks):
        lay = lo.add_block(f"line{i + 1}", [run], lo.CX, y, max_w=lo.CW, panel=panel, panel_alpha=1.0,
                           role="title", t_in=t0 + i * lo.anim["stagger"], t_out=seg.content_end,
                           anim=anim, align="center", anchor="topcenter", pad=(32, 22))
        y = lay.y + lay.h + gap
    return lo


def layout_scene(cfg, seg, scene, bg_img, work_dir) -> Layout:
    lo = Layout(cfg, work_dir, seg, bg_img)
    top = lo.header(scene_label(cfg, scene), cfg["logo"]["show_on_scenes"]) + 28
    fb, fr = cfg["theme"]["font"]["bold"], cfg["theme"]["font"]["regular"]
    anim = scene.get("text_animation", "slide_up")
    t0 = seg.content_start + lo.anim["text_delay"]
    st = lo.anim["stagger"]
    t_end = seg.content_end

    # pilha inferior (de baixo para cima): subtítulo, título, categoria
    bottom = lo.B - (lo.anim["slide_px"] if anim == "slide_up" else 0)
    stack = []
    if scene.get("subtitle"):
        stack.append(("subtitle", Run(scene["subtitle"], fr, lo.sizes["subtitle"], lo.c("text")), "bg", "body", 2))
    stack.append(("title", Run(scene["title"], fb, lo.sizes["title"], lo.c("text")), "primary", "title", 1))
    stack.append(("category", Run(scene["category"].upper(), cfg["theme"]["font"]["label"],
                                  lo.sizes["category"], lo.c("text_dark")), "accent", "label", 0))
    for name, run, panel, role, order in stack:
        alpha = 1.0 if panel != "bg" else None
        lay = lo.add_block(name, [run], lo.L, bottom, panel=panel, panel_alpha=alpha, role=role,
                           t_in=t0 + order * st, t_out=t_end, anim=anim, anchor="bottomleft",
                           pad=(24, 14) if name == "category" else None)
        bottom = lay.y - 16
    stack_top = bottom + 16

    # destaques (pílulas/etiquetas) abaixo do cabeçalho, entram da direita
    items = [(h["text"], h["at"], h.get("style", "pill")) for h in scene.get("highlights", [])]
    for k in ("badge", "price"):
        if scene.get(k):
            items.append((scene[k], 0.0, "tag"))
    y = top
    for j, (txt, at, style) in enumerate(items):
        panel, col = ("primary", "text") if style == "pill" else ("bg", "accent")
        run = Run(txt, fb, lo.sizes["highlight"], lo.c(col))
        lay = lo.add_block(f"hl{j + 1}", [run], lo.L, y, panel=panel, panel_alpha=1.0, role="body",
                           t_in=max(at, t0), t_out=t_end, anim="slide_left",
                           radius=60 if style == "pill" else 14, pad=(30, 14))
        y = lay.y + lay.h + 14
    if items and y - 14 > stack_top - 12:
        lo.errors.append(f"{seg.key}: destaques ({y - 14}px) invadem o bloco de título ({stack_top}px)")
    return lo


def layout_cta(cfg, seg, bg_img, work_dir) -> Layout:
    lo = Layout(cfg, work_dir, seg, bg_img)
    cta = cfg["cta"]
    fb, fr, fl = cfg["theme"]["font"]["bold"], cfg["theme"]["font"]["regular"], cfg["theme"]["font"]["label"]
    lg = cfg["logo"]
    # medir os blocos para centralizar verticalmente a pilha
    pieces = []
    if cta["show_logo"]:
        pieces.append(("logo", None, round(lg["cta_size_px"] * 1.0)))
    head = Run(cta["headline"], fb, lo.sizes["cta_headline"], lo.c("text"))
    himg, _ = text_block([head], lo.CW, None, 0, 0, (0, 0), align="center")
    pieces.append(("headline", head, himg.height))
    btns = []
    for key, ch in resolve_buttons(cfg):
        runs = [Run(ch["label"], fl, lo.sizes["button"], lo.c("text_dark")),
                Run(ch["display"], fr, lo.sizes["button_sub"], lo.c("text_dark"))]
        bimg, _ = text_block(runs, lo.CW, (0, 0, 0), 1, 0, (36, 18), align="center", line_gap=0.05)
        btns.append((key, runs, bimg.height, bimg.width))
        pieces.append((f"btn_{key}", runs, bimg.height))
    disc = Run(cta["disclosure"], fr, lo.sizes["disclosure"], lo.c("text"))
    dimg, _ = text_block([disc], lo.CW, (0, 0, 0), 1, 0, (24, 12), align="center")
    label = cfg["demo_label"]["text"] if cfg["demo_label"]["enabled"] else None
    lab_h = 0
    if label:
        limg, _ = text_block([Run(label, fl, lo.sizes["label"], lo.c("accent"))], lo.CW, (0, 0, 0), 1, 0,
                             (20, 14), align="center")
        lab_h = limg.height
    gaps = {"logo": 36, "headline": 40, "btn": 22}
    body_h = sum(h for _, _, h in pieces) + gaps["logo"] * bool(cta["show_logo"]) + gaps["headline"] \
        + gaps["btn"] * max(len(btns) - 1, 0)
    foot_h = dimg.height + (lab_h + 14 if label else 0)
    slide = lo.anim["slide_px"]
    avail = lo.B - lo.T - foot_h - 30 - slide
    if body_h > avail:
        lo.errors.append(f"cta: conteúdo ({body_h}px) não cabe na área segura ({avail}px); "
                         f"reduza logo.cta_size_px ou tamanhos de fonte")
    y = lo.T + max((avail - body_h) // 2, 0)
    t = 0.1 + (seg.content_start if seg.trans_in else 0)
    st = lo.anim["stagger"]
    cx = lo.CX
    if cta["show_logo"]:
        logo = lo.add_logo(lg["cta_size_px"], cx, y, name="logo_cta", t_in=t, anim="fade", anchor="topcenter")
        y = logo.y + logo.h + gaps["logo"]
    h = lo.add_block("headline", [head], cx, y, panel=None, role="title", t_in=t + st, anim="slide_up",
                     align="center", anchor="topcenter", pad=(0, 0))
    y = h.y + h.h + gaps["headline"]
    btn_w = max((b[3] for b in btns), default=0)
    for i, (key, runs, _bh, _bw) in enumerate(btns):
        b = lo.add_block(f"btn_{key}", runs, cx, y, panel="accent", panel_alpha=1.0, role="body",
                         t_in=t + (2 + i) * st, anim="slide_up", align="center", anchor="topcenter",
                         pad=(36, 18), radius=44, min_w=btn_w)
        b.meta["channel"] = key
        y = b.y + b.h + gaps["btn"]
    yb = lo.B
    lo.add_block("disclosure", [disc], cx, yb, panel="bg", panel_alpha=0.6, role="body",
                 t_in=t + (2 + len(btns)) * st, anim="fade", align="center", anchor="bottomcenter", pad=(24, 12))
    if label:
        dl = lo.layers[-1]
        lo.add_block("label", [Run(label, fl, lo.sizes["label"], lo.c("accent"))], cx, dl.y - 14,
                     panel="bg", panel_alpha=0.9, role="label", anim="static", align="center",
                     anchor="bottomcenter", pad=(20, 14), radius=18)
    return lo


def check_layers(layers: list[Layer], cfg: dict, seg_key: str) -> list[str]:
    """Margem segura, tamanhos mínimos de fonte, contraste e proporção do logo."""
    o, sz, v = cfg["output"], cfg["safe_zone"], cfg["validation"]
    L, T, R, B = sz["left"], sz["top"], o["width"] - sz["right"], o["height"] - sz["bottom"]
    errs = []
    for la in layers:
        x0, y0, x1, y1 = la.motion_bbox()
        if x0 < L or y0 < T or x1 > R or y1 > B:
            errs.append(f"{seg_key}/{la.name}: fora da margem segura ({x0},{y0},{x1},{y1}) vs ({L},{T},{R},{B})")
        if la.role == "title" and la.font_px < v["min_title_px"]:
            errs.append(f"{seg_key}/{la.name}: título {la.font_px}px < {v['min_title_px']}px")
        if la.role in ("body", "label") and la.font_px < v["min_body_px"]:
            errs.append(f"{seg_key}/{la.name}: texto {la.font_px}px < {v['min_body_px']}px")
        if la.contrast is not None and la.contrast < v["min_contrast"]:
            errs.append(f"{seg_key}/{la.name}: contraste {la.contrast:.2f} < {v['min_contrast']}")
        if la.role == "logo":
            ar = la.w / la.h
            if abs(ar - la.meta["source_aspect"]) / la.meta["source_aspect"] > 0.01:
                errs.append(f"{seg_key}/{la.name}: proporção do logo alterada ({ar:.3f})")
    return errs
