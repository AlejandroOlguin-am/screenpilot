# User stories — ScreenPilot

> **Versión:** 0.2 · **Última actualización:** 2026-10-10 16:50 · **Fuente de verdad de:** qué se
> construye y en qué orden. El estado vivo va en `memory/current-state.md`.
> Estados: ⬜ pendiente · 🟡 en curso · 🔍 en review · ✅ hecho · ↪ backlog.

## Ahora
**Tanda en curso:** T1 Ver, decidir, actuar · rama `t0-base` (T0 cerrada 17:15). Entrega dura: **20:00 (Bogotá)**.

| Tanda | Hora objetivo | Historias | Estado |
|---|---|---|---|
| T0 Base | 16:50 → 17:40 | SP-01, SP-02, SP-03, SP-04 | ✅ 17:15 |
| T1 Ver, decidir, actuar | 17:40 → 18:40 | SP-05, SP-06, SP-07 | ⬜ |
| T2 Ejemplos en verde | 18:40 → 19:20 | SP-08, SP-09 | ⬜ |
| T3 Cierre | 19:20 → 20:00 | SP-10, SP-11 | ⬜ |

**Regla de recorte:** a las 19:00 lo que no pasa se deja como `fallida` honesta.
**Criterios comunes:** cumplen `AGENTS.md`. "Hecho" = el harness (SP-04) lo muestra en verde.

---

<details open><summary><b>T0 — Base</b></summary>

**SP-01 — Contrato del API** · P0 · S
Criterios: `/health` 200; `POST /tasks` < 2 s, 401 sin token; `GET` devuelve `en_curso` mientras
corre una tarea falsa de 10 s y luego `terminada`; 404 para id desconocido.
Qué probar: `curl` de los tres endpoints, local y en Cloud Run.

**SP-02 — Deploy en Cloud Run** · P0 · S
Criterios: imagen construida, secretos montados, URL pública responde `/health`, la tarea falsa
termina aunque nadie consulte (CPU sin throttling).
Qué probar: `POST` → esperar 15 s sin consultar → `GET` = `terminada`.

**SP-03 — Cliente VNC sobre websocket** · P0 · M
Criterios: con la URL y contraseña del escritorio propio: conectar, capturar PNG 1280×800, clic
con 120 ms, escribir con Ctrl+A previo, `wait_stable`.
Qué probar: `scripts/vnc_smoke.py` guarda `out/before.png` y `out/after.png` (tras un clic).
Riesgo: auth VNC y librería; decidir en ≤ 30 min (`experiments/2026-10-10-vnc-perception.md`).

**SP-04 — Harness de evaluación** · P0 · S
Criterios: `scripts/eval.py --target <url>` corre `pruebas/*.json`: `/__reset` (token del
escritorio) → `POST /tasks` → poll cada 5 s → `/__check` → valida estado, `respuesta:` y
`claves_razon` → tabla en `experiments/<fecha>-eval/`.
Qué probar: con el agente falso la tabla sale completa (casi todo en rojo).
</details>

<details open><summary><b>T1 — Ver, decidir, actuar</b></summary>

**SP-05 — Percepción: `observe()`** · P0 · M
Criterios: sobre capturas reales: elementos numerados con texto y caja (menús, `Filtrar`,
`Crear cliente`, `Aplicar`, etiquetas de campo, filas); detecta el modal; lee la fecha del
encabezado.
Qué probar: fixtures PNG en `tests/fixtures/` + test unitario; tiempo por captura < 1,5 s.

**SP-06 — Primitivas + bucle del agente** · P0 · L
Criterios: las primitivas de arquitectura §4; el bucle llama a OpenRouter con JSON por paso;
presupuesto de 270 s, 40 pasos y costo; log de cada paso (acción, costo, tiempo).
Qué probar: tarea "abre la lista de clientes y dime cuántos hay en la primera página" llega a
`finish` sola en el escritorio propio.

**SP-07 — Guard + resumen** · P0 · M
Criterios: test de `redact()` (contraseña, token, `SGC-…`); clic destructivo bloqueado; segundo
"guardar" bloqueado; corte a 270 s; formato `respuesta:` / `motivo:`.
Qué probar: `pytest tests/unit`.
</details>

<details open><summary><b>T2 — Ejemplos en verde</b></summary>

**SP-08 — E1–E5 en verde** · P0 · M
Criterios: harness local con los 5 en verde (check + estado + resumen). Cada fallo con su
categoría (percepción, decisión, tiempo, modal, verificación); se ataca la más grande primero.

**SP-09 — Generalización** · P0 · S
Criterios: 2 paráfrasis con valores nuevos + 1 pregunta con fecha relativa, inventadas, en verde
(la verificación de estas se hace a mano en la app si `/__check` no las cubre).
</details>

<details open><summary><b>T3 — Cierre</b></summary>

**SP-10 — Deploy final y corrida pública** · P0 · S
Criterios: deploy verde; harness completo contra la URL pública; tabla en `experiments/`.

**SP-11 — Entrega** · P0 · S
Criterios: README al día; video de 2 min (problema → arquitectura → demo E3 y E5 → incidente
v4.2 resuelto sin tocar código → métricas); repo, URL y video cargados en Frontier antes de las 20:00.
</details>

## Backlog
| Idea | Por qué espera | Se reabre cuando… |
|---|---|---|
| Playbooks deterministas por forma | Recortado por tiempo | El bucle pasa todo y sobra tiempo para bajar costo |
| Mapa de app persistente / huella | La app y el escritorio cambian entre tareas | Hay muchas tareas sobre la misma app |
| Rutas aprendidas de corridas exitosas | Requiere persistencia y router | Después del reto |
