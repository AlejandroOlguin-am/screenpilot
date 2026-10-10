"""Harness de evaluación (SP-04): reproduce la evaluación del reto sobre el escritorio propio.

Por cada prueba: /__reset → POST /tasks → poll cada 5 s (máx. 300 s) → /__check → valida estado,
línea `respuesta:`, `claves_razon` y secretos en el resumen. Deja la tabla en experiments/.

Uso: python scripts/eval.py --target http://localhost:8080 [--only E3,E5] [--cases pruebas]
Lee de .env: TEAM_TOKEN, DESKTOP_URL, DESKTOP_PASSWORD, DESKTOP_TOKEN.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.vnc_smoke import load_env  # noqa: E402

POLL_S = 5
TASK_LIMIT_S = 300


def desktop_base(ws_url: str) -> str:
    u = ws_url.replace("wss://", "https://").replace("ws://", "http://")
    return u.removesuffix("/websockify").rstrip("/")


def first_number(s: str) -> str | None:
    m = re.search(r"-?\d[\d.,]*", s)
    return m.group(0) if m else None


def norm_num(s: str) -> str:
    return re.sub(r"[.,\s]", "", s)


def check_summary(case: dict, estado: str, resumen: str, secrets: list[str]) -> list[tuple[str, bool]]:
    out = [("estado", estado == case["estado_esperado"])]
    lines = [l for l in resumen.splitlines() if l.strip().lower().startswith("respuesta:")]
    if "respuesta_esperada" in case:
        exp = str(case["respuesta_esperada"])
        ok = False
        if lines:
            val = lines[0].split(":", 1)[1].strip()
            if re.fullmatch(r"-?\d[\d.,]*", exp):
                n = first_number(val)
                ok = n is not None and norm_num(n) == norm_num(exp)
            else:
                ok = val.lower() == exp.lower()
        out.append(("respuesta", ok))
    elif case["estado_esperado"] == "fallida":
        out.append(("sin respuesta:", not lines))
    for k in case.get("claves_razon", []):
        out.append((f"razón {k}", k in resumen))
    out.append(("sin secretos", not any(s and s in resumen for s in secrets)))
    return out


def run_case(cli: httpx.Client, target: str, case: dict, env: dict) -> dict:
    base = desktop_base(env["DESKTOP_URL"])
    dauth = {"Authorization": f"Bearer {env['DESKTOP_TOKEN']}"}
    tauth = {"Authorization": f"Bearer {env['TEAM_TOKEN']}"}
    r = cli.post(f"{base}/__reset", headers=dauth, timeout=90)
    r.raise_for_status()
    time.sleep(3)
    t0 = time.monotonic()
    r = cli.post(f"{target}/tasks", headers=tauth, timeout=10, json={
        "tarea": case["instruccion"],
        "escritorio": {"url": env["DESKTOP_URL"], "password": env["DESKTOP_PASSWORD"]},
    })
    post_s = time.monotonic() - t0
    r.raise_for_status()
    tid = r.json()["task_id"]
    estado, resumen = "en_curso", ""
    while time.monotonic() - t0 < TASK_LIMIT_S:
        time.sleep(POLL_S)
        j = cli.get(f"{target}/tasks/{tid}", headers=tauth, timeout=10).json()
        estado, resumen = j["estado"], j.get("resumen", "")
        if estado != "en_curso":
            break
    dur = time.monotonic() - t0
    chk = cli.post(f"{base}/__check", headers=dauth, json=case, timeout=30).json()
    checks = [(c["nombre"], c["ok"]) for c in chk.get("checks", [])]
    checks += check_summary(case, estado, resumen, [env["DESKTOP_PASSWORD"], env["TEAM_TOKEN"], env["DESKTOP_TOKEN"]])
    return {"id": case["id"], "pass": all(ok for _, ok in checks), "estado": estado, "dur": dur,
            "post_s": post_s, "checks": checks, "resumen": resumen}


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--only")
    ap.add_argument("--cases", default=str(ROOT / "pruebas"))
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    env = {k: os.environ[k] for k in ("TEAM_TOKEN", "DESKTOP_URL", "DESKTOP_PASSWORD", "DESKTOP_TOKEN")}
    cases = [json.loads(p.read_text()) for p in sorted(Path(a.cases).glob("*.json"))]
    if a.only:
        ids = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in ids]
    results = []
    with httpx.Client() as cli:
        for c in cases:
            res = run_case(cli, a.target.rstrip("/"), c, env)
            fails = [n for n, ok in res["checks"] if not ok]
            print(f"{res['id']}: {'✅' if res['pass'] else '❌'} {res['estado']} {res['dur']:.0f}s"
                  + (f" — falla: {', '.join(fails)}" if fails else ""), flush=True)
            results.append(res)
    now = datetime.now()
    d = ROOT / "experiments" / f"{now:%Y-%m-%d}-eval"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{now:%H%M}{('-' + a.tag) if a.tag else ''}.md"
    lines = [f"# Eval {now:%Y-%m-%d %H:%M} · target `{a.target}`" + (f" · {a.tag}" if a.tag else ""), "",
             f"**{sum(r['pass'] for r in results)}/{len(results)} en verde**", "",
             "| Caso | Pasa | Estado | Tiempo | POST | Fallas |", "|---|---|---|---|---|---|"]
    for r in results:
        fails = ", ".join(n for n, ok in r["checks"] if not ok) or "—"
        lines.append(f"| {r['id']} | {'✅' if r['pass'] else '❌'} | {r['estado']} | {r['dur']:.0f}s | {r['post_s']:.2f}s | {fails} |")
    lines += ["", "## Resúmenes", ""]
    for r in results:
        lines += [f"**{r['id']}**", "```", r["resumen"], "```", ""]
    f.write_text("\n".join(lines))
    print(f"{sum(r['pass'] for r in results)}/{len(results)} → {f.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
