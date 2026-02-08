import sqlite3
from werkzeug.security import generate_password_hash

def init_db():
    db_path = '/home/pi/GeV5/static/credentials.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            access_level INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_user(username, password, access_level=1):
    db_path = '/home/pi/GeV5/static/credentials.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    hashed_password = generate_password_hash(password)
    c.execute('INSERT INTO Users (username, password, access_level) VALUES (?, ?, ?)', (username, hashed_password, access_level))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    # Ajouter un utilisateur initial (ex. admin) pour test
    add_user('admin', 'password', 2)  # Changez les credentials par défaut et le niveau d'accès si nécessaire
    add_user('user', 'password', 1)  # Ajouter un utilisateur standard pour test
