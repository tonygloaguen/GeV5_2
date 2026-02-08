import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import tkinter as tk
from tkinter import messagebox

def test_smtp(server, port, from_addr, to_addr, username=None, password=None, use_tls=False, use_ssl=False):
    try:
        # Création du message
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = 'Test SMTP'
        body = 'Ceci est un email de test pour vérifier les paramètres SMTP.'
        msg.attach(MIMEText(body, 'plain'))

        # Connexion au serveur SMTP
        if use_ssl:
            server_conn = smtplib.SMTP_SSL(server, port)
        else:
            server_conn = smtplib.SMTP(server, port)
            if use_tls:
                server_conn.starttls()

        if username and password:
            server_conn.login(username, password)

        # Envoi de l'email
        server_conn.sendmail(from_addr, to_addr, msg.as_string())
        server_conn.quit()
        messagebox.showinfo("Succès", "Email envoyé avec succès")
    except Exception as e:
        messagebox.showerror("Erreur", f"Échec de l'envoi de l'email: {e}")

def send_email():
    smtp_server = entry_server.get()
    smtp_port = int(entry_port.get())
    email_from = entry_from.get()
    email_to = entry_to.get()
    smtp_username = entry_username.get()
    smtp_password = entry_password.get()
    smtp_use_tls = var_tls.get()
    smtp_use_ssl = var_ssl.get()

    test_smtp(smtp_server, smtp_port, email_from, email_to, smtp_username, smtp_password, smtp_use_tls, smtp_use_ssl)

# Création de la fenêtre principale
root = tk.Tk()
root.title("Test SMTP")

# Création des widgets
tk.Label(root, text="Serveur SMTP:").grid(row=0, column=0, padx=5, pady=5)
entry_server = tk.Entry(root)
entry_server.grid(row=0, column=1, padx=5, pady=5)

tk.Label(root, text="Port SMTP:").grid(row=1, column=0, padx=5, pady=5)
entry_port = tk.Entry(root)
entry_port.grid(row=1, column=1, padx=5, pady=5)

tk.Label(root, text="Email de l'expéditeur:").grid(row=2, column=0, padx=5, pady=5)
entry_from = tk.Entry(root)
entry_from.grid(row=2, column=1, padx=5, pady=5)

tk.Label(root, text="Email du destinataire:").grid(row=3, column=0, padx=5, pady=5)
entry_to = tk.Entry(root)
entry_to.grid(row=3, column=1, padx=5, pady=5)

tk.Label(root, text="Nom d'utilisateur:").grid(row=4, column=0, padx=5, pady=5)
entry_username = tk.Entry(root)
entry_username.grid(row=4, column=1, padx=5, pady=5)

tk.Label(root, text="Mot de passe:").grid(row=5, column=0, padx=5, pady=5)
entry_password = tk.Entry(root, show="*")
entry_password.grid(row=5, column=1, padx=5, pady=5)

var_tls = tk.BooleanVar()
tk.Checkbutton(root, text="Utiliser TLS", variable=var_tls).grid(row=6, column=0, padx=5, pady=5)

var_ssl = tk.BooleanVar()
tk.Checkbutton(root, text="Utiliser SSL", variable=var_ssl).grid(row=6, column=1, padx=5, pady=5)

tk.Button(root, text="Envoyer l'email", command=send_email).grid(row=7, columnspan=2, padx=5, pady=10)

# Lancement de la boucle principale
root.mainloop()
