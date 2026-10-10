"""SP-07: guard en código, formato del resumen y redact()."""
from app.guard import Guard
from app.perception import Element, Screen
from app.summary import format_summary, redact


def el(n, text, kind="texto", label="", in_modal=False):
    return Element(n, text, 10 * n, 10, 50, 20, kind=kind, label=label, in_modal=in_modal)


def form_screen():
    els = [el(1, "", "campo", "Telefono *"), el(2, "", "campo", "NIT *"),
           el(3, "Aplicar"), el(4, "Eliminar"), el(5, "Cerrar")]
    return Screen(els)


# ---------- redact ----------
def test_redact_contrasena_y_token():
    s = redact("hice login con Pa$$w0rd!x y token abc123TOKENxyz", ["Pa$$w0rd!x", "abc123TOKENxyz"])
    assert "Pa$$w0rd!x" not in s and "abc123TOKENxyz" not in s and "[oculto]" in s


def test_redact_claves_con_forma():
    for k in ("SGC-LIVE-8f3a9c2d71", "sk-or-v1-0123456789abcdef", "AKIAABCDEFGHIJKLMNOP"):
        assert k not in redact(f"La integración muestra {k} en pantalla"), k


def test_redact_junto_a_etiqueta():
    s = redact("clave secreta: x9Kp2mQ7 y contraseña=hunter22")
    assert "x9Kp2mQ7" not in s and "hunter22" not in s


def test_redact_no_toca_datos_de_negocio():
    s = "Cliente CL-0007 NIT 901234567 teléfono 3157654321 factura FV-10159"
    assert redact(s) == s


# ---------- formato ----------
def test_formato_respuesta_y_motivo():
    assert format_summary("terminada", "Conté las facturas.", "45") == "Conté las facturas.\nrespuesta: 45"
    out = format_summary("fallida", "Hay dos Ana Torres.\nrespuesta: 2", "2", "NIT 52345678 y 1019876543")
    assert "respuesta:" not in out and out.endswith("motivo: NIT 52345678 y 1019876543")


# ---------- guard ----------
def test_destructivo_bloqueado_salvo_intencion():
    scr = form_screen()
    assert Guard("Cambia el teléfono de Ana").check("click", {"n": 4}, scr.get(4), scr)
    assert Guard("Elimina el cliente CL-0099").check("click", {"n": 4}, scr.get(4), scr) is None


def test_guardar_una_sola_vez():
    g, scr = Guard("Registra al cliente X"), form_screen()
    assert g.check("click", {"n": 3}, scr.get(3), scr) is None
    g.executed("click", {"n": 3}, scr.get(3), scr)
    assert "ya pulsaste" in g.check("click", {"n": 3}, scr.get(3), scr)
    assert g.check("click", {"n": 5}, scr.get(5), scr) is None  # Cerrar sigue permitido


def test_modal_bloquea_lo_de_atras():
    scr = Screen([el(1, "Archivo"), el(2, "Entendido", in_modal=True)], modal=(0, 0, 10, 10))
    g = Guard("abre clientes")
    assert g.check("click", {"n": 1}, scr.get(1), scr)
    assert g.check("click", {"n": 2}, scr.get(2), scr) is None


def test_bucle_trabado():
    g, scr = Guard("x"), form_screen()
    assert not g.stuck("click", {"n": 1}, scr)
    assert not g.stuck("click", {"n": 1}, scr)
    assert g.stuck("click", {"n": 1}, scr)
