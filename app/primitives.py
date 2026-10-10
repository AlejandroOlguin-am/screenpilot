"""Primitivas que el LLM puede elegir (docs/system-architecture.md §4).

El LLM nunca da coordenadas: nombra un elemento por número de la última observación. Cada
primitiva actúa, espera a que la pantalla se asiente y devuelve un texto corto con el efecto
observado (que vuelve al LLM en el paso siguiente).
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.perception import Element, Screen, analyze, norm, squash
from app.vnc import VNCSession

log = logging.getLogger("screenpilot.primitives")

MAX_PAGES = 40


class ActionError(Exception):
    """Error que vuelve al LLM como resultado del paso (no tumba la tarea)."""


class Primitives:
    def __init__(self, vnc: VNCSession):
        self.vnc = vnc
        self.screen: Screen | None = None
        self.table: list[dict[str, str]] = []
        self.table_cols: list[str] = []

    # ---------- observar ----------
    async def observe(self, settle_since: float | None = None) -> Screen:
        if settle_since is not None:
            await self.vnc.settle(settle_since)
        else:
            await self.vnc.wait_stable()
        # Si la app repinta mientras se hace el OCR (datos que llegan tarde), se vuelve a observar.
        for _ in range(4):
            shot_t = time.monotonic()
            img = self.vnc.capture()
            self.screen = await asyncio.to_thread(analyze, img)
            await asyncio.sleep(0.3)
            if self.vnc.last_change <= shot_t:
                break
            await self.vnc.wait_stable(min_wait=0.1)
        return self.screen

    def element(self, n) -> Element:
        try:
            n = int(n)
        except (TypeError, ValueError):
            raise ActionError(f"'{n}' no es un número de elemento")
        el = self.screen.get(n) if self.screen else None
        if el is None:
            raise ActionError(f"no existe el elemento [{n}] en la pantalla actual")
        return el

    # ---------- acciones ----------
    async def click(self, n) -> str:
        el = self.element(n)
        t = time.monotonic()
        await self.vnc.click(*el.center)
        before = self.screen.signature()
        await self.observe(t)
        return f"clic en [{n}] «{el.text or el.label}»" + ("" if self.screen.signature() != before
                                                           else " (la pantalla no cambió)")

    async def double_click(self, n) -> str:
        el = self.element(n)
        t = time.monotonic()
        await self.vnc.double_click(*el.center)
        await self.observe(t)
        return f"doble clic en [{n}] «{el.text}»"

    async def hover(self, n) -> str:
        el = self.element(n)
        t = time.monotonic()
        await self.vnc.move(*el.center)
        await self.observe(t)
        return f"mouse sobre [{n}] «{el.text}»"

    async def type_into(self, n, texto: str) -> str:
        el = self.element(n)
        texto = str(texto)
        t = time.monotonic()
        await self.vnc.click(*el.center)
        await asyncio.sleep(0.25)
        await self.vnc.key("ctrl+a")
        await asyncio.sleep(0.05)
        if texto:
            await self.vnc.type_text(texto)
        else:
            await self.vnc.key("backspace")
        await self.observe(t)
        # Releer el campo: la caja más parecida en posición.
        same = [e for e in self.screen.elements if e.kind == "campo"
                and abs(e.x - el.x) < 12 and abs(e.y - el.y) < 12]
        if same:
            got = same[0].text
            ok = squash(texto) in squash(got) or squash(got) in squash(texto) and len(squash(got)) > 3
            return (f"escrito en [{n}] «{el.label}»; el campo ahora muestra «{got}»"
                    + ("" if ok or not texto else " (no coincide con lo pedido: revisa)"))
        return f"escrito «{texto}» en [{n}] «{el.label}» (no pude releer el campo)"

    async def select_option(self, n, texto: str) -> str:
        el = self.element(n)
        t = time.monotonic()
        await self.vnc.click(*el.center)
        scr = await self.observe(t)
        q = squash(str(texto))
        opts = [e for e in scr.elements if e.kind == "texto" and squash(e.text) == q
                and not (abs(e.y - el.y) < 6 and abs(e.x - el.x) < 30)]
        if not opts:
            opts = [e for e in scr.elements if e.kind == "texto" and q and q in squash(e.text)
                    and e.y > el.y - 300]
        if opts:
            # La opción más cercana a la lista abierta.
            opt = min(opts, key=lambda e: abs(e.y - el.y) + abs(e.x - el.x))
            t = time.monotonic()
            await self.vnc.click(*opt.center)
            await self.observe(t)
        else:
            # Lista nativa que no se ve: elegir con el teclado (escribir el texto y Enter).
            await self.vnc.key("escape")
            await asyncio.sleep(0.2)
            t = time.monotonic()
            await self.vnc.type_text(str(texto))
            await self.vnc.key("enter")
            await self.observe(t)
        same = [e for e in self.screen.elements if e.kind == "campo"
                and abs(e.x - el.x) < 12 and abs(e.y - el.y) < 12]
        got = same[0].text if same else "?"
        ok = squash(got) == q
        return f"opción en [{n}] «{el.label}»: ahora muestra «{got}»" + ("" if ok else " (no coincide: revisa)")

    async def key(self, nombre: str) -> str:
        t = time.monotonic()
        await self.vnc.key(str(nombre))
        await self.observe(t)
        return f"tecla {nombre}"

    async def scroll(self, dir: str = "down", n=None) -> str:
        x, y = (self.element(n).center if n is not None else (self.vnc.width // 2, self.vnc.height // 2))
        t = time.monotonic()
        await self.vnc.move(x, y)
        await self.vnc.scroll("up" if str(dir).lower() in ("up", "arriba") else "down", 5, x, y)
        await self.observe(t)
        return f"scroll {dir}"

    async def wait(self, s=1.5) -> str:
        await asyncio.sleep(min(5.0, float(s)))
        await self.observe()
        return f"esperé {s}s"

    # ---------- tablas ----------
    @staticmethod
    def parse_table(screen: Screen) -> tuple[list[str], list[dict[str, str]]]:
        """Tabla visible: el bloque más largo de renglones con ≥3 textos separados ≤ 40 px.
        El primero es el encabezado; las columnas van de un encabezado al siguiente."""
        texts = [e for e in screen.elements if e.kind == "texto" and not (screen.modal and not e.in_modal)]
        rows: list[list[Element]] = []
        for e in sorted(texts, key=lambda e: e.y + e.h / 2):
            cy = e.y + e.h / 2
            if rows and cy - (rows[-1][0].y + rows[-1][0].h / 2) <= 9:
                rows[-1].append(e)
            else:
                rows.append([e])
        blocks: list[list[list[Element]]] = []
        for r in rows:
            r.sort(key=lambda e: e.x)
            if len(r) >= 3 and blocks and blocks[-1] and \
                    (r[0].y - blocks[-1][-1][0].y) <= 40 and len(r) >= 2:
                blocks[-1].append(r)
            elif len(r) >= 3:
                blocks.append([r])
        blocks = [b for b in blocks if len(b) >= 2]
        if not blocks:
            return [], []
        block = max(blocks, key=len)
        # Encabezado = el renglón con más textos entre los primeros; lo de antes es título o barra.
        hi = max(range(min(3, len(block))), key=lambda i: len(block[i]))
        block = block[hi:]
        header = block[0]
        # Al final suele venir la paginación (pocos textos): se descarta.
        while len(block) > 1 and len(block[-1]) < 0.6 * len(header):
            block.pop()
        cols = [h.text for h in header]
        starts = [h.x - 8 for h in header]
        out = []
        for r in block[1:]:
            cells = {c: "" for c in cols}
            for e in r:
                cx = e.x + 2
                idx = max([i for i, s in enumerate(starts) if s <= cx] or [0])
                cells[cols[idx]] = (cells[cols[idx]] + " " + e.text).strip()
            out.append(cells)
        return cols, out

    async def read_table(self, n_siguiente=None) -> str:
        cols, rows = self.parse_table(self.screen)
        if not cols or not rows:
            raise ActionError("no encontré una tabla con filas en la pantalla (¿terminó de cargar?)")
        seen = {tuple(r.values()) for r in rows}
        all_rows = list(rows)
        per_page = [len(rows)]
        pages = 1
        if n_siguiente is not None:
            nxt = self.element(n_siguiente)
            label = nxt.text
            while pages < MAX_PAGES:
                before = self.screen.signature()
                t = time.monotonic()
                await self.vnc.click(*nxt.center)
                await self.observe(t)
                if self.screen.signature() == before:
                    break
                _, rows = self.parse_table(self.screen)
                new = [r for r in rows if tuple(r.values()) not in seen]
                if not new:
                    break
                for r in new:
                    seen.add(tuple(r.values()))
                all_rows += new
                per_page.append(len(new))
                pages += 1
                hits = self.screen.find(label, exact=True)
                if not hits:
                    break
                nxt = min(hits, key=lambda e: abs(e.y - nxt.y) + abs(e.x - nxt.x))
        self.table_cols, self.table = cols, all_rows
        preview = "\n".join(" | ".join(r.values()) for r in all_rows[:12])
        return (f"tabla leída: {len(all_rows)} filas en {pages} página(s) (filas por página: {per_page}). Columnas: {cols}.\n"
                f"Primeras filas:\n{preview}" + ("\n…" if len(all_rows) > 12 else ""))

    def count_rows(self, filtros: dict | None = None) -> str:
        if not self.table_cols:
            raise ActionError("primero usa read_table")
        filtros = filtros or {}
        colmap = {}
        for k in filtros:
            m = [c for c in self.table_cols if squash(c) == squash(k)] or \
                [c for c in self.table_cols if squash(k) in squash(c)]
            if not m:
                raise ActionError(f"no hay columna «{k}»; columnas: {self.table_cols}")
            colmap[k] = m[0]
        # Coincidencia exacta de la celda (normalizada): "Ferretería Ruiz" ≠ "Ferretería Ruiz Central".
        hits = [r for r in self.table
                if all(norm(r[colmap[k]]) == norm(str(v)) for k, v in filtros.items())]
        first = self.table_cols[0]
        codes = ", ".join(r[first] for r in hits[:60])
        return f"count_rows({filtros}) = {len(hits)} de {len(self.table)} filas leídas. {first}: {codes}"
