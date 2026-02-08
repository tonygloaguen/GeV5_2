import serial
import time
import glob

def detect_modem_ports(possible_ports=None):
    """
    Liste les ports série disponibles et teste la commande AT pour trouver le modem.
    """
    if possible_ports is None:
        # Cherche tous les ports tty connus
        possible_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyAMA*')
    
    for port in possible_ports:
        print(f"Test du port : {port}")
        try:
            with serial.Serial(port, baudrate=9600, timeout=2) as modem:
                modem.write(b'AT\r')
                time.sleep(1)
                response = modem.read(modem.in_waiting or 64).decode(errors='ignore')
                print(f"Réponse: {response.strip()}")
                if "OK" in response:
                    print(f"✅ Modem trouvé sur {port}")
                    return port
        except serial.SerialException:
            print(f"⚠️ Impossible d'ouvrir {port}")
    print("❌ Aucun modem détecté")
    return None

def send_at_command(modem, command, expected_response, timeout=1):
    """
    Envoie une commande AT et vérifie la réponse.
    """
    modem.write(f'{command}\r'.encode())
    time.sleep(timeout)
    response = modem.read(modem.in_waiting or 64).decode(errors='ignore')
    print(f"Commande: {command}, Réponse: {response.strip()}")
    return expected_response in response

def send_sms(port, phone_number, message):
    """
    Envoie un SMS via le modem détecté.
    """
    try:
        with serial.Serial(port, baudrate=9600, timeout=5) as modem:
            if send_at_command(modem, 'AT', 'OK') and \
               send_at_command(modem, 'AT+CMGF=1', 'OK'):
                if send_at_command(modem, f'AT+CMGS="{phone_number}"', '>'):
                    modem.write(f'{message}\x1A'.encode())
                    time.sleep(5)
                    response = modem.read(modem.in_waiting or 256).decode(errors='ignore')
                    print(f"Réponse finale: {response.strip()}")
                    if 'OK' in response:
                        print(f"✅ SMS envoyé à {phone_number}")
                    else:
                        print(f"❌ Échec de l'envoi: {response.strip()}")
            else:
                print("❌ Échec initialisation modem (AT ou CMGF)")
    except serial.SerialException as e:
        print(f"Erreur Serial: {e}")

if __name__ == "__main__":
    # Liste manuelle possible si tu sais déjà tes ports
    # possible_ports = ["/dev/ttyAMA0", "/dev/ttyUSB0"]
    possible_ports = None  # Laisse None pour tout tester

    port = detect_modem_ports(possible_ports)
    if port:
        send_sms(port, '0612190122', 'Bonjour, ceci est un test Raspberry Pi.')
    else:
        print("Aucun modem disponible pour envoyer le SMS.")
