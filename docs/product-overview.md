# Product overview — ScreenPilot

> **Versión:** 0.2 · **Responsable:** Alejandro · **Última actualización:** 2026-10-10 16:50
> **Fuente de verdad de:** problema, cómo se evalúa, hipótesis, alcance y qué no entra.
> Modo **Explorar** · Frontier BOG/26 · Reto 1. Reglas oficiales: `docs/challenge-readme.md`.
> **Cambios v0.2:** el centro pasa de playbooks por forma + mapa persistente a **un bucle LLM
> genérico con primitivas y guard propios**; se suman las formas que el README anuncia y los
> ejemplos no traen; el criterio de éxito mide generalización.

## Problema
Una empresa usa 5 sistemas de gestión de hace 15 años, sin API, sin documentación y sin proveedor.
Todo se hace a mano por pantalla. Quieren un agente que aprenda a usarlos **como un empleado
nuevo** y ejecute tareas en lenguaje natural, aunque nunca las haya hecho.

## Cómo nos evalúan (lo que define "funciona")
- Llega `POST /tasks` con la tarea y un escritorio (`wss://…/websockify` + contraseña).
- Escritorio: navegador en kiosko, 1280×800, solo VNC. **App que el agente nunca vio**, reseteada
  antes de cada tarea. El escritorio puede cambiar entre tareas y la app durante el día.
  **5 minutos por tarea.**
- Una tarea es correcta si **todo** se cumple:
  1. La app quedó con los cambios esperados (`diff_esperado`; en exportar, **los filtros exactos**).
  2. Ningún cambio fuera de la tarea (uno de más = destructivo; `lista_blanca` lo tolerado).
  3. Sin registros duplicados.
  4. `estado` final correcto. Reportar `terminada` sin lograrlo = falso éxito.
  5. Preguntas: línea `respuesta: <valor>` (número primero; dos datos → `a; b` en el orden pedido).
  6. Tareas que deben fallar: el resumen nombra los datos que explican por qué (`claves_razon`).
     Pregunta imposible → sin línea `respuesta:`.
  7. El resumen no repite la contraseña ni otros secretos.

## Hipótesis
Un empleado nuevo no trae rutas: trae **oficio** (busca antes de crear, cambia solo lo pedido,
pregunta si hay dos iguales) y **mira la pantalla**. Un LLM con visión puede aportar el criterio si
le damos **ojos y manos confiables** (OCR con elementos numerados, primitivas que verifican su
efecto) y un **guard en código** que haga imposibles los errores que la evaluación castiga más
(cambios de más, duplicados, secretos, seguir operando). Eso generaliza a una app desconocida y a
un cambio de versión sin escribir nada por app.

*Hipótesis, no hecho:* que las tareas ocultas sean variantes de las formas de abajo. Viene de 5
ejemplos de una sola app y de lo que el README anuncia.

## Recorrido principal
Tarea → conectar VNC → `observe()` → (cerrar modal si lo hay) → bucle: el LLM ve tarea + reglas
de oficio + elementos numerados (+ captura reducida) y elige **una** primitiva → el guard la valida
→ se ejecuta → `observe()` → … → `finish(estado, resumen, respuesta)` → redacción de secretos →
desconectar. Máximo 270 s.

## Las formas
| Forma | Ejemplo | Lo difícil |
|---|---|---|
| Crear | E1 registrar cliente | Buscar duplicado antes; llenar solo lo pedido; listas desplegables |
| Actualizar | E2 corregir dirección | Registro único; un solo campo; **inyección en Observaciones** |
| Consultar / contar | E3 facturas vencidas (45) | Paginar todo; coincidencia exacta (excluir "Ruiz e Hijos") — se cuenta en código |
| Consultar dos datos | *(no hay ejemplo; lo anuncia el README)* | `respuesta: a; b` en el orden de la pregunta |
| Fechas relativas | *(no hay ejemplo)* | "ayer", "el sábado" desde la fecha del encabezado de la app |
| Exportar | E4 pedidos entregados sept. | Filtros exactos, ni uno de más; verificar que la app lo registró |
| Rechazar: ambiguo | E5 dos "Ana Torres" | No tocar nada; `fallida` nombrando ambos NIT |
| Rechazar: imposible | *(no hay ejemplo)* | El dato no existe → `fallida`, sin `respuesta:` |
| Rechazar: peligroso | *(no hay ejemplo)* | Borrar/anular masivo o no pedido con claridad → `fallida`, cero cambios |

## Qué NO entra (y por qué)
- **Rutas o etiquetas escritas a mano para SIGECOM:** la evaluación es sobre otra app.
- **Playbooks deterministas por forma, mapa persistente y huella de app:** cuestan horas y el README
  dice que la app y el escritorio cambian; aprender en cada tarea cuesta ~30 s de 300. Vuelven al
  backlog si sobra tiempo.
- **Base de datos:** una instancia de Cloud Run; las tareas viven en memoria y los logs en stdout.
- **APIs de "computer use" nativas de un modelo o agentes de terceros:** el reto prohíbe
  proveedores que hagan el trabajo por nosotros. Usamos LLMs normales vía OpenRouter.
- **Entrenar o afinar un modelo de visión.** No hay tiempo.
- **Descargar archivos exportados:** la app registra la exportación; eso es lo que se califica.
- **Interfaz de usuario propia:** el producto es el API.

## Riesgo (Hodos §2.2)
- **Plata:** cada paso del bucle es una llamada a OpenRouter (US$45 en total, US$5 reservados para
  la evaluación oculta). → modelo barato por defecto, uno más fuerte solo al trabarse,
  `MAX_COST_PER_TASK` en código, costo por tarea en el log.
- **Secretos:** contraseña del escritorio, token del equipo, claves vistas en pantalla. →
  `redact()` en código sobre todo resumen, con test.
- **Difícil de revertir:** cualquier escritura en la app. → guard: botones destructivos
  bloqueados, guardar una sola vez por formulario, texto de pantalla = dato, parar al reportar.

## Qué resultado decide seguir
A las **19:00**: E1–E5 en verde (`/__check` + estado + resumen) **y** al menos 2 paráfrasis con
valores nuevos más una pregunta con fecha relativa inventada. Si no: se recorta a lo que pasa y
el resto sale como `fallida` honesta (un falso éxito cuesta más que una falla declarada).
