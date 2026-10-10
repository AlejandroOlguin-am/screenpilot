"""Depuración manual: conecta al escritorio, ejecuta operaciones y guarda la captura final.

Uso: python scripts/poke.py 'click:Entendido' 'key:enter' 'type:texto' 'at:x,y' 'snap:nombre' ...
     --reset hace /__reset antes. Imprime la pantalla tal como la ve el LLM.
"""
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.primitives import Primitives  # noqa: E402
from app.vnc import VNCSession  # noqa: E402
from scripts.eval import desktop_base  # noqa: E402
from scripts.vnc_smoke import load_env  # noqa: E402


async def main(ops: list[str]) -> None:
    async with VNCSession(os.environ["DESKTOP_URL"], os.environ["DESKTOP_PASSWORD"]) as vnc:
        p = Primitives(vnc)
        await p.observe()
        for op in ops:
            kind, _, arg = op.partition(":")
            t = time.monotonic()
            if kind == "click":
                hits = p.screen.find(arg, exact=True) or p.screen.find(arg)
                print(op, "→", await p.click(hits[-1].n) if hits else "NO ENCONTRADO")
            elif kind == "n":
                print(op, "→", await p.click(int(arg)))
            elif kind == "at":
                x, y = map(int, arg.split(","))
                await vnc.click(x, y)
                await p.observe(t)
            elif kind == "key":
                print(op, "→", await p.key(arg))
            elif kind == "type":
                await vnc.type_text(arg)
                await p.observe(t)
            elif kind == "typeinto":
                n, _, txt = arg.partition("=")
                print(op, "→", await p.type_into(int(n), txt))
            elif kind == "select":
                n, _, txt = arg.partition("=")
                print(op, "→", await p.select_option(int(n), txt))
            elif kind == "table":
                print(op, "→", await p.read_table(int(arg) if arg else None))
            elif kind == "snap":
                p.screen.image.save(ROOT / "out" / f"{arg}.png")
            print(f"   ({time.monotonic() - t:.1f}s)")
        print(p.screen.render())
        p.screen.image.save(ROOT / "out" / "poke.png")


if __name__ == "__main__":
    load_env()
    args = sys.argv[1:]
    if args and args[0] == "--reset":
        args = args[1:]
        httpx.post(f"{desktop_base(os.environ['DESKTOP_URL'])}/__reset", timeout=90,
                   headers={"Authorization": f"Bearer {os.environ['DESKTOP_TOKEN']}"}).raise_for_status()
        time.sleep(3)
    asyncio.run(main(args))
