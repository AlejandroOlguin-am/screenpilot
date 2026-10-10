"""Contrato del API (docs/system-architecture.md §2)."""
import asyncio
import logging
import os
import secrets
import uuid
from dataclasses import dataclass, field

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.runner import run_task

log = logging.getLogger("screenpilot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TASK_DEADLINE_S = float(os.environ.get("TASK_DEADLINE_S", "270"))


class Desktop(BaseModel):
    url: str
    password: str


class TaskIn(BaseModel):
    tarea: str
    escritorio: Desktop


@dataclass
class Task:
    id: str
    tarea: str
    estado: str = "en_curso"
    resumen: str = ""
    handle: asyncio.Task | None = field(default=None, repr=False)


TASKS: dict[str, Task] = {}
DESKTOP_LOCKS: dict[str, asyncio.Lock] = {}

app = FastAPI(title="ScreenPilot")


def require_token(request: Request) -> None:
    expected = os.environ.get("TEAM_TOKEN", "")
    got = request.headers.get("authorization", "")
    if not expected or not secrets.compare_digest(got, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="token inválido")


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


async def _supervise(task: Task, desktop: Desktop) -> None:
    lock = DESKTOP_LOCKS.setdefault(desktop.url, asyncio.Lock())
    async with lock:
        try:
            estado, resumen = await asyncio.wait_for(
                run_task(task.tarea, desktop.url, desktop.password), TASK_DEADLINE_S
            )
        except asyncio.TimeoutError:
            estado, resumen = "fallida", "Se agotó el tiempo de la tarea antes de terminar."
        except Exception:  # noqa: BLE001 — una tarea nunca tumba el proceso
            log.exception("tarea %s falló", task.id)
            estado, resumen = "fallida", "Error interno del agente; no se completó la tarea."
    task.estado, task.resumen = estado, resumen
    log.info("tarea %s → %s", task.id, estado)


@app.post("/tasks", dependencies=[Depends(require_token)])
async def create_task(body: TaskIn) -> dict:
    task = Task(id=str(uuid.uuid4()), tarea=body.tarea)
    TASKS[task.id] = task
    task.handle = asyncio.create_task(_supervise(task, body.escritorio))
    log.info("tarea %s recibida", task.id)
    return {"task_id": task.id}


@app.get("/tasks/{task_id}", dependencies=[Depends(require_token)])
async def get_task(task_id: str) -> dict:
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="tarea no encontrada")
    return {"estado": task.estado, "resumen": task.resumen}
