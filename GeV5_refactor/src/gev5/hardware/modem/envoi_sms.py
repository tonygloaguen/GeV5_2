"""sms_module_hilink.py -- v4 (V2 compat)"""

from __future__ import annotations

import html
import threading
import time
import xml.etree.ElementTree as ET
from typing import Iterable

import requests

from ...core.alarmes.alarmes import AlarmeThread
from ...core.defauts.defauts import DefautThread

import unicodedata
import re

_GSM7 = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1BÆæßÉ "
    " !\"#¤%&'()*+,-./0123456789:;<=>?¡"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`¿"
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)


def to_gsm7(text: str) -> str:
    """Enleve accents et caracteres non GSM-7."""
    txt = unicodedata.normalize("NFD", text)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    return re.sub(fr"[^{re.escape(_GSM7)}]", " ", txt)


class HiLinkError(RuntimeError):
    """Raised when the modem returns an <error> code."""


class HiLinkModem:
    """Minimal helper to send SMS via /api/sms/send-sms."""

    def __init__(self, base_url: str = "http://192.168.8.1") -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def _cookie_token(self) -> tuple[str, str]:
        xml = self._session.get(f"{self.base_url}/api/webserver/SesTokInfo", timeout=3).text
        root = ET.fromstring(xml)
        return root.findtext("SesInfo", ""), root.findtext("TokInfo", "")

    def send_sms(self, phone: str, message: str) -> None:
        if phone.startswith("0") and len(phone) == 10:
            phone = "+33" + phone[1:]
        cookie, token = self._cookie_token()
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<request><Index>-1</Index>'
            f"<Phones><Phone>{phone}</Phone></Phones>"
            "<Sca></Sca>"
            f"<Content>{html.escape(message)}</Content>"
            "<Length>-1</Length><Reserved>1</Reserved><Date>-1</Date></request>"
        )
        r = self._session.post(
            f"{self.base_url}/api/sms/send-sms",
            headers={"Cookie": cookie, "__RequestVerificationToken": token},
            data=body,
            timeout=5,
        )
        if r.status_code != 200 or "<response>OK</response>" not in r.text:
            raise HiLinkError(r.text.strip())


def clean_phone(num: str) -> str:
    num = num.strip().replace(" ", "")
    if num.startswith("00"):
        num = "+" + num[2:]
    if num.startswith("0") and len(num) == 10:
        num = "+33" + num[1:]
    return num


class SMSModule(threading.Thread):
    """Polls flags in AlarmeThread / DefautThread and sends throttled SMS."""

    _THROTTLE = 300  # seconds

    def __init__(
        self,
        Nom_portique: str,
        phone_numbers: Iterable[str],
        modem_url: str = "http://192.168.8.1",
        poll_period: float = 1.0,
    ) -> None:
        super().__init__(daemon=True)
        self.nom_portique = Nom_portique
        self.phone_numbers = [clean_phone(n) for n in phone_numbers if n]
        self.poll_period = poll_period
        self.modem = HiLinkModem(modem_url)
        self._stop = threading.Event()
        self._last_sent: dict[str, float] = {}
        self._flag_active: dict[str, bool] = {}

    def _send(self, key: str, msg: str) -> None:
        now = time.time()
        if now - self._last_sent.get(key, 0) < self._THROTTLE:
            return
        self._last_sent[key] = now
        for num in self.phone_numbers:
            try:
                self.modem.send_sms(num, msg)
                print(f"SMS envoye a {num} ({key})")
                time.sleep(10)
            except Exception as exc:
                print(f"Echec d'envoi SMS a {num}: {exc}")

    def run(self):
        tpl = f"Message portique Berthold GeV5 - {self.nom_portique} - {{msg}}"
        while not self._stop.is_set():
            for idx in range(1, 13):
                flag = AlarmeThread.alarme_resultat.get(idx, 0)
                key = f"A{idx}"
                if flag in (1, 2):
                    self._flag_active[key] = True
                    self._send(key, tpl.format(msg=f"Alarme radiologique sur detecteur {idx}"))
                else:
                    if self._flag_active.pop(key, False):
                        self._last_sent.pop(key, None)

            for idx in range(1, 13):
                flag = DefautThread.defaut_resultat.get(idx, 0)
                key = f"T{idx}"
                if flag in (1, 2):
                    self._flag_active[key] = True
                    self._send(key, tpl.format(msg=f"Alarme technique sur detecteur {idx}"))
                else:
                    if self._flag_active.pop(key, False):
                        self._last_sent.pop(key, None)

            time.sleep(self.poll_period)
