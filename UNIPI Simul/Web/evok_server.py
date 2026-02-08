"""
Web/evok_server.py — Faux serveur EVOK (REST + WebSocket)
═════════════════════════════════════════════════════════
Émule le serveur EVOK Unipi sur 127.0.0.1:8080 pour que
GeV5 puisse tourner sans modification :

  • Svr_Unipi.py  → GET /rest/di/{c}   → lit les DI
  • relais.py     → WS  /ws            → écrit les RO

Conversion EVOK ↔ logique :
─────────────────────────────────────────────────────────
La fonction _coerce01() de Svr_Unipi.py inverse les valeurs :
    EVOK 1 → coerce → 0
    EVOK 0 → coerce → 1

Puis INVERT_DI = {3: True, 4: True, 5: False} re-inverse :
    Si INVERT=True  : final = 1 - coerce(evok)
    Si INVERT=False : final = coerce(evok)

Pour obtenir la valeur logique L désirée dans GeV5 :
    INVERT=True  → evok = L       (identique)
    INVERT=False → evok = 1 - L   (inversé)

Mapping résultant (Svr_Unipi.py config) :
    DI3 (S1, INVERT=True)  : evok = logique
    DI4 (S2, INVERT=True)  : evok = logique
    DI5 (ACK, INVERT=False): evok = 1 - logique
─────────────────────────────────────────────────────────
100 % stdlib Python — aucune dépendance externe.
"""

import hashlib
import base64
import io
import json
import struct
import socket
import socketserver
import threading
import time
from typing import Optional

from API import UniPiAPI

# ─── Configuration EVOK ────────────────────────────────────
EVOK_PORT = 8080

# Mapping : pour chaque DI, True = INVERT_DI dans Svr_Unipi.py
# Si INVERT=True → evok_value = logical_value
# Si INVERT=False → evok_value = 1 - logical_value
INVERT_DI_MAP = {
    3: True,   # Cellule S1
    4: True,   # Cellule S2
    5: False,  # Acquittement
}

# Labels pour les logs
DI_LABELS = {3: "Cellule S1", 4: "Cellule S2", 5: "Acquittement"}
RO_LABELS = {
    1: "Défaut (séc+)", 2: "Cellule", 3: "Alarme N1",
    4: "Alarme N2", 5: "Défaut (séc+)", 6: "Alarme",
    7: "Alarme N2", 8: "Cellule",
}


def _logical_to_evok(di_index: int, logical: bool) -> int:
    """Convertit l'état logique du simulateur en valeur EVOK brute."""
    inverted = INVERT_DI_MAP.get(di_index, False)
    if inverted:
        return 1 if logical else 0
    else:
        return 0 if logical else 1


# ═══════════════════════════════════════════════════════════
#  WEBSOCKET MINIMAL (RFC 6455)
# ═══════════════════════════════════════════════════════════

WS_MAGIC = "258EAFA5-E914-47DA-95CA-5AB9A4D898C8"
OP_TEXT  = 0x1
OP_CLOSE = 0x8
OP_PING  = 0x9
OP_PONG  = 0xA


def _ws_accept_key(client_key: str) -> str:
    h = hashlib.sha1((client_key.strip() + WS_MAGIC).encode()).digest()
    return base64.b64encode(h).decode()


def _ws_read_frame(sock: socket.socket):
    """
    Lit un frame WebSocket complet. Retourne (opcode, payload_bytes) ou None.
    """
    def _recv_exact(n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    hdr = _recv_exact(2)
    if not hdr:
        return None

    b0, b1 = hdr[0], hdr[1]
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F

    if length == 126:
        ext = _recv_exact(2)
        if not ext:
            return None
        length = struct.unpack("!H", ext)[0]
    elif length == 127:
        ext = _recv_exact(8)
        if not ext:
            return None
        length = struct.unpack("!Q", ext)[0]

    mask_key = b""
    if masked:
        mask_key = _recv_exact(4)
        if not mask_key:
            return None

    payload = _recv_exact(length) if length > 0 else b""
    if payload is None:
        return None

    if masked and mask_key:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    return opcode, payload


def _ws_send_frame(sock: socket.socket, opcode: int, payload: bytes = b""):
    """Envoie un frame WebSocket (serveur → client, non masqué)."""
    frame = bytearray()
    frame.append(0x80 | opcode)  # FIN + opcode

    length = len(payload)
    if length < 126:
        frame.append(length)
    elif length < 65536:
        frame.append(126)
        frame.extend(struct.pack("!H", length))
    else:
        frame.append(127)
        frame.extend(struct.pack("!Q", length))

    frame.extend(payload)
    sock.sendall(bytes(frame))


# ═══════════════════════════════════════════════════════════
#  HANDLER TCP (HTTP + WS sur le même port)
# ═══════════════════════════════════════════════════════════

class EvokHandler(socketserver.StreamRequestHandler):
    """
    Gère les requêtes HTTP REST et les connexions WebSocket
    sur le même port 8080, exactement comme le vrai EVOK.
    """

    # Référence vers l'API (injectée par le serveur)
    api: Optional[UniPiAPI] = None
    _log_callback = None

    def handle(self):
        try:
            # Lire la ligne de requête HTTP
            request_line = self.rfile.readline(4096).decode("utf-8", errors="ignore").strip()
            if not request_line:
                return

            parts = request_line.split()
            if len(parts) < 2:
                return

            method = parts[0].upper()
            path = parts[1]

            # Lire les headers
            headers = {}
            while True:
                line = self.rfile.readline(4096).decode("utf-8", errors="ignore").strip()
                if not line:
                    break
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            # WebSocket upgrade ?
            if headers.get("upgrade", "").lower() == "websocket":
                self._handle_websocket(headers)
            elif method == "GET":
                self._handle_rest_get(path, headers)
            else:
                self._send_http(405, {"error": "Method not allowed"})

        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        except Exception as e:
            self._log(f"ERR handler: {e}")

    # ── REST GET ────────────────────────────────────────

    def _handle_rest_get(self, path: str, headers: dict):
        """Répond aux requêtes REST comme un vrai EVOK."""
        path = path.rstrip("/")

        # GET /rest/di  ou  /rest/input  → liste de tous les DI
        if path in ("/rest/di", "/rest/input"):
            self._send_http(200, self._build_all_di())
            return

        # GET /rest/di/{c}  ou  /rest/input/{c}  → un seul DI
        for prefix in ("/rest/di/", "/rest/input/"):
            if path.startswith(prefix):
                try:
                    circuit = int(path[len(prefix):])
                    self._send_http(200, self._build_one_di(circuit))
                except (ValueError, KeyError) as e:
                    self._send_http(404, {"error": str(e)})
                return

        # GET /rest/all  → tous les devices (DI + relais)
        if path == "/rest/all":
            result = self._build_all_di() + self._build_all_ro()
            self._send_http(200, result)
            return

        # GET /rest/relay  → tous les relais
        if path == "/rest/relay":
            self._send_http(200, self._build_all_ro())
            return

        # GET /rest/relay/{c}
        if path.startswith("/rest/relay/"):
            try:
                circuit = int(path[len("/rest/relay/"):])
                self._send_http(200, self._build_one_ro(circuit))
            except (ValueError, KeyError) as e:
                self._send_http(404, {"error": str(e)})
            return

        self._send_http(404, {"error": f"Unknown path: {path}"})

    def _build_all_di(self) -> list:
        """Construit la réponse EVOK pour tous les DI."""
        api = self.api
        if not api:
            return []
        result = []
        for i in range(1, api.NB_DI + 1):
            logical = api.read_di(i)
            evok_val = _logical_to_evok(i, logical)
            result.append({
                "dev": "input",
                "circuit": str(i),
                "value": evok_val,
                "pending": False,
            })
        return result

    def _build_one_di(self, circuit: int) -> dict:
        """Construit la réponse EVOK pour un DI."""
        api = self.api
        if not api:
            return {"dev": "input", "circuit": str(circuit), "value": 0}
        logical = api.read_di(circuit)
        evok_val = _logical_to_evok(circuit, logical)
        return {
            "dev": "input",
            "circuit": str(circuit),
            "value": evok_val,
            "pending": False,
        }

    def _build_all_ro(self) -> list:
        """Construit la réponse EVOK pour tous les relais."""
        api = self.api
        if not api:
            return []
        result = []
        for i in range(1, api.NB_RO + 1):
            result.append({
                "dev": "relay",
                "circuit": str(i),
                "value": 1 if api.read_ro(i) else 0,
                "pending": False,
            })
        return result

    def _build_one_ro(self, circuit: int) -> dict:
        api = self.api
        if not api:
            return {"dev": "relay", "circuit": str(circuit), "value": 0}
        return {
            "dev": "relay",
            "circuit": str(circuit),
            "value": 1 if api.read_ro(circuit) else 0,
            "pending": False,
        }

    def _send_http(self, status: int, body):
        """Envoie une réponse HTTP JSON."""
        payload = json.dumps(body).encode("utf-8")
        reason = {200: "OK", 404: "Not Found", 405: "Method Not Allowed"}.get(status, "OK")
        resp = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8") + payload
        try:
            self.wfile.write(resp)
            self.wfile.flush()
        except Exception:
            pass

    # ── WebSocket ───────────────────────────────────────

    def _handle_websocket(self, headers: dict):
        """Handshake WebSocket puis boucle de réception des commandes relais."""
        client_key = headers.get("sec-websocket-key", "")
        if not client_key:
            self._send_http(400, {"error": "Missing Sec-WebSocket-Key"})
            return

        accept = _ws_accept_key(client_key)
        handshake = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        self.wfile.write(handshake.encode("utf-8"))
        self.wfile.flush()

        self._log("WS client connecté (relais.py ?)")
        sock = self.request  # socket brut

        # Boucle de réception
        while True:
            try:
                result = _ws_read_frame(sock)
                if result is None:
                    break

                opcode, payload = result

                if opcode == OP_TEXT:
                    self._process_ws_command(payload.decode("utf-8", errors="ignore"))
                elif opcode == OP_PING:
                    _ws_send_frame(sock, OP_PONG, payload)
                elif opcode == OP_CLOSE:
                    _ws_send_frame(sock, OP_CLOSE, b"")
                    break

            except (ConnectionResetError, BrokenPipeError, OSError):
                break
            except Exception as e:
                self._log(f"ERR WS frame: {e}")
                break

        self._log("WS client déconnecté")

    def _process_ws_command(self, raw: str):
        """
        Traite une commande WebSocket EVOK.
        Format attendu : {"cmd":"set","dev":"relay","circuit":"3","value":"1"}
        """
        api = self.api
        if not api:
            return

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            self._log(f"WS JSON invalide: {raw}")
            return

        cmd = msg.get("cmd", "")
        dev = msg.get("dev", "").lower()
        circuit = msg.get("circuit", "")
        value = msg.get("value", "")

        if cmd == "set" and dev == "relay":
            try:
                ro_idx = int(circuit)
                ro_val = int(value) != 0
                api.set_ro(ro_idx, ro_val)
                label = RO_LABELS.get(ro_idx, "")
                state_str = "ON" if ro_val else "OFF"
                self._log(f"WS → RO{ro_idx} = {state_str}  ({label})")
            except (ValueError, Exception) as e:
                self._log(f"WS ERR set relay: {e}")
        else:
            self._log(f"WS cmd ignorée: {raw[:80]}")

    def _log(self, msg: str):
        if self._log_callback:
            self._log_callback(msg)
        else:
            print(f"[EVOK] {msg}")


# ═══════════════════════════════════════════════════════════
#  SERVEUR THREADÉ (port 8080)
# ═══════════════════════════════════════════════════════════

class _EvokTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class FakeEvokServer:
    """
    Lance un faux serveur EVOK sur 127.0.0.1:8080.

    Usage:
        server = FakeEvokServer(api)
        server.start()   # non-bloquant (thread daemon)
        ...
        server.stop()
    """

    def __init__(self, api: UniPiAPI, port: int = EVOK_PORT, log_callback=None):
        self._api = api
        self._port = port
        self._log_callback = log_callback
        self._server: Optional[_EvokTCPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        # Injecter l'API et le logger dans le handler (attribut de classe)
        EvokHandler.api = self._api
        EvokHandler._log_callback = self._log_callback

        try:
            self._server = _EvokTCPServer(("127.0.0.1", self._port), EvokHandler)
        except OSError as e:
            print(f"[EVOK] ❌ Impossible de démarrer sur :{self._port} — {e}")
            print(f"[EVOK]    Le vrai EVOK tourne peut-être déjà ?")
            raise

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="FakeEvokServer",
            daemon=True,
        )
        self._thread.start()
        print(f"[EVOK] ✅ Faux serveur EVOK démarré sur 127.0.0.1:{self._port}")
        print(f"[EVOK]    REST : http://127.0.0.1:{self._port}/rest/di/")
        print(f"[EVOK]    WS   : ws://127.0.0.1:{self._port}/ws")

    def stop(self):
        if self._server:
            self._server.shutdown()
            print("[EVOK] Serveur arrêté")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
