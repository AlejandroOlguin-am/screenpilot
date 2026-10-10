"""SP-05: observe() sobre capturas reales del escritorio (tests/fixtures/)."""
from pathlib import Path

import pytest
from PIL import Image

from app.perception import analyze, norm

FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def screens():
    return {p.stem: analyze(Image.open(p)) for p in FIX.glob("*.png")}


def texts(s):
    return [norm(e.text) for e in s.elements]


def test_fecha_del_encabezado(screens):
    for name, s in screens.items():
        assert s.today == "14/10/2026", name


def test_modal_detectado_y_su_boton(screens):
    s = screens["home_modal"]
    assert s.modal is not None
    ent = s.find("Entendido")
    assert ent and ent[0].in_modal
    assert not s.find("Archivo")[0].in_modal
    for name in ("clientes_list", "cliente_form", "menu_comercial"):
        assert screens[name].modal is None, name


def test_lista_de_clientes(screens):
    s = screens["clientes_list"]
    t = texts(s)
    for label in ("filtrar", "crear cliente", "exportar", "siguiente", "cl-0065"):
        assert any(label == x for x in t), label
    campos = {norm(e.label): e for e in s.elements if e.kind == "campo"}
    assert {"nombre", "nit", "ciudad"} <= set(campos)
    assert norm(campos["ciudad"].text) == "todos"


def test_formulario_campos_con_etiqueta(screens):
    s = screens["cliente_form"]
    labels = {norm(e.label).rstrip(" *") for e in s.elements if e.kind == "campo"}
    assert {"razon social o nombre", "nit", "telefono", "ciudad", "direccion", "correo",
            "estado", "observaciones"} <= labels
    assert s.find("Aplicar", exact=True) and s.find("Cerrar", exact=True)


def test_menus_no_son_campos(screens):
    for name in ("menu_comercial", "submenu_maestros"):
        assert not [e for e in screens[name].elements if e.kind == "campo"], name
    assert screens["submenu_maestros"].find("Clientes")


def test_numeracion_y_tiempo(screens):
    for name, s in screens.items():
        assert [e.n for e in s.elements] == list(range(1, len(s.elements) + 1))
        assert s.ocr_s < 2.5, name  # objetivo 1,5 s en Cloud Run (2 CPU); margen en CI
