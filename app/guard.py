"""Guard en código (docs/system-architecture.md §5). Se consulta antes de ejecutar cada acción;
si bloquea, el motivo vuelve al LLM como error y la acción no se ejecuta."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.perception import Element, Screen, norm

DESTRUCTIVE = ("eliminar", "borrar", "anular", "revertir", "descartar", "suprimir", "quitar",
               "delete", "remove", "void", "reversar", "dar de baja")
# Verbos de la tarea que autorizan cada familia destructiva.
DESTRUCTIVE_INTENT = {
    "eliminar": ("elimin", "borr", "suprim", "quit"),
    "borrar": ("borr", "elimin", "suprim"),
    "anular": ("anul",),
    "revertir": ("revert", "revers"),
    "reversar": ("revert", "revers"),
    "descartar": ("descart",),
    "suprimir": ("suprim", "elimin", "borr"),
    "quitar": ("quit", "elimin"),
    "delete": ("elimin", "borr", "delete"),
    "remove": ("quit", "elimin", "remove"),
    "void": ("anul", "void"),
    "dar de baja": ("baja", "desactiv"),
}
CONFIRM = ("aplicar", "guardar", "confirmar", "grabar", "registrar", "enviar", "save", "apply",
           "submit", "actualizar", "crear")
CLICKS = ("click", "double_click")


def _is_confirm(text: str) -> bool:
    t = norm(text)
    # "Crear cliente" en una barra abre un formulario; solo cuenta como confirmar dentro de uno.
    return any(t == w or t.startswith(w + " ") for w in CONFIRM)


def form_signature(screen: Screen) -> str:
    """Identidad del formulario visible: las etiquetas de sus campos."""
    labels = sorted(norm(e.label) for e in screen.elements if e.kind == "campo" and e.label)
    return "|".join(labels)


@dataclass
class Guard:
    task: str
    confirmed: dict[tuple[str, str], int] = field(default_factory=dict)
    history: list[tuple[str, str]] = field(default_factory=list)

    def _destructive_allowed(self, word: str) -> bool:
        t = norm(self.task)
        return any(stem in t for stem in DESTRUCTIVE_INTENT.get(word, (word,)))

    def check(self, action: str, args: dict, el: Element | None, screen: Screen) -> str | None:
        if el is not None and action in CLICKS + ("type_into", "select_option", "hover"):
            if screen.modal and not el.in_modal:
                return ("Hay un modal abierto: ese elemento está detrás. Primero cierra el modal con "
                        "su botón no destructivo (Entendido, Aceptar, Cerrar, ×).")
        if el is not None and action in CLICKS:
            t = norm(el.text)
            for w in DESTRUCTIVE:
                if w in t and not self._destructive_allowed(w):
                    return (f"Bloqueado: «{el.text}» es una acción destructiva y la tarea no la pide. "
                            "No se ejecutó.")
            sig = form_signature(screen)
            if sig and _is_confirm(el.text):
                key = (t, sig)
                if self.confirmed.get(key, 0) >= 1:
                    return (f"Bloqueado: ya pulsaste «{el.text}» en este formulario. En esta app "
                            "guardar puede no cerrar el formulario: verifica el resultado en la lista, "
                            "un mensaje o la bitácora; nunca lo pulses dos veces.")
        return None

    def executed(self, action: str, args: dict, el: Element | None, screen: Screen) -> None:
        if el is not None and action in CLICKS:
            sig = form_signature(screen)
            if sig and _is_confirm(el.text):
                key = (norm(el.text), sig)
                self.confirmed[key] = self.confirmed.get(key, 0) + 1

    def stuck(self, action: str, args: dict, screen: Screen) -> bool:
        """Misma pantalla + misma acción 3 veces seguidas."""
        key = (screen.signature(), f"{action}:{sorted(args.items()) if isinstance(args, dict) else args}")
        self.history.append(key)
        return len(self.history) >= 3 and len(set(self.history[-3:])) == 1
