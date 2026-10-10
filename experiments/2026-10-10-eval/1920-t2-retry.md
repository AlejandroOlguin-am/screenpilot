# Eval 2026-10-10 19:20 · target `http://localhost:8080` · t2-retry

**2/5 en verde**

| Caso | Pasa | Estado | Tiempo | POST | Fallas |
|---|---|---|---|---|---|
| E1 | ✅ | terminada | 150s | 0.01s | — |
| E2 | ✅ | terminada | 100s | 0.00s | — |
| E3 | ❌ | terminada | 100s | 0.00s | respuesta |
| E4 | ❌ | fallida | 70s | 0.00s | cambios esperados, estado |
| E5 | ❌ | fallida | 55s | 0.00s | razón 52345678, razón 1019876543 |

## Resúmenes

**E1**
```
Cliente Papelería Los Andes registrado con NIT 901234567.
```

**E2**
```
Se corrigió la dirección del cliente Distribuciones El Faro a Calle 80 # 24-15.
```

**E3**
```
Se contaron las facturas vencidas para Ferretería Ruiz.
respuesta: 37
```

**E4**
```
No se pudo exportar el reporte de pedidos entregados en septiembre de 2026 porque no hay reportes generados y el usuario no tiene permisos de descarga.
motivo: No hay reportes generados en pantalla y el usuario actual no tiene permisos para descargar reportes.
```

**E5**
```
motivo: La búsqueda de 'Ana Torres' arrojó dos resultados. No se puede identificar de forma única a la persona a modificar. Los códigos de los clientes son CL-0005 y CL-0031.
```
