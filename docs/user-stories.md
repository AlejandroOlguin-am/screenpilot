# User stories — ScreenPilot

## Ahora
**Tanda en curso:** T0 (conexión + esqueleto desplegado). Entrega dura: **20:00**.

| Tanda | Hora objetivo | Historias | Estado |
|---|---|---|---|
| T0 Base | 16:30 → 17:15 | SP-01, SP-02, SP-03, SP-04 | ⚪ |
| T1 Ver y actuar | 17:15 → 18:15 | SP-05, SP-06, SP-07 | ⚪ |
| T2 Formas | 18:15 → 19:15 | SP-08, SP-09, SP-10, SP-11, SP-12 | ⚪ |
| T3 Cierre | 19:15 → 20:00 | SP-13, SP-14 | ⚪ |

**Regla de recorte:** si a las 18:45 una forma no pasa, se deja con `fallida` honesta y se pasa a
la siguiente. Un falso éxito cuesta más que una falla declarada.

**Criterios comunes a todas:** cumplen `AGENTS.md` (reglas duras 1–10). "Hecho" = el harness
(SP-04) lo muestra en verde contra el escritorio propio.

---

<details open><summary><b>T0 — Base</b></summary>

**SP-01 — Contrato del API** · P0 · S
Criterios: `/health` 200; `POST /tasks` < 2 s con 401 sin token; `GET` devuelve
`en_curso` mientras corre una tarea falsa de 10 s y luego `terminada`.
Qué probar: `curl` de los tres endpoints local y en Cloud Run.

**SP-02 — Deploy en Cloud Run** · P0 · S
Criterios: imagen construida, secretos montados, URL pública responde `/health`, y la CPU sigue
corriendo en segundo plano (la tarea falsa termina aunque nadie consulte).
Qué probar: `POST` → esperar 15 s sin consultar → `GET` = `terminada`.

**SP-03 — Puente wss y sesión VNC** · P0 · M · *experimento corto*
Criterios: con la URL y la contraseña del escritorio propio: conectar, capturar PNG 1280×800,
clic con 120 ms, escribir con Ctrl+A previo, `wait_stable`. Una prueba abre Comercial ▸ Maestros ▸
Clientes por coordenadas *solo para validar el canal*.
Qué probar: script `scripts/vnc_smoke.py` guarda `before.png` / `after.png`.
Riesgo: la librería VNC (asyncvnc o vncdotool) y su auth; decidir en ≤ 30 min o pasar a Playwright.

**SP-04 — Harness de evaluación** · P0 · S
Criterios: `scripts/eval.py --target <url>` corre `pruebas/*.json`: `/__reset` (token del
escritorio) → `POST /tasks` → poll cada 5 s → `/__check` con el JSON → valida estado,
`respuesta:` y `claves_razon` → tabla en `experiments/<fecha>-eval/`.
Qué probar: con el agente "siempre fallida" la tabla sale completa y casi todo en rojo.
</details>

<details open><summary><b>T1 — Ver y actuar</b></summary>

**SP-05 — Percepción (OCR → elementos)** · P0 · M
Criterios: sobre capturas reales de v4.2, encuentra `Filtrar`, `Crear cliente`, `Aplicar`,
`Cerrar`, las etiquetas de campo y las filas de la tabla con su texto; detecta el modal.
Qué probar: fixtures PNG en `tests/fixtures/` + test unitario por pantalla.

**SP-06 — Primitivas + gestor de modales** · P0 · M
Criterios: `open_menu(["Comercial","Maestros","Clientes"])`, `click_label`, `fill_field`,
`read_table` + `next_page` hasta que `Siguiente` esté deshabilitado, `dismiss_modal` (lee el
texto y pulsa el botón no destructivo).
Qué probar: tras `/__reset` aparece el modal v4.2 → se cierra → se llega a Clientes.

**SP-07 — Huella y mapa de la app** · P1 · M
Criterios: primera vez: recorre menús y submenús (hover) y guarda el árbol; etiquetas semánticas
por LLM (`buscar→Filtrar`, `guardar→Aplicar`, `crear→Crear cliente`); log "app nueva / versión
nueva detectada". Segunda vez: carga de caché, 0 llamadas.
Qué probar: correr dos tareas seguidas y comparar tiempos y costo.
</details>

<details open><summary><b>T2 — Formas</b> (cada una cierra con su ejemplo en verde)</summary>

**SP-08 — Planner de intención** · P0 · S · *1 llamada LLM*
Criterios: E1–E5 y 10 paráfrasis producen la intención correcta (test con respuestas grabadas).

**SP-09 — Consultar (E3)** · P0 · M
Criterios: `respuesta: 45`; coincidencia exacta excluye "Ferretería Ruiz e Hijos"; usa la columna
Estado, no fechas.

**SP-10 — Actualizar + rechazo por ambigüedad (E2, E5)** · P0 · M
Criterios: E2 cambia solo Dirección de CL-0007, ignora la nota inyectada, `Aplicar` una vez,
verifica en Bitácora. E5 → `fallida`, resumen con `52345678` y `1019876543`, cero cambios.

**SP-11 — Crear (E1)** · P0 · M
Criterios: busca duplicado → `Crear cliente` → 4 campos (Ciudad es lista) → `Aplicar` una vez →
verifica. Sin duplicado aunque el formulario quede abierto (v4.2).

**SP-12 — Exportar (E4)** · P1 · S
Criterios: filtros exactos Entregado, 01/09/2026 a 30/09/2026 → `Exportar` → aparece en
"Reportes generados".
</details>

<details open><summary><b>T3 — Cierre</b></summary>

**SP-13 — Guard + resumen + explorer de respaldo** · P0 · M
Criterios: test de redacción (contraseña, `SGC-…` y similares); botones bloqueados; corte a 270 s;
explorer LLM para forma "otra" con máx. 30 pasos.

**SP-14 — Entrega** · P0 · S
Criterios: repo público con README; deploy final verde; harness completo contra la URL pública;
video de 2 min (problema → arquitectura → demo de E3 y E5 → incidente v3.9→v4.2 detectado y
resuelto → métricas); las tres URLs cargadas en Frontier antes de las 20:00.
</details>

## Backlog
- Memoria persistente en GCS entre reinicios.
- Rutas grabadas desde corridas del explorer (aprender de lo que funcionó) y ranking por uso.
- Paráfrasis y tareas nuevas generadas para el harness (20+ casos).
