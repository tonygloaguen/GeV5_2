import os
import ssl
import threading
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from ...core.alarmes.alarmes import AlarmeThread
from ...core.defauts.defauts import DefautThread
from .rapport_pdf import ReportThread


class EmailSender(threading.Thread):
    def __init__(
        self,
        Nom_portique,
        smtp_server,
        port,
        login=None,
        password=None,
        sender=None,
        recipients=None,
        subject="",
        body="",
        attachment=None,
    ):
        super().__init__(daemon=True)
        self.smtp_server = str(smtp_server)
        self.port = int(port)
        self.login = login
        self.password = password
        self.sender = sender
        self.recipients = recipients if recipients else []
        self.nom_portique = Nom_portique

    def run(self):
        while True:
            for ch in range(1, 13):
                if AlarmeThread.email_send_alarm.get(ch, 0) == 1:
                    self.send_email(
                        f"Message portique Berthold GeV5 - {self.nom_portique}",
                        f"Alarme radiologique sur detecteur {ch}",
                        None,
                    )
                    AlarmeThread.email_send_alarm[ch] = 0

                if DefautThread.email_send_defaut.get(ch, 0) == 1:
                    state = DefautThread.defaut_resultat.get(ch, 0)
                    self.send_email(
                        f"Message portique Berthold GeV5 - {self.nom_portique}",
                        f"Alarme technique sur detecteur {ch} - {state}",
                        None,
                    )
                    DefautThread.email_send_defaut[ch] = 2

            if ReportThread.email_send_rapport.get(1) == 1:
                self.send_email(
                    f"Message portique Berthold GeV5 - {self.nom_portique}",
                    "Rapport de passage",
                    ReportThread.email_send_rapport.get(10),
                )

            time.sleep(0.1)

    def create_server(self, context):
        try:
            if self.port == 465:
                return smtplib.SMTP_SSL(self.smtp_server, self.port, context=context)
            server = smtplib.SMTP(self.smtp_server, self.port)
            server.ehlo()
            if self.port in [587, 2525]:
                server.starttls(context=context)
            return server
        except Exception as e:
            print(e)
            return None

    def send_email(self, subject, body, attachment):
        context = ssl.create_default_context()
        try:
            server = self.create_server(context)
            if server is not None:
                if self.login and self.password and self.port != 25:
                    server.login(self.login, self.password)
                self._send(server, subject, body, attachment)
            else:
                print("Failed to create server connection.")
        except ssl.SSLCertVerificationError:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            server = self.create_server(context)
            if server is not None:
                if self.login and self.password and self.port != 25:
                    server.login(self.login, self.password)
                self._send(server, subject, body, attachment)
            else:
                print("Failed to create server connection after SSL certificate verification error.")
        except Exception as e:
            print(e)
        ReportThread.email_send_rapport[1] = 0
        print("Email envoye : ", body)

    def _send(self, server, subject, body, attachment):
        msg = MIMEMultipart()
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if attachment:
            filename = os.path.basename(attachment)
            with open(attachment, "rb") as attach_file:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attach_file.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                msg.attach(part)
        server.sendmail(msg["From"], self.recipients, msg.as_string())
        server.quit()
