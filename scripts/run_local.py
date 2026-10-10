"""Corre una tarea directo con el agente, sin API (SP-06). Uso: python scripts/run_local.py "tarea" [--reset]"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.eval import desktop_base  # noqa: E402
from scripts.vnc_smoke import load_env  # noqa: E402


def main() -> None:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("tarea")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    if a.reset:
        httpx.post(f"{desktop_base(os.environ['DESKTOP_URL'])}/__reset", timeout=90,
                   headers={"Authorization": f"Bearer {os.environ['DESKTOP_TOKEN']}"}).raise_for_status()
    from app.agent import run
    estado, resumen = asyncio.run(run(a.tarea, os.environ["DESKTOP_URL"], os.environ["DESKTOP_PASSWORD"]))
    print("\nESTADO:", estado, "\nRESUMEN:\n" + resumen)


if __name__ == "__main__":
    main()
