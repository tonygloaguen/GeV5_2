import sqlite3
from datetime import datetime

from ...utils.paths import PARAM_DB_PATH


DEFAULT_PARAMS = [
    ("Nom_portique", "Portique eV5"),
    ("sample_time", "0.5"),
    ("distance_cellules", "0.5"),
    ("Mode_sans_cellules", "0"),
    ("multiple", "1.5"),
    ("seuil2", "10000"),
    ("low", "300"),
    ("high", "20000"),
    ("camera", "0"),
    ("modbus", "0"),
    ("eVx", "0"),
    ("mod_SMS", "0"),
    ("date_prochaine_visite", "01/07/2030"),
    ("D1_ON", "1"),
    ("D2_ON", "1"),
    ("D3_ON", "0"),
    ("D4_ON", "0"),
    ("D5_ON", "0"),
    ("D6_ON", "0"),
    ("D7_ON", "0"),
    ("D8_ON", "0"),
    ("D9_ON", "0"),
    ("D10_ON", "0"),
    ("D11_ON", "0"),
    ("D12_ON", "0"),
    ("D1_nom", "DÃ©tecteur 1"),
    ("D2_nom", "DÃ©tecteur 2"),
    ("D3_nom", "DÃ©tecteur 3"),
    ("D4_nom", "DÃ©tecteur 4"),
    ("D5_nom", "DÃ©tecteur 5"),
    ("D6_nom", "DÃ©tecteur 6"),
    ("D7_nom", "DÃ©tecteur 7"),
    ("D8_nom", "DÃ©tecteur 8"),
    ("D9_nom", "DÃ©tecteur 9"),
    ("D10_nom", "DÃ©tecteur 10"),
    ("D11_nom", "DÃ©tecteur 11"),
    ("D12_nom", "DÃ©tecteur 12"),
    ("Rem_IP", "--"),
    ("Rem_IP_2", "--"),
    ("RTSP", "--"),
    ("IP", "--"),
    ("smtp_server", "--"),
    ("port", "25"),
    ("login", "None"),
    ("password", "None"),
    ("sender", "GeV5@berthold.com"),
    ("recipients", "--"),
    ("SMS", "--,--"),
    ("PIN_1", "26"),
    ("PIN_2", "16"),
    ("PIN_3", "6"),
    ("PIN_4", "18"),
    ("SIM", "0"),
    ("suiv_block", "1"),
    ("language", "fr"),
]


def init_params(db_path: str | None = None) -> None:
    """
    Initialise la base Parametres.db si elle est vide.
    Ne rÃ©-insÃ¨re pas si des paramÃ¨tres existent dÃ©jÃ .
    """
    if db_path is None:
        db_path = str(PARAM_DB_PATH)

    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS Parametres (
                nom TEXT,
                valeur TEXT
            )"""
        )
        c.execute("SELECT COUNT(*) FROM Parametres")
        count = int(c.fetchone()[0])
        if count == 0:
            c.executemany(
                "INSERT INTO Parametres (nom, valeur) VALUES (?, ?)",
                DEFAULT_PARAMS,
            )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    init_params()
    print(f"[reinit_params] Parametres.db initialisÃ© Ã  {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
