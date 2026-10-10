"""Punto de entrada del worker. SP-01: tarea falsa; SP-06 lo reemplaza por el bucle del agente."""
import asyncio
import os


async def run_task(tarea: str, url: str, password: str) -> tuple[str, str]:
    await asyncio.sleep(float(os.environ.get("FAKE_TASK_S", "10")))
    return "fallida", "Agente en construcción: no se operó el escritorio."
