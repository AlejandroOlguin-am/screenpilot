# Experimento — Canal VNC y percepción

> 10-oct · SP-03 / SP-05 · Timebox: 45 min en total

## Hipótesis
1. **Canal:** un cliente VNC de Python (asyncvnc o vncdotool) conectado a un puente local
   TCP⇄`wss://…/websockify` se autentica con la contraseña del escritorio y puede capturar,
   hacer clic y escribir de forma confiable.
2. **Percepción:** con OCR sobre la captura 1280×800 (escalada ×2) se leen todas las etiquetas,
   los botones y las filas de las tablas de SIGECOM v4.2 sin LLM.
3. **Grounding semántico:** un modelo barato de visión vía OpenRouter elige bien la etiqueta para
   una acción abstracta (`guardar` → `Aplicar`) en ≥ 95 % de los casos, con costo < US$0,005 por
   llamada.

## Cómo se corre
- `scripts/vnc_smoke.py`: conectar, capturar, abrir Comercial ▸ Maestros ▸ Clientes, capturar.
  Medir latencia de captura y de `wait_stable`.
- `scripts/ocr_bench.py`: sobre 6 capturas (inicio con modal, Clientes, formulario CL-0007,
  Pedidos, Facturas página 1, Bitácora) comparar **Tesseract spa** y **RapidOCR**: % de etiquetas
  clave encontradas, % de celdas de tabla correctas y tiempo por captura.
- `scripts/grounding_bench.py`: 20 preguntas (acción abstracta + lista de textos en pantalla)
  contra 2 o 3 modelos baratos. Medir aciertos, latencia y costo.

## Resultado
(completar: tablas con los números)

## Decisión
(completar: librería VNC, motor OCR, modelo por defecto y de respaldo)
Si el canal directo no funciona en 30 min → Playwright con la página noVNC (plan B aprobado).
