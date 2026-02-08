import csv
import io
import os, subprocess, sys, schedule
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import sqlite3
import threading
import Check_open_cell
from datetime import datetime
import time
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse, urljoin
from waitress import serve

import comptage_1, comptage_2, comptage_3, comptage_4, comptage_5, comptage_6, comptage_7, comptage_8, comptage_9, comptage_10, comptage_11, comptage_12
import alarme_1, alarme_2, alarme_3, alarme_4, alarme_5, alarme_6, alarme_7, alarme_8, alarme_9, alarme_10, alarme_11, alarme_12
import defaut_1, defaut_2, defaut_3, defaut_4, defaut_5, defaut_6, defaut_7, defaut_8, defaut_9, defaut_10, defaut_11, defaut_12
import etat_cellule_1, etat_cellule_2
from vitesse_chargement import ListWatcher

from network_config import NetworkConfig

import re

NUMERIC_PATTERN = re.compile(r'^\s*-?\d+(?:[.,]\d+)?\s*$')

def normalize_numeric_str(v: str) -> str:
    """Retourne une chaîne numérique normalisée (point décimal), sinon v inchangé."""
    if isinstance(v, str) and NUMERIC_PATTERN.match(v):
        v = v.strip().replace(',', '.')
    return v

class Interface(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.initialize_lists()
        self.stop_thread = False
        self.lock = threading.Lock()

        # --- Notifications / bannières ---
        self.cell_open_notification = False         # reste True tant que défaut actif
        self.low_disk_space_notification = ""       # toast éphémère
        self.ENABLE_INTERNAL_CELL_TIMER = False  # utilise l'état central Check_open_cell

        # --- Temporisation cellules ouvertes (auto) ---
        self.CELL_OPEN_THRESHOLD_SEC = 15 * 60      # 15 min (ajuste si besoin)
        self.cell_open_started_at = None            # timestamp de début d'occupation
        self.cell_open_elapsed = 0                  # durée courante en secondes

    def initialize_lists(self):
        self.liste_comptage = {1: None}
        self.liste_variance = {1: None}
        self.liste_alarm = {1: None}
        self.liste_suiveur = {1: None}
        self.list_recal = {1: None}
        self.liste_val_max = {1: None}
        self.liste_defaut = {1: None}
        self.list_cell = {1: None}
        self.liste_photo = {1: None}
        self.liste_vitesse = {1: None}
        self.list_acq = {1: None}
        self.list_mesure = {1: None}
        self.list_courbe = {1: None}
        self.list_val_deb_mes = {1: None}
        self.liste_point_chaud = {1: None}
        self.mesure = {1: None}

    def restart_program(self):
        os.execl(sys.executable, sys.executable, *sys.argv)

    def job(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"Watchdog check à {current_time}")
        self.restart_program()

    def run(self):
        #schedule.every(6).hours.do(self.job)
        while not self.stop_thread:
            # 1) rafraîchir les listes
            self.update_lists()

            # 2) détecter "cellules ouvertes trop longtemps"
            try:
                with self.lock:
                    lc = self.list_cell[1]
                    c1 = int(lc[0]) if lc is not None else 0
                    c2 = int(lc[1]) if lc is not None else 0
                occupied = (c1 != 0 or c2 != 0)
                if occupied:
                    now = time.time()
                    if self.cell_open_started_at is None:
                        self.cell_open_started_at = now
                        self.cell_open_elapsed = 0
                    else:
                        self.cell_open_elapsed = int(now - self.cell_open_started_at)
                        if (not self.cell_open_notification and
                            self.cell_open_elapsed >= self.CELL_OPEN_THRESHOLD_SEC):
                            self.cell_open_notification = True
                else:
                    self.cell_open_started_at = None
                    self.cell_open_elapsed = 0
                    self.cell_open_notification = False
            except Exception:
                # ne pas casser la boucle si une valeur manque
                pass

            # 3) watchdog/scheduler
            schedule.run_pending()
            time.sleep(1)

    def update_lists(self):
        with self.lock:
            self.liste_comptage[1] = [
                comptage_1.Frequence_1_Thread.compteur[1], comptage_2.Frequence_2_Thread.compteur[2],
                comptage_3.Frequence_3_Thread.compteur[3], comptage_4.Frequence_4_Thread.compteur[4],
                comptage_5.Frequence_5_Thread.compteur[5], comptage_6.Frequence_6_Thread.compteur[6],
                comptage_7.Frequence_7_Thread.compteur[7], comptage_8.Frequence_8_Thread.compteur[8],
                comptage_9.Frequence_9_Thread.compteur[9], comptage_10.Frequence_10_Thread.compteur[10],
                comptage_11.Frequence_11_Thread.compteur[11], comptage_12.Frequence_12_Thread.compteur[12]
            ]
            self.liste_suiveur[1] = [
                alarme_1.Alarme1.suiv[1], alarme_2.Alarme2.suiv[2],
                alarme_3.Alarme3.suiv[3], alarme_4.Alarme4.suiv[4],
                alarme_5.Alarme5.suiv[5], alarme_6.Alarme6.suiv[6],
                alarme_7.Alarme7.suiv[7], alarme_8.Alarme8.suiv[8],
                alarme_9.Alarme9.suiv[9], alarme_10.Alarme10.suiv[10],
                alarme_11.Alarme11.suiv[11], alarme_12.Alarme12.suiv[12]
            ]
            self.liste_val_max[1] = [
                alarme_1.Alarme1.val_max[1], alarme_2.Alarme2.val_max[2],
                alarme_3.Alarme3.val_max[3], alarme_4.Alarme4.val_max[4],
                alarme_5.Alarme5.val_max[5], alarme_6.Alarme6.val_max[6],
                alarme_7.Alarme7.val_max[7], alarme_8.Alarme8.val_max[8],
                alarme_9.Alarme9.val_max[9], alarme_10.Alarme10.val_max[10],
                alarme_11.Alarme11.val_max[11], alarme_12.Alarme12.val_max[12]
            ]
            self.liste_alarm[1] = [
                alarme_1.Alarme1.alarme_resultat[1], alarme_2.Alarme2.alarme_resultat[2],
                alarme_3.Alarme3.alarme_resultat[3], alarme_4.Alarme4.alarme_resultat[4],
                alarme_5.Alarme5.alarme_resultat[5], alarme_6.Alarme6.alarme_resultat[6],
                alarme_7.Alarme7.alarme_resultat[7], alarme_8.Alarme8.alarme_resultat[8],
                alarme_9.Alarme9.alarme_resultat[9], alarme_10.Alarme10.alarme_resultat[10],
                alarme_11.Alarme11.alarme_resultat[11], alarme_12.Alarme12.alarme_resultat[12]
            ]
            self.liste_defaut[1] = [
                defaut_1.Defaut_1.eta_defaut[1], defaut_2.Defaut_2.eta_defaut[2],
                defaut_3.Defaut_3.eta_defaut[3], defaut_4.Defaut_4.eta_defaut[4],
                defaut_5.Defaut_5.eta_defaut[5], defaut_6.Defaut_6.eta_defaut[6],
                defaut_7.Defaut_7.eta_defaut[7], defaut_8.Defaut_8.eta_defaut[8],
                defaut_9.Defaut_9.eta_defaut[9], defaut_10.Defaut_10.eta_defaut[10],
                defaut_11.Defaut_11.eta_defaut[11], defaut_12.Defaut_12.eta_defaut[12]
            ]
            self.list_cell[1] = [
                etat_cellule_1.InputWatcher.cellules[1], etat_cellule_2.InputWatcher.cellules[2]
            ]
            self.liste_point_chaud[1] = [
                alarme_1.Alarme1.etat_point_chaud[1], alarme_2.Alarme2.etat_point_chaud[2],
                alarme_3.Alarme3.etat_point_chaud[3], alarme_4.Alarme4.etat_point_chaud[4],
                alarme_5.Alarme5.etat_point_chaud[5], alarme_6.Alarme6.etat_point_chaud[6],
                alarme_7.Alarme7.etat_point_chaud[7], alarme_8.Alarme8.etat_point_chaud[8],
                alarme_9.Alarme9.etat_point_chaud[9], alarme_10.Alarme10.etat_point_chaud[10],
                alarme_11.Alarme11.etat_point_chaud[11], alarme_12.Alarme12.etat_point_chaud[12]
            ]
            self.mesure[1] = [
                alarme_1.Alarme1.mesure[1], alarme_2.Alarme2.mesure[2],
                alarme_3.Alarme3.mesure[3], alarme_4.Alarme4.mesure[4],
                alarme_5.Alarme5.mesure[5], alarme_6.Alarme6.mesure[6],
                alarme_7.Alarme7.mesure[7], alarme_8.Alarme8.mesure[8],
                alarme_9.Alarme9.mesure[9], alarme_10.Alarme10.mesure[10],
                alarme_11.Alarme11.mesure[11], alarme_12.Alarme12.mesure[12]
            ]

    def stop(self):
        self.stop_thread = True
        self.join()

def create_flask_app(D1_nom, D2_nom, D3_nom, D4_nom, D5_nom, D6_nom, D7_nom, D8_nom, D9_nom, D10_nom, D11_nom, D12_nom, Nom_portique, Mode_sans_cellules, echeance):
    global start_time
    interface = Interface()
    interface.start()
    
    net_config = NetworkConfig()
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    params_db_path = '/home/pi/Partage/Base_donnees/Parametres.db'
    credentials_db_path = '/home/pi/GeV5/static/credentials.db'
    db_path = '/home/pi/Partage/Base_donnees/Db_GeV5.db'
    export_path = '/home/pi/Partage/Export'

    def get_parametres():
        conn = sqlite3.connect(params_db_path)
        c = conn.cursor()
        c.execute('SELECT nom, valeur FROM Parametres')
        rows = c.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}

    def update_parametres(parametres):
        conn = sqlite3.connect(params_db_path)
        c = conn.cursor()
        # Normalisation + validation simple
        invalid = {}
        to_update = {}
        for nom, valeur in parametres.items():
            normalized = normalize_numeric_str(valeur)
            # si c'était visiblement numérique et que la normalisation donne une valeur non float, marque invalide
            if isinstance(valeur, str) and NUMERIC_PATTERN.match(valeur):
                try:
                    float(normalized)  # validation
                except Exception:
                    invalid[nom] = valeur
                    continue
            to_update[nom] = normalized

        # Si erreurs, on n’écrit rien et on renvoie l’info
        if invalid:
            conn.close()
            # utilise le logger + flash pour retour UI
            app.logger.warning("Paramètres invalides: %s", invalid)
            # stocke temporairement les erreurs en session pour l’affichage dans le template si besoin
            session['params_invalid'] = invalid
            raise ValueError(f"Paramètres invalides: {invalid}")

        for nom, valeur in to_update.items():
            c.execute('UPDATE Parametres SET valeur = ? WHERE nom = ?', (valeur, nom))
        conn.commit()
        conn.close()
        app.logger.debug("Paramètres mis à jour avec succès: %s", to_update)


    def add_user(username, password, access_level):
        conn = sqlite3.connect(credentials_db_path)
        c = conn.cursor()
        hashed_password = generate_password_hash(password)
        c.execute('INSERT INTO Users (username, password, access_level) VALUES (?, ?, ?)', (username, hashed_password, access_level))
        conn.commit()
        conn.close()

    def delete_user(user_id):
        conn = sqlite3.connect(credentials_db_path)
        c = conn.cursor()
        c.execute('DELETE FROM Users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

    def verify_user(username, password):
        conn = sqlite3.connect(credentials_db_path)
        c = conn.cursor()
        c.execute('SELECT password, access_level FROM Users WHERE username = ?', (username,))
        row = c.fetchone()
        conn.close()
        if row and check_password_hash(row[0], password):
            session['access_level'] = row[1]
            return True
        return False

    def get_users():
        conn = sqlite3.connect(credentials_db_path)
        c = conn.cursor()
        c.execute('SELECT id, username, access_level FROM Users')
        rows = c.fetchall()
        conn.close()
        return rows

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                flash('Veuillez vous connecter pour accéder à cette page.')
                return redirect(url_for('login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function

    def access_level_required(level):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'logged_in' not in session:
                    flash('Veuillez vous connecter pour accéder à cette page.')
                    return redirect(url_for('login', next=request.url))
                elif session.get('access_level', 1) < level:
                    flash('Vous n\'avez pas l\'autorisation d\'accéder à cette page.')
                    return redirect(url_for('login'))
                return f(*args, **kwargs)
            return decorated_function
        return decorator

    def is_safe_url(target):
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))
        return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        next_page = request.args.get('next')
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            if verify_user(username, password):
                session['logged_in'] = True
                session['username'] = username
                flash('Connexion réussie!')
                if next_page and is_safe_url(next_page):
                    return redirect(next_page)
                else:
                    return redirect(url_for('login'))
            else:
                flash('Nom d’utilisateur ou mot de passe incorrect.')
        return render_template('login.html', next=next_page)

    @app.route('/logout')
    def logout():
        session.pop('logged_in', None)
        session.pop('username', None)
        session.pop('access_level', None)
        flash('Déconnexion réussie!')
        return redirect(url_for('login'))

    @app.route('/users', methods=['GET', 'POST'])
    @login_required
    @access_level_required(2)
    def manage_users():
        if request.method == 'POST':
            if 'add_user' in request.form:
                username = request.form['username']
                password = request.form['password']
                access_level = int(request.form['access_level'])
                add_user(username, password, access_level)
            elif 'delete_user' in request.form:
                user_id = request.form['user_id']
                delete_user(user_id)
            return redirect(url_for('manage_users'))
        users = get_users()
        return render_template('manage_users.html', users=users)

    @app.route('/view_data')
    def view_data():
        rows = []
        col_names = []
        error_message = None
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Db_GeV5'")
            table_exists = c.fetchone()
            if not table_exists:
                error_message = "Aucune table de données n'est créée pour l'instant."
            else:
                c.execute('SELECT * FROM Db_GeV5')
                rows = c.fetchall()
                col_names = [description[0] for description in c.description] if c.description else []
            conn.close()
        except sqlite3.Error as e:
            error_message = str(e)
        return render_template('view_data.html', rows=rows, col_names=col_names, error_message=error_message)

    @app.route('/export_csv', methods=['POST'])
    def export_csv():
        try:
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            filter_alarms = request.form.get('filter_alarms') == 'on'
            start_date_str = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y%m%d_000000')
            end_date_str = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y%m%d_235959')

            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            query = '''
                SELECT * FROM Db_GeV5
                WHERE Horodatage BETWEEN ? AND ?
            '''
            c.execute(query, (start_date_str, end_date_str))
            rows = c.fetchall()
            col_names = [description[0] for description in c.description]

            filtered_rows = []
            if filter_alarms:
                for row in rows:
                    if any(row[i] != 0 for i in range(38, 50)):
                        filtered_rows.append(row)
            else:
                filtered_rows = rows

            conn.close()

            csv_filename = os.path.join(export_path, 'export.csv')
            with open(csv_filename, 'w', newline='') as csvfile:
                cw = csv.writer(csvfile)
                cw.writerow(col_names)
                cw.writerows(filtered_rows)

            return send_file(csv_filename, as_attachment=True)

        except Exception as e:
            print(f"Erreur lors de l'exportation CSV: {str(e)}")
            return jsonify({"error": "Erreur lors de l'exportation CSV."}), 500

    @app.route('/start_anydesk')
    def start_anydesk():
        try:
            subprocess.run(["python3", "/home/pi/GeV5/any_dsk_srv.py"], check=True)
            with app.test_request_context():
                return redirect(url_for('get_channels_data'))
        except subprocess.CalledProcessError as e:
            return f"Failed to start AnyDesk: {e}"

    @app.route('/network')
    @access_level_required(2)
    @login_required
    def network():
        interfaces = net_config.get_interfaces()
        message = request.args.get('message')
        return render_template('network.html', interfaces=interfaces, message=message)

    @app.route('/set_static_ip', methods=['POST'])
    @login_required
    @access_level_required(2)
    def set_static_ip():
        interface_name = request.form['interface']
        ip_address = request.form['ip_address']
        netmask = request.form['netmask']
        gateway = request.form['gateway']
        message = net_config.set_static_ip(interface_name, ip_address, netmask, gateway)
        return redirect(url_for('network', message=message))

    @app.route('/set_dhcp', methods=['POST'])
    @login_required
    @access_level_required(2)
    def set_dhcp():
        interface_name = request.form['interface']
        message = net_config.set_dhcp(interface_name)
        return redirect(url_for('network', message=message))

    @app.route('/set_dns', methods=['POST'])
    @login_required
    @access_level_required(2)
    def set_dns():
        dns_servers = request.form.getlist('dns_servers')
        message = net_config.set_dns(dns_servers)
        return redirect(url_for('network', message=message))

    @app.route('/params/maj_ntp', methods=['GET', 'POST'])
    @login_required
    @access_level_required(2)
    def maj_ntp():
        if request.method == 'POST':
            ntp_server = request.form['ntp_server']
            # update_ntp_server(ntp_server)  # si utilisé
            return redirect(url_for('maj_ntp'))
        return render_template('maj_ntp.html')

    @app.route('/params/general', methods=['GET', 'POST'])
    @login_required
    @access_level_required(1)
    def general_params():
        if request.method == 'POST':
            params = request.form.to_dict()
            try:
                update_parametres(params)
                flash('Paramètres enregistrés.')
            except ValueError as e:
                flash("Certains paramètres sont invalides (utilise 1.5, pas 1,5). Aucun changement sauvegardé.")
            return redirect(url_for('general_params'))
        params = get_parametres()
        invalid = session.pop('params_invalid', None) if 'params_invalid' in session else None
        return render_template('general_params.html', params=params, invalid=invalid)


    @app.route('/params/voies', methods=['GET', 'POST'])
    @login_required
    @access_level_required(1)
    def voies_params():
        if request.method == 'POST':
            params = request.form.to_dict()
            update_parametres(params)
            return redirect(url_for('voies_params'))
        params = get_parametres()
        return render_template('voies_params.html', params=params)

    @app.route('/params/communication_params', methods=['GET', 'POST'])
    @login_required
    @access_level_required(1)
    def communication_params():
        if request.method == 'POST':
            params = request.form.to_dict()
            update_parametres(params)
            return redirect(url_for('communication_params'))       
        params = get_parametres()
        return render_template('communication_params.html', params=params)

    @app.route('/params/camera', methods=['GET', 'POST'])
    @login_required
    @access_level_required(1)
    def camera_params():
        if request.method == 'POST':
            params = request.form.to_dict()
            update_parametres(params)
            return redirect(url_for('camera_params'))
        params = get_parametres()
        return render_template('camera_params.html', params=params)

    @app.route('/params/email', methods=['GET', 'POST'])
    @login_required
    @access_level_required(1)
    def email_params():
        if request.method == 'POST':
            params = request.form.to_dict()
            update_parametres(params)
            return redirect(url_for('email_params'))
        params = get_parametres()
        return render_template('email_params.html', params=params)

    @app.route('/params/sms', methods=['GET', 'POST'])
    @login_required
    @access_level_required(1)
    def sms_params():
        if request.method == 'POST':
            params = request.form.to_dict()
            update_parametres(params)
            return redirect(url_for('sms_params'))
        params = get_parametres()
        return render_template('sms_params.html', params=params)

    @app.route('/params/remote', methods=['GET', 'POST'])
    @login_required
    @access_level_required(1)
    def remote_params():
        if request.method == 'POST':
            params = request.form.to_dict()
            update_parametres(params)
            return redirect(url_for('remote_params'))
        params = get_parametres()
        return render_template('remote_params.html', params=params)

    @app.route('/params/voies_gpio', methods=['GET', 'POST'])
    @login_required
    @access_level_required(2)
    def voies_gpio_params():
        if request.method == 'POST':
            params = request.form.to_dict()
            app.logger.debug("Paramètres GPIO reçus: %s", params)
            update_parametres(params)
            return redirect(url_for('voies_gpio_params'))
        params = get_parametres()
        return render_template('voies_gpio.html', params=params)

    @app.route('/params/mode_simulation', methods=['GET', 'POST'])
    @login_required
    @access_level_required(2)
    def mode_simulation():
        if request.method == 'POST':
            params = request.form.to_dict()
            update_parametres(params)
            return redirect(url_for('mode_simulation'))
        params = get_parametres()
        return render_template('mode_simulation.html', params=params)

    @app.route('/restart_gev5_moteur')
    @login_required
    @access_level_required(2)
    def restart_gev5_moteur():
        os.execl(sys.executable, sys.executable, *sys.argv)

    # -------- Helpers communs pour template/data ----------
    def _snapshot_channels_and_cells():
        with interface.lock:
            names = [D1_nom, D2_nom, D3_nom, D4_nom, D5_nom, D6_nom, D7_nom, D8_nom, D9_nom, D10_nom, D11_nom, D12_nom]
            channels = []
            for i in range(12):
                comptage = interface.liste_comptage[1][i]
                if comptage != -1:
                    channels.append({
                        "channel": names[i],
                        "comptage": comptage,
                        "suiveur": interface.liste_suiveur[1][i],
                        "val_max": interface.liste_val_max[1][i],
                        "alarm": interface.liste_alarm[1][i],
                        "defaut": interface.liste_defaut[1][i],
                        "etat_point_chaud": interface.liste_point_chaud[1][i]
                    })
            cells = {
                "cellule_1": interface.list_cell[1][0],
                "cellule_2": interface.list_cell[1][1],
                "etat_mesure": interface.mesure[1],
                "vitesse_1": ListWatcher.vitesse[1] if Mode_sans_cellules == 0 else None,
                "vitesse_10": ListWatcher.vitesse[10] if Mode_sans_cellules == 0 else None
            }
        return channels, cells
    # -----------------------------------------------------

    @app.route('/template')
    def template_route():
        channels, cells = _snapshot_channels_and_cells()
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open('/home/pi/GeV5/static/version.txt', 'r') as file:
                version = file.read().strip()
        except Exception:
            version = "n/a"
        return render_template('template.html', channels=channels, cells=cells,
                               current_datetime=current_datetime, nom_portique=Nom_portique,
                               mode_sans_cellules=Mode_sans_cellules, echeance=echeance, version=version)

    @app.route('/control_camera')
    def control_camera():
        parametres = get_parametres()
        camera_ip = parametres.get('IP', '127.0.0.1')
        return redirect(f'http://{camera_ip}', code=302)

    def set_alarms(value):
        alarme_1.Alarme1.etat_acq_modbus[1] = value
        alarme_2.Alarme2.etat_acq_modbus[2] = value
        alarme_3.Alarme3.etat_acq_modbus[3] = value
        alarme_4.Alarme4.etat_acq_modbus[4] = value
        alarme_5.Alarme5.etat_acq_modbus[5] = value
        alarme_6.Alarme6.etat_acq_modbus[6] = value
        alarme_7.Alarme7.etat_acq_modbus[7] = value
        alarme_8.Alarme8.etat_acq_modbus[8] = value
        alarme_9.Alarme9.etat_acq_modbus[9] = value
        alarme_10.Alarme10.etat_acq_modbus[10] = value
        alarme_11.Alarme11.etat_acq_modbus[11] = value
        alarme_12.Alarme12.etat_acq_modbus[12] = value

    @app.route('/acquittement')
    @login_required
    @access_level_required(1)
    def acquittement():
        set_alarms(1)
        time.sleep(1)
        set_alarms(0)
        with app.test_request_context():
            return redirect(url_for('get_channels_data'))

    def get_data_from_db():
        try:
            with sqlite3.connect('/home/pi/Partage/Base_donnees/Bruit_de_fond.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT timestamp, compteur_1, compteur_2, compteur_3, compteur_4, compteur_5, 
                           compteur_6, compteur_7, compteur_8, compteur_9, compteur_10, 
                           compteur_11, compteur_12 
                    FROM compteurs 
                    WHERE timestamp >= ? 
                    ORDER BY timestamp DESC
                ''', (start_time,))
                rows = cursor.fetchall()

            timestamps = [datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').isoformat() for row in rows]
            data = {f'compteur_{i}': [row[i] for row in rows] for i in range(1, 13)}
            data.update({'timestamps': timestamps[::-1]})
            for i in range(1, 13):
                data[f'compteur_{i}'] = data[f'compteur_{i}'][::-1]
            return data
        except Exception as e:
            print(e)

    @app.route('/data', methods=['GET'])
    def get_data():
        with interface.lock:
            data = {
                "comptage": interface.liste_comptage[1],
                "suiveur": interface.liste_suiveur[1],
                "val_max": interface.liste_val_max[1],
                "alarm": interface.liste_alarm[1],
                "defaut": interface.liste_defaut[1],
                "etat_point_chaud": interface.liste_point_chaud[1],
                "mesure": interface.mesure[1],
                "cells": {
                    "cellule_1": interface.list_cell[1][0],
                    "cellule_2": interface.list_cell[1][1]
                },
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "names": [D1_nom, D2_nom, D3_nom, D4_nom, D5_nom, D6_nom, D7_nom, D8_nom, D9_nom, D10_nom, D11_nom, D12_nom],
                "nom_portique": Nom_portique,
                "mode_sans_cellules": Mode_sans_cellules,
                "vitesse_1": ListWatcher.vitesse[1] if Mode_sans_cellules == 0 else None,
                "vitesse_10": ListWatcher.vitesse[10] if Mode_sans_cellules == 0 else None,
                "echeance": echeance
            }
        db_data = get_data_from_db()
        if db_data:
            data.update(db_data)
        return jsonify(data)

    @app.route('/data/channels', methods=['GET'])
    def get_channels_data():
        channels, cells = _snapshot_channels_and_cells()
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open('/home/pi/GeV5/static/version.txt', 'r') as file:
                version = file.read().strip()
        except Exception:
            version = "n/a"
        return render_template('template.html', channels=channels, cells=cells,
                               current_datetime=current_datetime, nom_portique=Nom_portique,
                               mode_sans_cellules=Mode_sans_cellules, echeance=echeance, version=version)

    @app.route('/notify_open_cell', methods=['POST'])
    def notify_open_cell():
        with interface.lock, Check_open_cell.state.lock:
            Check_open_cell.state.active = True
            if Check_open_cell.state.started_at is None:
                Check_open_cell.state.started_at = time.time()
        return jsonify({"status": "notification received"})

    @app.route('/clear_open_cell', methods=['POST'])
    def clear_open_cell():
        with interface.lock, Check_open_cell.state.lock:
            Check_open_cell.state.active = False
            Check_open_cell.state.started_at = None
            Check_open_cell.state.elapsed = 0
        return jsonify({"status": "cleared"})

    @app.route('/notify_low_disk_space', methods=['POST'])
    def notify_low_disk_space():
        data = request.json
        with interface.lock:
            interface.low_disk_space_notification = data.get("message", "")
        return jsonify({"status": "notification received"})

    @app.route('/get_notifications', methods=['GET'])
    def get_notifications():
        with interface.lock, Check_open_cell.state.lock:
            elapsed = 0
            if Check_open_cell.state.active and Check_open_cell.state.started_at:
                elapsed = int(time.time() - Check_open_cell.state.started_at)
            notifications = {
                "cell_open_notification": Check_open_cell.state.active,
                "low_disk_space_notification": interface.low_disk_space_notification,
                "cell_open_elapsed": elapsed
            }
            interface.low_disk_space_notification = ""
        return jsonify(notifications)

    def run_email_tester():
        try:
            subprocess.run(["python3", "/home/pi/GeV5/email_tester.py"], check=True)
            return "Script exécuté avec succès"
        except subprocess.CalledProcessError as e:
            return f"Échec de l'exécution du script: {e}"

    @app.route('/test_smtp')
    def test_smtp():
        result = run_email_tester()
        with app.test_request_context():
            return redirect(url_for('get_channels_data'))
    
    @app.route('/test_io')
    def test_io():
        try:
            subprocess.run(["sudo", "pkill", "chromium"], check=True)
            subprocess.run(["python3", "/home/pi/GeV5/auto_tester.py"], check=True)
        except subprocess.CalledProcessError as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return app

def run_flask_app(D1_nom, D2_nom, D3_nom, D4_nom, D5_nom, D6_nom, D7_nom, D8_nom, D9_nom, D10_nom, D11_nom, D12_nom, Nom_portique, Mode_sans_cellules, echeance):
    global start_time
    start_time = datetime.now()
    app = create_flask_app(D1_nom, D2_nom, D3_nom, D4_nom, D5_nom, D6_nom, D7_nom, D8_nom, D9_nom, D10_nom, D11_nom, D12_nom, Nom_portique, Mode_sans_cellules, echeance)
    try:
        import logging
        logging.getLogger("waitress.queue").setLevel(logging.ERROR)
        serve(app, host='0.0.0.0', port=5002, threads=4)
    except OSError as e:
        if e.errno == 98:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Erreur serveur fatale, reboot en cours...")
            os.system("sudo reboot")
        else:
            raise

if __name__ == '__main__':
    run_flask_app(D1_nom, D2_nom, D3_nom, D4_nom, D5_nom, D6_nom, D7_nom, D8_nom, D9_nom, D10_nom, D11_nom, D12_nom, Nom_portique, Mode_sans_cellules, echeance)
