"""Smoke del canal VNC (SP-03): conectar, capturar, actuar, capturar.

Uso: python scripts/vnc_smoke.py [--click X Y] [--type TEXTO] [--key NOMBRE]
Lee DESKTOP_URL y DESKTOP_PASSWORD del entorno (.env). Deja PNG en out/.
Solo operaciones inocuas; no usar para escribir en la app sin /__reset después.
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.vnc import VNCSession  # noqa: E402


def load_env() -> None:
    p = Path(__file__).resolve().parents[1] / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


async def main() -> None:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--click", nargs=2, type=int)
    ap.add_argument("--type")
    ap.add_argument("--key")
    ap.add_argument("--name", default="")
    a = ap.parse_args()
    out = Path("out")
    out.mkdir(exist_ok=True)
    t0 = time.monotonic()
    async with VNCSession(os.environ["DESKTOP_URL"], os.environ["DESKTOP_PASSWORD"]) as s:
        print(f"conectado en {time.monotonic() - t0:.2f}s, {s.width}x{s.height}")
        t = time.monotonic()
        await s.wait_stable()
        print(f"wait_stable inicial {time.monotonic() - t:.2f}s")
        s.capture().save(out / f"{a.name}before.png")
        if a.click:
            await s.click(*a.click)
        if a.type:
            await s.type_text(a.type)
        if a.key:
            await s.key(a.key)
        t = time.monotonic()
        await s.wait_stable()
        print(f"wait_stable tras acción {time.monotonic() - t:.2f}s, updates={s.updates}")
        s.capture().save(out / f"{a.name}after.png")
    print("ok →", out.resolve())


if __name__ == "__main__":
    asyncio.run(main())
