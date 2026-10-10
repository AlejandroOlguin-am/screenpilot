"""Captura fixtures reales para tests/fixtures/ (SP-05). Solo navega y abre, no escribe.

Uso: python scripts/capture_fixtures.py  (hace /__reset antes para tener el modal)
"""
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.perception import analyze  # noqa: E402
from app.vnc import VNCSession  # noqa: E402
from scripts.eval import desktop_base  # noqa: E402
from scripts.vnc_smoke import load_env  # noqa: E402

OUT = ROOT / "tests" / "fixtures"


async def click_text(s: VNCSession, text: str) -> None:
    await s.wait_stable()
    scr = analyze(s.capture())
    hits = scr.find(text, exact=True) or scr.find(text)
    if not hits:
        raise SystemExit(f"no encontré «{text}»")
    t = time.monotonic()
    await s.click(*hits[0].center)
    await s.settle(t)


async def snap(s: VNCSession, name: str) -> None:
    await s.wait_stable()
    s.capture().save(OUT / f"{name}.png")
    print("→", name)


async def main() -> None:
    load_env()
    base = desktop_base(os.environ["DESKTOP_URL"])
    httpx.post(f"{base}/__reset", headers={"Authorization": f"Bearer {os.environ['DESKTOP_TOKEN']}"},
               timeout=90).raise_for_status()
    await asyncio.sleep(4)
    OUT.mkdir(parents=True, exist_ok=True)
    async with VNCSession(os.environ["DESKTOP_URL"], os.environ["DESKTOP_PASSWORD"]) as s:
        await snap(s, "home_modal")
        await click_text(s, "Entendido")
        await click_text(s, "Comercial")
        await snap(s, "menu_comercial")
        await click_text(s, "Maestros")
        await snap(s, "submenu_maestros")
        await click_text(s, "Clientes")
        await snap(s, "clientes_list")
        await click_text(s, "Crear cliente")
        await snap(s, "cliente_form")


if __name__ == "__main__":
    asyncio.run(main())
