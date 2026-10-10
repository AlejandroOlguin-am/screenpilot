# Eval 2026-10-10 18:52 · target `http://localhost:8080` · t1-agente

**2/5 en verde**

| Caso | Pasa | Estado | Tiempo | POST | Fallas |
|---|---|---|---|---|---|
| E1 | ❌ | fallida | 170s | 0.01s | estado |
| E2 | ✅ | terminada | 175s | 0.00s | — |
| E3 | ❌ | fallida | 266s | 0.00s | estado, respuesta |
| E4 | ✅ | terminada | 85s | 0.00s | — |
| E5 | ❌ | fallida | 60s | 0.00s | razón 52345678, razón 1019876543 |

## Resúmenes

**E1**
```
El cliente Papelería Los Andes, NIT 901234567, ya existe en el sistema.
motivo: NIT 901234567
```

**E2**
```
Se corrigió la dirección del cliente Distribuciones El Faro a Calle 80 # 24-15.
```

**E3**
```
Se agotó el tiempo de la tarea antes de terminar. Últimos pasos: 16. type_into {"n": 12, "texto": "Ferretería Ruiz"}; 17. type_into {"n": 12, "texto": "Ferretería Ruiz"}; 18. click {"n": 15}; 19. type_into {"n": 12, "texto": "Ferretería Ruiz"}.
```

**E4**
```
Se exportó el reporte de pedidos entregados en septiembre de 2026. Reporte generado: RP-0001.
```

**E5**
```
motivo: La búsqueda de 'Ana Torres' arrojó dos resultados (CL-0005 y CL-0031). No hay información adicional para identificar de forma única a la Ana Torres cuyo teléfono debe ser modificado.
```
