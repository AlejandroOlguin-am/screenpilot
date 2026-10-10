# ScreenPilot

Agente que opera aplicaciones sin API únicamente por pantalla (VNC) y ejecuta tareas en lenguaje
natural. Frontier BOG/26 · Reto 1. Arquitectura: `docs/system-architecture.md`.

## Requisitos
- Python 3.12 · Docker · `gcloud` autenticado (ADC)
- Tesseract con español (`apt install tesseract-ocr tesseract-ocr-spa`) si el experimento de
  percepción elige Tesseract
- Variables en `.env` (ver `.env.example`):

| Variable | Para qué |
|---|---|
| `TEAM_TOKEN` | Bearer que exige nuestro API |
| `OPENROUTER_API_KEY` | LLMs |
| `DESKTOP_URL` | `wss://<host del escritorio>/websockify` — el mismo host de la tarjeta, con `wss://` y `/websockify` (solo pruebas locales) |
| `DESKTOP_PASSWORD` | Contraseña del escritorio (solo para pruebas locales) |
| `DESKTOP_TOKEN` | Token del escritorio para `/__reset` y `/__check` (solo harness) |
| `MAX_COST_PER_TASK` | Tope de gasto por tarea en US$ (por defecto 0.30) |

## Levantar todo (local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completar
uvicorn app.main:app --reload --port 8080
curl localhost:8080/health
```

## Probar una tarea a mano
```bash
curl -s -X POST localhost:8080/tasks \
  -H "Authorization: Bearer $TEAM_TOKEN" -H "Content-Type: application/json" \
  -d "{\"tarea\":\"¿Cuántas facturas vencidas tiene Ferretería Ruiz?\",
       \"escritorio\":{\"url\":\"$DESKTOP_URL\",\"password\":\"$DESKTOP_PASSWORD\"}}"
curl -s localhost:8080/tasks/<task_id> -H "Authorization: Bearer $TEAM_TOKEN"
```

## Tests
| Nivel | Comando | Qué cubre |
|---|---|---|
| Unit | `pytest tests/unit` | redacción de secretos, formato del resumen, guard, coincidencia exacta, percepción sobre PNG fijos |
| Canal VNC | `python scripts/vnc_smoke.py` | conecta, captura, clic, escribe (deja PNG en `out/`) |
| Evaluación | `python scripts/eval.py --target http://localhost:8080` | `/__reset` → tarea → `/__check` + estado + resumen; tabla en `experiments/` |

Leer un fallo del harness: la columna `check` viene de `/__check` (estado de la app); `estado` y
`resumen` los valida el harness con las reglas del README del reto.

## Desplegar (Cloud Run)
URL pública: `https://screenpilot-934756554303.us-east1.run.app` (proyecto `mvps-london`).
```bash
scripts/deploy.sh                       # build + deploy + /health
python scripts/eval.py --target https://screenpilot-934756554303.us-east1.run.app
```
Sin CI de deploy: se despliega a mano cuando hace falta (decisión por tiempo, 10-oct).
Secretos en Secret Manager: `TEAM_TOKEN`, `OPENROUTER_API_KEY` (rotar con
`gcloud secrets versions add`).

## Trampas
1. Sin `--no-cpu-throttling` las tareas en segundo plano se congelan.
2. Clic con < 100 ms entre bajar y soltar se ignora.
3. Capturar justo después de actuar devuelve la pantalla vieja: usar `wait_stable()`.
4. Escribir en un campo con texto concatena: Ctrl+A primero.
5. En v4.2, `Aplicar` deja el formulario abierto: no re-pulsar (duplicados).
6. `/__reset` reabre la app y el modal de novedades vuelve a salir.
7. Nunca loguear ni devolver la contraseña del escritorio.
