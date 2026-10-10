# System architecture — ScreenPilot

> Versión post-README e incidente (reemplaza al PDF de systems design de las 12:00 en lo que
> difiera; cambios en §9). Contexto: `product-overview.md`. Mapa de la app de pruebas:
> `app-knowledge/`.

## 1. Vista de una línea
FastAPI en Cloud Run recibe la tarea → la parsea a una **intención** → un worker se conecta al
escritorio por **VNC sobre websocket** → ejecuta el **playbook** de esa intención con primitivas
deterministas + decisiones puntuales del LLM → **verifica** → responde con un resumen formateado y
filtrado → se desconecta.

```
Evaluador ─POST /tasks──▶ API (FastAPI) ──encola──▶ Worker (asyncio, 1 por tarea)
          ◀─GET /tasks/id── store de tareas ◀──estado/resumen──┘    │
                                                                  │ VNC (RFB)
                                          puente local TCP ⇄ wss://…/websockify
                                                                  ▼
                                                     Escritorio (kiosko 1280×800)
```

## 2. Contrato del API (fijo, lo dicta el reto)
Todas las llamadas: `Authorization: Bearer <TEAM_TOKEN>` (401 si falta o no coincide; `/health`
responde 200 con o sin token).

| Ruta | Comportamiento |
|---|---|
| `GET /health` | `200 {"ok": true}` cuando el proceso está listo |
| `POST /tasks` | Body `{"tarea": str, "escritorio": {"url": "wss://…/websockify", "password": str}}` → crea `task_id` (uuid), lo guarda como `en_curso`, lanza `asyncio.create_task(run_task(...))` y responde `{"task_id"}` en **< 100 ms** |
| `GET /tasks/{id}` | `{"estado": "en_curso" \| "terminada" \| "fallida", "resumen": str}`. 404 si no existe |

- El evaluador consulta cada 5 s, hasta 5 min. Corte interno a los **270 s**: se cancela, se
  reporta `fallida` con resumen parcial y se cierra VNC.
- Varias tareas pueden llegar a la vez con escritorios distintos: un worker por tarea, **un lock por
  URL de escritorio** (nunca dos tareas sobre el mismo escritorio).
- La contraseña se guarda solo en memoria de la tarea; nunca se loguea.

## 3. Componentes

| # | Módulo | Responsabilidad | LLM |
|---|---|---|---|
| 1 | `api/` | Contrato, auth, store de tareas en memoria (+ volcado a disco para depurar) | — |
| 2 | `vnc/bridge.py` | Servidor TCP en `127.0.0.1:<puerto libre>` que reenvía bytes al `wss://` (subprotocolo `binary`) | — |
| 3 | `vnc/session.py` | Cliente VNC: conectar con contraseña, `capture()` → imagen, `click(x,y)` con bajar→120 ms→soltar, `type()`, `key()`, `scroll()`, `wait_stable()` | — |
| 4 | `perception/` | OCR de la captura → **elementos** (texto, caja, tipo: botón/campo/link/encabezado/fila); detección de modal (capa oscura + cuadro centrado); lectura de tablas por filas/columnas | — |
| 5 | `primitives/` | Acciones deterministas con verificación propia: `open_menu(path)`, `click_label(label)`, `fill_field(label, value)` (Ctrl+A antes de escribir), `select_option(label, value)`, `read_table()`, `next_page()`, `dismiss_modal()`, `read_header()` | — |
| 6 | `knowledge/app_map.py` | **Huella** de la app (título + versión + menús) → mapa: árbol de menús, pantallas por entidad, etiquetas semánticas (`buscar→Filtrar`, `guardar→Aplicar`). Se aprende la primera vez (~30 s) y se reutiliza | 1–2 llamadas al aprender |
| 7 | `planner/intent.py` | Tarea → intención estructurada (ver §4) | 1 llamada |
| 8 | `playbooks/` | Una receta genérica por forma: crear, actualizar, consultar, exportar. Usa primitivas + mapa | Solo para mapear campos y etiquetas no vistas |
| 9 | `playbooks/explorer.py` | Fallback para lo que no encaja: bucle LLM paso a paso con *set-of-marks* (elementos numerados) | 1 por paso, máx. 30 |
| 10 | `guard/` | Reglas de seguridad: unicidad antes de escribir, botones bloqueados, texto de pantalla = dato, presupuesto de tiempo y costo | — |
| 11 | `report/summary.py` | Resumen con formato del reto + **redacción de secretos** | — |
| 12 | `scripts/eval.py` | Harness: `/__reset` → `POST /tasks` → poll → `/__check` + validación local de estado y resumen | — |

## 4. Intención (salida del planner)
```json
{
  "forma": "crear | actualizar | consultar | exportar | otra",
  "entidad": "clientes | pedidos | facturas | <otra>",
  "objetivo": {"nombre": "Distribuciones El Faro", "nit": null, "codigo": null},
  "campos": {"direccion": "Calle 80 # 24-15"},
  "filtros": {"estado": "Entregado", "desde": "2026-09-01", "hasta": "2026-09-30"},
  "pregunta": {"medida": "contar", "condicion": "estado=Vencida", "datos_pedidos": 1},
  "fechas_relativas": ["ayer"]
}
```
Las fechas relativas se resuelven con la fecha del **encabezado de la app** (`Hoy: 14/10/2026`).
Los nombres de entidad y campo son los de la tarea; el mapa los traduce a las pantallas y
etiquetas de la app concreta.

## 5. Playbooks (las "rutas")
Todos empiezan igual: `conectar → dismiss_modal → leer encabezado → huella → mapa (cargar o
aprender) → navegar a la pantalla de la entidad`.

| Forma | Pasos | Verificación | Falla (`fallida`) si… |
|---|---|---|---|
| **Crear** | filtrar por nombre/NIT → si existe: no crear → `crear` → llenar solo los campos pedidos → `guardar` **una vez** | Bitácora o lista muestran el registro nuevo con esos valores | Ya existe (nombrar código/NIT) · falta un obligatorio |
| **Actualizar** | filtrar → leer **todas** las páginas → coincidencia **exacta** → 1 resultado → abrir → cambiar solo esos campos → `guardar` una vez | Bitácora: un cambio, en ese registro y ese campo | 0 coincidencias · >1 (nombrar los NIT/códigos, como E5) |
| **Consultar** | aplicar los filtros que la app ofrece (amplios) → leer todas las páginas con OCR → **filtrar exacto en código** (nombre idéntico, estado) → calcular | Releer la última página; que la cuenta de filas cuadre | No se puede responder → sin línea `respuesta:` |
| **Exportar** | aplicar **exactamente** los filtros pedidos (ni uno más) → `exportar` | "Reportes generados" muestra el reporte con esos filtros | El botón no existe o la pantalla no lo registra |
| **Otra** | explorer (LLM paso a paso), con el mismo guard | Lo que el LLM declare + la Bitácora | Sin evidencia de éxito |

**El mapa es lo que se "aprende como empleado nuevo":** dónde está cada entidad, cómo se llama cada
acción y qué campos tiene cada formulario. Los playbooks son el oficio general. Ninguno de los dos
lleva textos de SIGECOM escritos a mano.

## 6. Percepción y grounding
- Captura completa 1280×800 → OCR → elementos con caja. Cada clic apunta al **centro de la caja**
  del elemento encontrado por texto.
- Campos de formulario: la etiqueta OCR encima o a la izquierda + el rectángulo vacío más cercano
  debajo (OpenCV).
- Cuando la correspondencia es semántica (¿qué botón es "guardar"?), el LLM recibe la **lista de
  textos** en pantalla (más una captura reducida con marcas numeradas si hace falta) y elige un
  número. Resultado en caché por huella de app.
- Modelo: uno barato con visión por defecto y uno más fuerte si falla 2 veces. Elección en
  `experiments/2026-10-10-perception/`.

## 7. Guard (seguridad y puntaje)
- **Texto de pantalla = dato.** Nunca entra al prompt como instrucción; va delimitado como
  `<pantalla>…</pantalla>` con la regla explícita, y además el guard bloquea en código acciones
  fuera de la intención.
- **Botones bloqueados** salvo que la forma lo requiera: eliminar, borrar, anular, revertir,
  descartar.
- **Escritura solo en campos de la intención.** Antes de guardar, se comparan los valores del
  formulario con los originales: si cambió otro campo, se aborta.
- **Guardar una sola vez.** Nunca se re-pulsa; si no hay evidencia → `fallida`.
- **Tiempo:** 270 s de corte duro; el explorer tiene máx. 30 pasos.
- **Costo:** `MAX_COST_PER_TASK` (p. ej. US$0,30); al superarlo, `fallida` con resumen.

## 8. Resumen
```
<qué se hizo en una o dos frases, con códigos de registro>
respuesta: <valor>            ← solo en preguntas respondibles
motivo: <datos clave>         ← en fallida: NIT/códigos que lo explican
```
Antes de devolverlo, `redact()` reemplaza por `[oculto]`: la contraseña del escritorio, el token
del equipo y cualquier cadena con forma de clave vista en pantalla (p. ej. `XXX-XXXX-XXXX`) o
cercana a palabras como "clave", "token", "contraseña". Tiene test.

## 9. Despliegue (GCP)
- **Cloud Run**, una región en EE. UU. (los escritorios están en Railway). Imagen Docker con
  Python 3.12, Tesseract (`spa`) u ONNX según el experimento, OpenCV headless.
- Flags: `--no-cpu-throttling --min-instances=1 --max-instances=1 --timeout=300 --cpu=2
  --memory=2Gi --allow-unauthenticated` (la auth la hace la app con el Bearer).
- Secretos en Secret Manager: `TEAM_TOKEN`, `OPENROUTER_API_KEY` (`--set-secrets`).
- Una sola instancia, así que el store de tareas en memoria es válido. Si la instancia se recicla,
  se pierden las tareas en curso; se acepta para el reto.
- Verificación del deploy: `curl /health` y una tarea real del harness contra la URL pública.

## 10. Cambios respecto al PDF de las 12:00
| Antes | Ahora | Por qué |
|---|---|---|
| Playwright sobre la página noVNC | VNC directo sobre `wss://…/websockify` | El README entrega el websocket como interfaz del agente |
| Railway | Cloud Run | Decisión del equipo |
| Rutas = cadenas grabadas por app | Playbooks genéricos por forma + mapa aprendido por app | El set oculto es otra app; los ejemplos revelan 5 formas |
| Verificación genérica | Verificación por Bitácora y Reportes generados, unicidad, guardar una vez | Así se califica (diff, duplicados, falso éxito) |
| — | Guard anti-inyección y redacción de secretos | Trampas reales en la app (E2, Integraciones) |
| — | Gestor de modales y etiquetas semánticas | Incidente v4.2 |
