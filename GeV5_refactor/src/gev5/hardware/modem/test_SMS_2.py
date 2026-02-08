#!/usr/bin/env python3
# sms_hilink.py – envoie “Test” à 0612190122 via E3372h-320 (Hi-Link)

import requests, xml.etree.ElementTree as ET, sys

MODEM = "http://192.168.8.1"       # IP du stick
PHONE  = "+33676756283"            # même format que dans ton batch
TEXT   = "PD"                    # message (ASCII simple)

def get_cookie_token(sess):
    xml = sess.get(f"{MODEM}/api/webserver/SesTokInfo", timeout=3).text
    r   = ET.fromstring(xml)
    return r.findtext("SesInfo"), r.findtext("TokInfo")

with requests.Session() as s:
    cookie, token = get_cookie_token(s)

    body = (f'<?xml version="1.0" encoding="UTF-8"?><request>'
            f'<Index>-1</Index><Phones><Phone>{PHONE}</Phone></Phones>'
            f'<Sca></Sca><Content>{TEXT}</Content>'
            f'<Length>-1</Length><Reserved>1</Reserved><Date>-1</Date></request>')

    headers = {"Cookie": cookie,
               "__RequestVerificationToken": token}

    resp = s.post(f"{MODEM}/api/sms/send-sms",
                  headers=headers, data=body, timeout=5)

    print(resp.text.strip())
    if "<response>OK</response>" in resp.text:
        print("✅  SMS envoyé")
    else:
        sys.exit("❌  Échec d’envoi")

