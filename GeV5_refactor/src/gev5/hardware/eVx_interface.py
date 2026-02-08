import socket
import threading
from pathlib import Path

from ..core.alarmes.alarmes import AlarmeThread
from ..core.comptage.comptage import ComptageThread


def _version_string() -> str:
    root = Path(__file__).resolve().parents[3]
    version_path = root / "static" / "version.txt"
    try:
        return version_path.read_text(encoding="utf-8").splitlines()[0].strip()
    except Exception:
        return "unknown"


class eVx_Thread(threading.Thread):
    def __init__(self, client_socket, client_address):
        super().__init__(daemon=True)
        self.client_socket = client_socket
        self.client_address = client_address
        self.ver = _version_string()

    def _fond(self, idx: int) -> int:
        return int(AlarmeThread.fond.get(idx, 0.0))

    def _suiveur(self, idx: int) -> int:
        return int(AlarmeThread.fond.get(idx, 0.0))

    def _val_max(self, idx: int) -> int:
        return int(ComptageThread.compteur.get(idx, 0.0))

    def run(self):
        try:
            while True:
                data = self.client_socket.recv(1024)
                if not data:
                    break
                print(f"Received from {self.client_address}: {data.decode('utf-8')}")

                string = "{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{},{},{}".format(
                    self._fond(1), self._fond(2),
                    self._fond(1) + self._fond(2),
                    self._suiveur(1), self._suiveur(2),
                    self._suiveur(1) + self._suiveur(2),
                    self._val_max(1), self._val_max(2),
                    self._val_max(1) + self._val_max(2),
                    AlarmeThread.alarme_resultat.get(1, 0), AlarmeThread.alarme_resultat.get(2, 0),
                    AlarmeThread.alarme_resultat.get(1, 0) + AlarmeThread.alarme_resultat.get(2, 0),
                )

                string_2 = "{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{:6},{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(
                    self._fond(1), self._fond(2),
                    self._fond(3), self._fond(4),
                    self._fond(5), self._fond(6),
                    self._fond(7), self._fond(8),
                    self._fond(9), self._fond(10),
                    self._fond(11), self._fond(12),
                    sum(self._fond(i) for i in range(1, 13)),
                    self._suiveur(1), self._suiveur(2),
                    self._suiveur(3), self._suiveur(4),
                    self._suiveur(5), self._suiveur(6),
                    self._suiveur(7), self._suiveur(8),
                    self._suiveur(9), self._suiveur(10),
                    self._suiveur(11), self._suiveur(12),
                    sum(self._suiveur(i) for i in range(1, 13)),
                    self._val_max(1), self._val_max(2),
                    self._val_max(3), self._val_max(4),
                    self._val_max(5), self._val_max(6),
                    self._val_max(7), self._val_max(8),
                    self._val_max(9), self._val_max(10),
                    self._val_max(11), self._val_max(12),
                    sum(self._val_max(i) for i in range(1, 13)),
                    AlarmeThread.alarme_resultat.get(1, 0), AlarmeThread.alarme_resultat.get(2, 0),
                    AlarmeThread.alarme_resultat.get(3, 0), AlarmeThread.alarme_resultat.get(4, 0),
                    AlarmeThread.alarme_resultat.get(5, 0), AlarmeThread.alarme_resultat.get(6, 0),
                    AlarmeThread.alarme_resultat.get(7, 0), AlarmeThread.alarme_resultat.get(8, 0),
                    AlarmeThread.alarme_resultat.get(9, 0), AlarmeThread.alarme_resultat.get(10, 0),
                    AlarmeThread.alarme_resultat.get(11, 0), AlarmeThread.alarme_resultat.get(12, 0),
                    sum(AlarmeThread.alarme_resultat.get(i, 0) for i in range(1, 13)),
                )

                length = len(string)
                string = "{:3}{}".format(length, string)
                length_2 = len(string_2)
                string_2 = "{:3}{}".format(length_2, string_2)
                print(data)

                if "LireValeursRadioactivite" in str(data):
                    self.client_socket.sendall(string.encode("utf-8"))
                if "LireValeursRadioactivite_2" in str(data):
                    self.client_socket.sendall(string.encode("utf-8"))
                if "bruitFondV1" in str(data):
                    self.client_socket.sendall(str(self._fond(1)).encode("utf-8"))
                if "bruitFondV2" in str(data):
                    self.client_socket.sendall(str(self._fond(2)).encode("utf-8"))
                if "bruitFondV3" in str(data):
                    self.client_socket.sendall(str(self._fond(3)).encode("utf-8"))
                if "bruitFondV4" in str(data):
                    self.client_socket.sendall(str(self._fond(4)).encode("utf-8"))
                if "bruitFondVSomme" in str(data):
                    self.client_socket.sendall(str(sum(self._fond(i) for i in range(1, 5))).encode("utf-8"))
                if "SeuilAlarmeV1" in str(data):
                    self.client_socket.sendall(str(self._suiveur(1)).encode("utf-8"))
                if "SeuilAlarmeV2" in str(data):
                    self.client_socket.sendall(str(self._suiveur(2)).encode("utf-8"))
                if "SeuilAlarmeV3" in str(data):
                    self.client_socket.sendall(str(self._suiveur(3)).encode("utf-8"))
                if "SeuilAlarmeV4" in str(data):
                    self.client_socket.sendall(str(self._suiveur(4)).encode("utf-8"))
                if "SeuilAlarmeVSomme" in str(data):
                    self.client_socket.sendall(str(sum(self._suiveur(i) for i in range(1, 5))).encode("utf-8"))
                if "MesureMaxVoie1" in str(data):
                    self.client_socket.sendall(str(self._val_max(1)).encode("utf-8"))
                if "MesureMaxVoie2" in str(data):
                    self.client_socket.sendall(str(self._val_max(2)).encode("utf-8"))
                if "MesureMaxVoie3" in str(data):
                    self.client_socket.sendall(str(self._val_max(3)).encode("utf-8"))
                if "MesureMaxVoie4" in str(data):
                    self.client_socket.sendall(str(self._val_max(4)).encode("utf-8"))
                if "MesureMaxVoieSomme" in str(data):
                    self.client_socket.sendall(str(sum(self._val_max(i) for i in range(1, 5))).encode("utf-8"))
                if "AlerteV1" in str(data):
                    self.client_socket.sendall(str(AlarmeThread.alarme_resultat.get(1, 0)).encode("utf-8"))
                if "AlerteV2" in str(data):
                    self.client_socket.sendall(str(AlarmeThread.alarme_resultat.get(2, 0)).encode("utf-8"))
                if "AlerteV3" in str(data):
                    self.client_socket.sendall(str(AlarmeThread.alarme_resultat.get(3, 0)).encode("utf-8"))
                if "AlerteV4" in str(data):
                    self.client_socket.sendall(str(AlarmeThread.alarme_resultat.get(4, 0)).encode("utf-8"))
                if "AlerteVSomme" in str(data):
                    self.client_socket.sendall(str(sum(AlarmeThread.alarme_resultat.get(i, 0) for i in range(1, 5))).encode("utf-8"))
                if "CON_TEST" in str(data):
                    self.client_socket.sendall("OK".encode("utf-8"))
        except Exception as e:
            print(f"Error handling client {self.client_address}: {e}")
        finally:
            self.client_socket.close()


class eVx_Start(threading.Thread):
    def __init__(self, host="", port=6789):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))

    def run(self):
        self.server_socket.listen(5)
        print(f"Server listening on {self.host}:{self.port}")

        try:
            while True:
                client_socket, client_address = self.server_socket.accept()
                client_socket.settimeout(None)
                print(f"Accepted connection from {client_address}")
                client_handler = eVx_Thread(client_socket, client_address)
                client_handler.start()
        except KeyboardInterrupt:
            print("Server is shutting down.")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            print("Close")
            self.server_socket.close()
