"""Punto de entrada del worker: corre el bucle del agente (SP-06).

Con FAKE_TASK_S definido se usa la tarea falsa de SP-01 (tests del contrato del API).
"""
import asyncio
import os

from app import agent


async def run_task(tarea: str, url: str, password: str) -> tuple[str, str]:
    if os.environ.get("FAKE_TASK_S"):
        await asyncio.sleep(float(os.environ["FAKE_TASK_S"]))
        return "fallida", "Agente en construcción: no se operó el escritorio."
    return await agent.run(tarea, url, password)
