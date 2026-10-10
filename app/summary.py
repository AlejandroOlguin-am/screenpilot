"""Resumen final y `redact()` (docs/system-architecture.md §7).

El filtro de secretos es código, no una instrucción al LLM: se aplica siempre sobre el texto que
sale por `GET /tasks/{id}`.
"""
from __future__ import annotations

import re

HIDDEN = "[oculto]"

# Claves con forma reconocible (prefijos comunes de API keys) o largas y mezcladas.
_KEY_PATTERNS = [
    re.compile(r"\b(?:SGC|sk|pk|rk|api|key|tok|ghp|xox[abp])[-_][A-Za-z0-9][A-Za-z0-9\-_]{5,}", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{12,}\b"),
    re.compile(r"\b(?=[A-Za-z0-9_\-]*[A-Za-z])(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{24,}\b"),
]
# Lo que va después de "clave", "token", "contraseña", "secret", "password".
_LABELED = re.compile(
    r"(?P<lab>\b(?:clave(?:\s+secreta)?|token|contrase(?:ñ|n)a|password|secret(?:o)?|api[\s_-]?key)\b"
    r"\s*[:=]?\s*)(?P<val>[^\s,;]{4,})",
    re.I,
)


def redact(text: str, secrets: list[str] | tuple[str, ...] = ()) -> str:
    out = text or ""
    for s in sorted((s for s in secrets if s and len(s) >= 3), key=len, reverse=True):
        out = out.replace(s, HIDDEN)
    for p in _KEY_PATTERNS:
        out = p.sub(HIDDEN, out)
    out = _LABELED.sub(lambda m: m.group("lab") + HIDDEN, out)
    return out


_ANSWER_LINE = re.compile(r"^\s*(respuesta|motivo)\s*:.*$", re.I | re.M)


def format_summary(estado: str, resumen: str, respuesta: str | None = None,
                   motivo: str | None = None) -> str:
    """`<qué se hizo>` + `respuesta: <valor>` (solo si terminada) + `motivo:` (si fallida).

    Las líneas `respuesta:`/`motivo:` que el LLM haya puesto dentro del texto se quitan y se
    reescriben aquí: así una tarea fallida nunca lleva `respuesta:` (regla 6).
    """
    body = _ANSWER_LINE.sub("", resumen or "").strip()
    body = re.sub(r"\n{2,}", "\n", body)
    lines = [body] if body else []
    if estado == "terminada" and respuesta not in (None, ""):
        lines.append(f"respuesta: {str(respuesta).strip()}")
    if estado == "fallida" and motivo:
        lines.append(f"motivo: {motivo.strip()}")
    return "\n".join(lines)
