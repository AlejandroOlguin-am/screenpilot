# SIGECOM v3.9 → v4.2: qué cambió con el incidente FR-0153

> Medido en el escritorio propio el 10-oct ~16:15. Base: `sigecom-v3.9-baseline.md`.
> Sirve como **evidencia para el video y el debrief**, y como caso de prueba de robustez.
> **No se hardcodea nada de esto en el agente**: el agente debe resolverlo solo.

## Cambios observados

| Área | v3.9 | v4.2 | Impacto en el agente |
|---|---|---|---|
| Versión / tema | Encabezado azul, "v3.9" | Encabezado **verde oscuro**, "v4.2" | La huella de la app cambia → el mapa aprendido se invalida y se re-aprende |
| **Modal al abrir** | No había | **"Novedades de la versión 4.2"** con botón **`Entendido`** y una `×`. Fondo gris que bloquea todo | Primer paso de cada sesión: detectar y cerrar modales. **Reaparece cada vez que la app se recarga** (lo vi dos veces) |
| Pantalla inicial | Integraciones / vacía | "Bienvenido a SIGECOM" | Nada |
| Botón de búsqueda | `Buscar` (azul) | **`Filtrar`** (verde) | Etiqueta por significado, no por texto |
| Crear registro | `Nuevo cliente` / `Nuevo pedido` a la **izquierda** | **`Crear cliente`** / **`Crear pedido`** a la **derecha** | Igual |
| Orden de la barra | `Nuevo` · `Exportar` | `Exportar` · `Crear …` | No depender de posiciones |
| Botones del formulario | `Guardar` · `Volver` a la izquierda | **`Cerrar` · `Aplicar`** a la **derecha** | Igual |
| **Comportamiento de guardar** | Guardar cierra el formulario y vuelve a la lista | **"Los formularios ahora se aplican sin cerrarse"**: Aplicar guarda y **el formulario sigue abierto** | ⚠️ **Riesgo de duplicados**: si el agente no ve un cambio de pantalla y vuelve a pulsar `Aplicar` en un alta, crea dos registros. Verificar en la lista o la Bitácora, **nunca** re-pulsar |
| Menús | Archivo · Comercial (Maestros ▸ Clientes, Ventas ▸ Pedidos) · Cartera (Facturas) · Herramientas (Bitácora, Reportes, Configuración ▸ Integraciones) · Ayuda | **Iguales** | El mapa de navegación sigue válido |
| Datos | — | Iguales (mismos clientes, mismas facturas; la nota inyectada de CL-0007 sigue) | Las respuestas esperadas no cambian |

## Lecciones que van al diseño
1. **Gestor de modales** antes de cada tarea y tras cada navegación: si hay una capa que oscurece
   y un cuadro con botones, se **lee** (como dato) y se cierra con el botón no destructivo
   (`Entendido`, `Aceptar`, `Cerrar`, `×`). Nunca con `Eliminar` ni `Confirmar` de algo que no se pidió.
2. **Etiquetas por significado**: el LLM recibe las etiquetas que hay en pantalla y la acción
   abstracta (`buscar`, `crear`, `guardar`, `cancelar`); devuelve cuál corresponde. Se guarda en
   caché por app: `{guardar: "Aplicar", buscar: "Filtrar", crear: "Crear cliente"}`.
3. **Guardar = una sola vez + verificar**: pulsar el botón de guardar exactamente una vez y
   confirmar por evidencia (mensaje, Bitácora, la lista). Si no hay evidencia, se reporta `fallida`,
   no se reintenta a ciegas.
4. **Huella de la app = título + versión + menús**: si cambia, el agente lo anota en el log
   ("versión nueva detectada: v3.9 → v4.2") y re-aprende las etiquetas. Ese log es la demo del
   incidente.
