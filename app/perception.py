"""Percepción: captura → elementos numerados (docs/system-architecture.md §4, `observe()`).

Sin conocimiento de la app: todo sale del OCR (RapidOCR) y de formas genéricas (cajas de texto
blancas con borde, capa oscura de un modal). RapidOCR pierde tildes y a veces espacios: el texto
se compara siempre con `norm()` (sin tildes, minúsculas, sin espacios dobles).
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

_ENGINE = None
_ENGINE_LOCK = threading.Lock()

DATE_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})")


def engine():
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            from rapidocr_onnxruntime import RapidOCR
            _ENGINE = RapidOCR()
    return _ENGINE


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def squash(s: str) -> str:
    """Sin tildes, minúsculas y sin espacios: RapidOCR a veces pega palabras."""
    return norm(s).replace(" ", "")


@dataclass
class Element:
    n: int
    text: str
    x: int
    y: int
    w: int
    h: int
    kind: str = "texto"        # texto | campo
    in_modal: bool = False
    label: str = ""            # para campos: etiqueta más cercana arriba o a la izquierda

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2

    def line(self) -> str:
        if self.kind == "campo":
            desc = f"[campo «{self.label}»] valor=«{self.text}»" if self.label else f"[campo] valor=«{self.text}»"
        else:
            desc = self.text
        return f"[{self.n}] {desc} ({self.x},{self.y},{self.w},{self.h})"


@dataclass
class Screen:
    elements: list[Element]
    modal: tuple[int, int, int, int] | None = None
    today: str | None = None          # dd/mm/aaaa tal como sale en el encabezado
    width: int = 0
    height: int = 0
    ocr_s: float = 0.0
    image: Image.Image | None = field(default=None, repr=False)

    def get(self, n: int) -> Element | None:
        for e in self.elements:
            if e.n == n:
                return e
        return None

    def find(self, text: str, exact: bool = False) -> list[Element]:
        q = squash(text)
        out = []
        for e in self.elements:
            t = squash(e.text)
            if (t == q) if exact else (q in t):
                out.append(e)
        return out

    def signature(self) -> str:
        return "|".join(squash(e.text) for e in self.elements)[:4000]

    def render(self) -> str:
        head = []
        if self.today:
            head.append(f"Fecha 'hoy' según el encabezado de la app: {self.today}")
        if self.modal:
            head.append("HAY UN MODAL ABIERTO que bloquea la pantalla: solo los elementos marcados "
                        "(modal) se pueden usar.")
        lines = []
        for e in self.elements:
            lines.append(e.line() + (" (modal)" if e.in_modal else ""))
        return "\n".join(head + lines)


def _detect_modal(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Un cuadro claro grande rodeado de una capa claramente más oscura."""
    h, w = gray.shape
    bright = (gray > 225).astype(np.uint8)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        if area < 0.03 * w * h or area > 0.7 * w * h or bw < 150 or bh < 80:
            continue
        pad = 25
        x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(w, x + bw + pad), min(h, y + bh + pad)
        ring = np.concatenate([
            gray[y0:y, x0:x1].ravel(), gray[y + bh:y1, x0:x1].ravel(),
            gray[y:y + bh, x0:x].ravel(), gray[y:y + bh, x + bw:x1].ravel(),
        ])
        if ring.size == 0:
            continue
        inside = float(np.median(gray[y:y + bh, x:x + bw]))
        if float(np.median(ring)) < 0.7 * inside and (best is None or area > best[2] * best[3]):
            best = (x, y, bw, bh)
    if best is None:
        return None
    # El título del modal suele ser una franja oscura justo encima del cuadro claro.
    x, y, bw, bh = best
    # El pie (botones) suele estar separado por una línea: crecer hacia abajo mientras siga claro.
    bottom = y + bh
    while bottom < h - 1 and float(np.mean(gray[bottom, x + 5:x + bw - 5])) > 170:
        bottom += 1
    bh = bottom - y
    top = y
    while top > 0 and float(np.mean(gray[top - 1, x + 5:x + bw - 5])) < 120:
        top -= 1
        if y - top > 60:
            break
    return x, top, bw, bh + (y - top)


def _detect_fields(rgb: np.ndarray, gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Cajas de entrada: interior blanco puro con borde oscuro en los cuatro lados."""
    dark = (gray < 190).astype(np.uint8)
    contours, _ = cv2.findContours(dark, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out: list[tuple[int, int, int, int]] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        single = 16 <= h <= 27 and 50 <= w <= 1200
        multi = 40 <= h <= 160 and 300 <= w <= 1200
        if not (single or multi):
            continue
        inner = rgb[y + 3:y + h - 3, x + 3:x + w - 3]
        if inner.size == 0:
            continue
        g = gray[y + 3:y + h - 3, x + 3:x + w - 3]
        med = float(np.median(g))
        # Blanco puro = caja de texto; gris muy claro y ancho = lista desplegable (los botones son angostos).
        if med < 250 and not (med >= 225 and w >= 140):
            continue
        sides = [dark[y, x:x + w].mean(), dark[y + h - 1, x:x + w].mean(),
                 dark[y:y + h, x].mean(), dark[y:y + h, x + w - 1].mean()]
        if min(sides) < 0.8:
            continue
        if any(abs(x - a) < 4 and abs(y - b) < 4 and abs(w - c_) < 8 for a, b, c_, _ in out):
            continue
        out.append((x, y, w, h))
    return out


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy / max(1, bw * bh)


def _inside(box: tuple[int, int, int, int], area: tuple[int, int, int, int]) -> bool:
    return _overlap(area, box) > 0.6


def analyze(img: Image.Image) -> Screen:
    t0 = time.monotonic()
    img = img.convert("RGB")
    rgb = np.asarray(img)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    result, _ = engine()(rgb[:, :, ::-1], use_cls=False)
    texts: list[tuple[str, tuple[int, int, int, int]]] = []
    for quad, text, _score in result or []:
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        x, y = int(min(xs)), int(min(ys))
        texts.append((text.strip(), (x, y, int(max(xs)) - x, int(max(ys)) - y)))

    modal = _detect_modal(gray)
    fields = _detect_fields(rgb, gray)

    raw: list[Element] = []
    used = set()
    for fb in fields:
        inner = [i for i, (_, tb) in enumerate(texts) if _overlap(fb, tb) > 0.5]
        used.update(inner)
        value = " ".join(texts[i][0] for i in sorted(inner, key=lambda i: texts[i][1][0]))
        raw.append(Element(0, value, *fb, kind="campo"))
    for i, (t, tb) in enumerate(texts):
        if i not in used and t:
            raw.append(Element(0, t, *tb))

    # Etiqueta de cada campo: texto justo arriba (alineado a la izquierda) o a la izquierda.
    labels = [e for e in raw if e.kind == "texto"]
    for f in (e for e in raw if e.kind == "campo"):
        best, bd = None, 1e9
        for l in labels:
            above = -6 <= f.y - (l.y + l.h) <= 22 and abs(l.x - f.x) <= 40
            left = abs((l.y + l.h // 2) - (f.y + f.h // 2)) <= 12 and 0 <= f.x - (l.x + l.w) <= 160
            if above or left:
                d = abs(f.y - l.y) + abs(f.x - l.x) * (0.2 if above else 1)
                if d < bd:
                    best, bd = l, d
        if best:
            f.label = best.text

    # Orden de lectura: agrupar por renglón (centro vertical a ≤ 10 px) y luego de izquierda a derecha.
    raw.sort(key=lambda e: e.y + e.h / 2)
    rows: list[list[Element]] = []
    for e in raw:
        cy = e.y + e.h / 2
        if rows and cy - (rows[-1][0].y + rows[-1][0].h / 2) <= 10:
            rows[-1].append(e)
        else:
            rows.append([e])
    raw = [e for r in rows for e in sorted(r, key=lambda e: e.x)]
    for n, e in enumerate(raw, 1):
        e.n = n
        if modal:
            e.in_modal = _inside((e.x, e.y, e.w, e.h), modal)

    today = None
    top = [e for e in raw if e.y < img.height * 0.1]
    for e in sorted(top, key=lambda e: "hoy" not in norm(e.text)):
        m = DATE_RE.search(e.text)
        if m:
            today = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
            break

    return Screen(raw, modal, today, img.width, img.height, time.monotonic() - t0, img)


def annotate(screen: Screen, scale: float = 0.6) -> Image.Image:
    """Captura reducida con el número de cada elemento (para el LLM cuando el texto no alcanza)."""
    import PIL.ImageDraw as D
    im = screen.image.copy()
    d = D.Draw(im)
    for e in screen.elements:
        d.rectangle([e.x, e.y, e.x + e.w, e.y + e.h], outline=(255, 0, 0) if e.kind == "texto" else (0, 0, 255))
        d.text((e.x, max(0, e.y - 10)), str(e.n), fill=(255, 0, 0))
    return im.resize((int(im.width * scale), int(im.height * scale)))
