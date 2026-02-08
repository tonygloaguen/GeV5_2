import datetime
import os
import platform
import shutil
import threading
from time import sleep

from pyModbusTCP.server import ModbusServer

from ..core.alarmes.alarmes import AlarmeThread
from ..core.comptage.comptage import ComptageThread
from ..core.defauts.defauts import DefautThread
from . import etat_cellule_1, etat_cellule_2
from . import Check_open_cell


def _setup_iptables_redirect() -> None:
    if platform.system().lower() != "linux":
        return
    if shutil.which("iptables") is None:
        return
    try:
        if os.geteuid() != 0:
            return
    except Exception:
        return

    os.system("iptables -A PREROUTING -t nat -p tcp --dport 502 -j REDIRECT --to-port 5200")


ETAT_ACQ_MODBUS = {i: 0 for i in range(1, 13)}


class ModbusThread(threading.Thread):
    def __init__(self, echeance: int) -> None:
        super().__init__(daemon=True)
        _setup_iptables_redirect()
        self.server = ModbusServer("0.0.0.0", 5200, no_block=True)
        self.running = True
        self.echeance = echeance
        self.words = 0

    def run(self) -> None:
        try:
            print(f"{datetime.datetime.now()} / Start server...")
            self.server.start()
            print("Server is online")

            while self.running:
                self.process_modbus()
                sleep(0.5)

        except Exception as e:
            print(e)
        finally:
            print("Shutdown server...")
            self.server.stop()
            print("Server is offline")

    def process_modbus(self) -> None:
        RegMean = [float(ComptageThread.compteur.get(i, 0.0)) for i in range(1, 13)]
        RegMax = [0.0 for _ in range(12)]
        RegSuiveur = [float(AlarmeThread.fond.get(i, 0.0)) for i in range(1, 13)]
        RegLD = [0.0 for _ in range(12)]

        RegInfoCell = [
            int(etat_cellule_1.InputWatcher.cellules.get(1, 0)),
            int(etat_cellule_2.InputWatcher.cellules.get(2, 0)),
        ]

        RegAlarmRadio = [int(AlarmeThread.alarme_resultat.get(i, 0)) for i in range(1, 13)]
        RegAlarmTech = [int(DefautThread.defaut_resultat.get(i, 0)) for i in range(1, 13)]
        RegAlarmLD = [0 for _ in range(12)]

        en_mesure = [float(AlarmeThread.alarme_mesure.get(i, 0.0)) for i in range(1, 13)]
        _ = en_mesure

        Update = []
        for i in RegMean:
            Update.append(int(i) if i != -1 else 0)
        for i in RegSuiveur:
            Update.append(int(i))
        for i in RegMax:
            Update.append(int(i))
        for i in RegLD:
            Update.append(int(i))
        for i in RegInfoCell:
            Update.append(int(i))
        for i in RegAlarmRadio:
            Update.append(int(i))
        for i in RegAlarmTech:
            Update.append(int(i))
        for i in RegAlarmLD:
            Update.append(int(i))
        Update.append(int(sum(RegMean)))
        Update.append(int(sum(RegMax)))
        Update.append(int(sum(RegSuiveur)))
        if (sum(RegMax) >= sum(RegSuiveur)) and sum(RegInfoCell) > 0:
            Update.append(1)
        else:
            if sum(RegAlarmRadio) == 0:
                Update.append(0)
            else:
                Update.append(1)
        Update.append(int(self.echeance))
        now = datetime.datetime.now().strftime("%d%m%Y%H%M%S")
        Update.append(int(now[0:2]))
        Update.append(int(now[2:4]))
        Update.append(int(now[4:8]))
        Update.append(int(now[8:10]))
        Update.append(int(now[10:12]))
        Update.append(int(now[12:14]))
        Update.append(int(Check_open_cell.etat_cellule_check.defaut_cell.get(1, 0)))
        self.server.data_bank.set_holding_registers(0, Update)

        try:
            words = self.server.data_bank.get_holding_registers(99)
            self.words = int(words[0]) if words else 0

            if any(ETAT_ACQ_MODBUS[i] != self.words for i in range(1, 13)):
                for i in range(1, 13):
                    ETAT_ACQ_MODBUS[i] = self.words
                self.server.data_bank.set_holding_registers(99, [0])

        except Exception as e:
            print(e)
