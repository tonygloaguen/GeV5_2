import time
import threading

import websocket

from ..core.alarmes.alarmes import AlarmeThread
from ..core.defauts.defauts import DefautThread
from . import etat_cellule_1, etat_cellule_2
from . import Check_open_cell


class Relais(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)

        self.liste_alarm = []
        self.liste_defaut = []
        self.list_cell = []
        self.flag_al_1 = 0
        self.flag_al_2 = 0
        self.flag_def_1 = 0
        self.flag_cell = 0

        self.ws = websocket.WebSocket()  # Ouverture du socket vers les relais Unipi
        self.ws.connect("ws://127.0.0.1:8080/ws")

        self.ws.send('{"cmd":"set","dev":"relay","circuit":"3","value":"0"}')  # al1
        self.ws.send('{"cmd":"set","dev":"relay","circuit":"4","value":"0"}')  # al2
        self.ws.send('{"cmd":"set","dev":"relay","circuit":"6","value":"0"}')  # al
        self.ws.send('{"cmd":"set","dev":"relay","circuit":"1","value":"1"}')  # def
        self.ws.send('{"cmd":"set","dev":"relay","circuit":"5","value":"1"}')  # def
        self.ws.send('{"cmd":"set","dev":"relay","circuit":"2","value":"0"}')  # cell

    def run(self) -> None:
        while True:
            self.liste_alarm = [
                int(AlarmeThread.alarme_resultat.get(i, 0)) for i in range(1, 13)
            ]
            self.liste_defaut = [
                int(DefautThread.defaut_resultat.get(i, 0)) for i in range(1, 13)
            ] + [int(Check_open_cell.etat_cellule_check.defaut_cell.get(1, 0))]
            self.list_cell = [
                int(etat_cellule_1.InputWatcher.cellules.get(1, 0)),
                int(etat_cellule_2.InputWatcher.cellules.get(2, 0)),
            ]

            if 1 in self.liste_alarm and self.flag_al_1 == 0:  # Test des alarmes
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"3","value":"1"}')
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"6","value":"1"}')
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"5","value":"1"}')
                self.flag_al_1 = 1
            else:
                if all(val == 0 for val in self.liste_alarm) and (self.flag_al_1 == 1 or self.flag_al_2 == 1):
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"3","value":"0"}')
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"6","value":"0"}')
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"5","value":"0"}')
                    self.flag_al_1 = 0

            if 2 in self.liste_alarm and self.flag_al_2 == 0:  # Test des alarmes
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"4","value":"1"}')
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"7","value":"1"}')
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"3","value":"1"}')
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"6","value":"1"}')
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"5","value":"1"}')

                self.flag_al_1 = 1
                self.flag_al_2 = 1
            else:
                if all(val == 0 for val in self.liste_alarm) and (self.flag_al_1 == 1 or self.flag_al_2 == 1):
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"3","value":"0"}')
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"4","value":"0"}')
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"6","value":"0"}')
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"7","value":"0"}')
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"5","value":"0"}')
                    self.flag_al_2 = 0

            if (1 in self.liste_defaut or 2 in self.liste_defaut) and self.flag_def_1 == 0:
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"1","value":"0"}')
                self.flag_def_1 = 1
            else:
                if all(val == 0 for val in self.liste_defaut) and self.flag_def_1 == 1:
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"1","value":"1"}')
                    self.flag_def_1 = 0

            if 1 in self.list_cell:  # Test des cellules
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"2","value":"1"}')
                self.ws.send('{"cmd":"set","dev":"relay","circuit":"8","value":"1"}')
                self.flag_cell = 1
            else:
                if all(val == 0 for val in self.list_cell) and self.flag_cell == 1:
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"2","value":"0"}')
                    self.ws.send('{"cmd":"set","dev":"relay","circuit":"8","value":"0"}')
                    self.flag_cell = 0

            time.sleep(1)
