"""Cliente RFB (VNC) sobre websocket — docs/system-architecture.md §3.

Habla el protocolo RFB 3.8 directo por `wss://…/websockify` (subprotocolo `binary`): no hay
puente TCP. Un lector en segundo plano mantiene el framebuffer al día pidiendo actualizaciones
incrementales continuas; así `wait_stable()` sabe cuándo la pantalla dejó de repintar.

Mecánica medida (AGENTS.md): clic = bajar → ≥120 ms → soltar; repinta hasta 1 s; escribir sobre
un campo concatena (Ctrl+A antes, lo hace la primitiva, no este módulo).
"""
from __future__ import annotations

import asyncio
import logging
import struct
import time

import numpy as np
import websockets
from Crypto.Cipher import DES
from PIL import Image

log = logging.getLogger("screenpilot.vnc")

CLICK_HOLD_S = 0.12
KEY_GAP_S = 0.015

KEYSYMS = {
    "enter": 0xFF0D, "return": 0xFF0D, "tab": 0xFF09, "escape": 0xFF1B, "esc": 0xFF1B,
    "backspace": 0xFF08, "delete": 0xFFFF, "home": 0xFF50, "end": 0xFF57,
    "left": 0xFF51, "up": 0xFF52, "right": 0xFF53, "down": 0xFF54,
    "pageup": 0xFF55, "pagedown": 0xFF56, "space": 0x20,
    "ctrl": 0xFFE3, "shift": 0xFFE1, "alt": 0xFFE9,
    **{f"f{i}": 0xFFBE + i - 1 for i in range(1, 13)},
}


def normalize_url(url: str) -> str:
    """Acepta `https://host`, `wss://host` o `wss://host/websockify`."""
    url = url.strip().rstrip("/")
    if url.startswith("https://"):
        url = "wss://" + url[len("https://"):]
    elif url.startswith("http://"):
        url = "ws://" + url[len("http://"):]
    if not url.endswith("/websockify"):
        url += "/websockify"
    return url


def char_keysym(ch: str) -> int:
    code = ord(ch)
    if ch == "\n":
        return KEYSYMS["enter"]
    if code < 0x100:
        return code
    return 0x01000000 + code


def _vnc_auth_response(password: str, challenge: bytes) -> bytes:
    key = password.encode("latin-1", "replace")[:8].ljust(8, b"\0")
    # VNC usa DES con los bits de cada byte de la clave invertidos.
    key = bytes(int(f"{b:08b}"[::-1], 2) for b in key)
    return DES.new(key, DES.MODE_ECB).encrypt(challenge)


class VNCError(RuntimeError):
    pass


class VNCSession:
    def __init__(self, url: str, password: str):
        self.url = normalize_url(url)
        self._password = password
        self._ws = None
        self._buf = bytearray()
        self._data_evt = asyncio.Event()
        self._reader: asyncio.Task | None = None
        self.width = self.height = 0
        self.fb: np.ndarray | None = None  # (h, w, 3) RGB
        self.last_change = 0.0
        self.updates = 0
        self._update_evt = asyncio.Event()
        self._buttons = 0
        self._pointer = (0, 0)

    # ---------- transporte ----------
    async def _recv_into_buf(self) -> None:
        msg = await self._ws.recv()
        if isinstance(msg, str):
            msg = msg.encode("latin-1")
        self._buf.extend(msg)

    async def _read(self, n: int) -> bytes:
        while len(self._buf) < n:
            await self._recv_into_buf()
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    async def _send(self, data: bytes) -> None:
        await self._ws.send(data)

    # ---------- ciclo de vida ----------
    async def connect(self, timeout: float = 20) -> None:
        self._ws = await asyncio.wait_for(
            websockets.connect(self.url, subprotocols=["binary"], max_size=None,
                               ping_interval=20, open_timeout=timeout),
            timeout,
        )
        await asyncio.wait_for(self._handshake(), timeout)
        self._reader = asyncio.create_task(self._read_loop())
        await self._request_update(incremental=False)
        await self.wait_update(timeout=10)
        log.info("VNC conectado %dx%d", self.width, self.height)

    async def _handshake(self) -> None:
        version = await self._read(12)
        if not version.startswith(b"RFB "):
            raise VNCError(f"no es un servidor RFB: {version!r}")
        await self._send(b"RFB 003.008\n")
        n = (await self._read(1))[0]
        if n == 0:
            (ln,) = struct.unpack(">I", await self._read(4))
            raise VNCError("servidor rechazó la conexión: " + (await self._read(ln)).decode(errors="replace"))
        types = await self._read(n)
        if 2 in types:
            await self._send(bytes([2]))
            challenge = await self._read(16)
            await self._send(_vnc_auth_response(self._password, challenge))
        elif 1 in types:
            await self._send(bytes([1]))
        else:
            raise VNCError(f"tipos de seguridad no soportados: {list(types)}")
        (result,) = struct.unpack(">I", await self._read(4))
        if result != 0:
            raise VNCError("autenticación VNC fallida")
        await self._send(bytes([1]))  # ClientInit, shared
        w, h = struct.unpack(">HH", await self._read(4))
        await self._read(16)  # pixel format del servidor; lo reemplazamos
        (ln,) = struct.unpack(">I", await self._read(4))
        await self._read(ln)
        self.width, self.height = w, h
        self.fb = np.zeros((h, w, 3), dtype=np.uint8)
        # 32 bpp, depth 24, little-endian, true color, BGRX
        pf = struct.pack(">BBBBHHHBBB3x", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
        await self._send(struct.pack(">B3x", 0) + pf)
        encodings = [0, 1]  # Raw, CopyRect
        await self._send(struct.pack(">BxH", 2, len(encodings)) + struct.pack(f">{len(encodings)}i", *encodings))

    async def close(self) -> None:
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._ws:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
        self._ws = None
        log.info("VNC cerrado")

    async def __aenter__(self) -> "VNCSession":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # ---------- framebuffer ----------
    async def _request_update(self, incremental: bool = True) -> None:
        await self._send(struct.pack(">BBHHHH", 3, 1 if incremental else 0, 0, 0, self.width, self.height))

    async def _read_loop(self) -> None:
        try:
            while True:
                mtype = (await self._read(1))[0]
                if mtype == 0:
                    await self._read(1)
                    (nrects,) = struct.unpack(">H", await self._read(2))
                    changed = False
                    for _ in range(nrects):
                        x, y, w, h, enc = struct.unpack(">HHHHi", await self._read(12))
                        if enc == 0:
                            raw = await self._read(w * h * 4)
                            px = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)
                            self.fb[y:y + h, x:x + w] = px[:, :, 2::-1]
                            changed = changed or (w * h > 0)
                        elif enc == 1:
                            sx, sy = struct.unpack(">HH", await self._read(4))
                            self.fb[y:y + h, x:x + w] = self.fb[sy:sy + h, sx:sx + w].copy()
                            changed = True
                        else:
                            raise VNCError(f"encoding inesperado {enc}")
                    if changed:
                        self.last_change = time.monotonic()
                    self.updates += 1
                    self._update_evt.set()
                    await self._request_update(incremental=True)
                elif mtype == 1:
                    await self._read(3)
                    (n,) = struct.unpack(">H", await self._read(2))
                    await self._read(n * 6)
                elif mtype == 2:
                    pass
                elif mtype == 3:
                    await self._read(3)
                    (ln,) = struct.unpack(">I", await self._read(4))
                    await self._read(ln)
                else:
                    raise VNCError(f"mensaje de servidor desconocido {mtype}")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("lector VNC terminó")

    async def wait_update(self, timeout: float = 5) -> bool:
        self._update_evt.clear()
        try:
            await asyncio.wait_for(self._update_evt.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def wait_stable(self, quiet: float = 0.6, min_wait: float = 0.35, max_wait: float = 3.0) -> None:
        """Espera a que no haya cambios durante `quiet` s (la app repinta hasta 1 s)."""
        start = time.monotonic()
        await asyncio.sleep(min_wait)
        while time.monotonic() - start < max_wait:
            if time.monotonic() - max(self.last_change, start) >= quiet:
                return
            await asyncio.sleep(0.05)

    async def settle(self, since: float, first_change: float = 1.5) -> None:
        """Tras una acción: espera a que la pantalla empiece a cambiar (hasta `first_change` s)
        y luego a que se quede quieta. Sin esto, se captura antes de que la app repinte."""
        start = time.monotonic()
        while self.last_change <= since and time.monotonic() - start < first_change:
            await asyncio.sleep(0.05)
        await self.wait_stable(min_wait=0.1)

    def capture(self) -> Image.Image:
        return Image.fromarray(self.fb.copy(), "RGB")

    # ---------- entrada ----------
    async def _pointer_event(self, x: int, y: int, buttons: int) -> None:
        x = max(0, min(self.width - 1, int(x)))
        y = max(0, min(self.height - 1, int(y)))
        self._pointer = (x, y)
        await self._send(struct.pack(">BBHH", 5, buttons, x, y))

    async def move(self, x: int, y: int) -> None:
        await self._pointer_event(x, y, 0)

    async def click(self, x: int, y: int, button: int = 1) -> None:
        mask = {1: 1, 2: 2, 3: 4}[button]
        await self.move(x, y)
        await asyncio.sleep(0.05)
        await self._pointer_event(x, y, mask)
        await asyncio.sleep(CLICK_HOLD_S)
        await self._pointer_event(x, y, 0)

    async def double_click(self, x: int, y: int) -> None:
        await self.click(x, y)
        await asyncio.sleep(0.08)
        await self.click(x, y)

    async def scroll(self, direction: str, clicks: int = 3, x: int | None = None, y: int | None = None) -> None:
        mask = 8 if direction == "up" else 16
        x, y = (x, y) if x is not None else self._pointer
        for _ in range(clicks):
            await self._pointer_event(x, y, mask)
            await asyncio.sleep(0.03)
            await self._pointer_event(x, y, 0)
            await asyncio.sleep(0.05)

    async def _key_event(self, keysym: int, down: bool) -> None:
        await self._send(struct.pack(">BBxxI", 4, 1 if down else 0, keysym))

    async def key(self, name: str) -> None:
        """`enter`, `tab`, `ctrl+a`, `shift+tab`… (combinaciones con `+`)."""
        parts = [p.strip().lower() for p in name.split("+")]
        syms = [KEYSYMS[p] if p in KEYSYMS else char_keysym(p) for p in parts]
        for s in syms:
            await self._key_event(s, True)
            await asyncio.sleep(KEY_GAP_S)
        for s in reversed(syms):
            await self._key_event(s, False)
            await asyncio.sleep(KEY_GAP_S)

    async def type_text(self, text: str) -> None:
        for ch in text:
            s = char_keysym(ch)
            await self._key_event(s, True)
            await asyncio.sleep(KEY_GAP_S)
            await self._key_event(s, False)
            await asyncio.sleep(KEY_GAP_S)
