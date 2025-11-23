import pyodbc
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

class SchoolDB:
    def __init__(self):
        # 1. Get values from .env
        driver = os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')
        server = os.getenv('DB_SERVER', 'localhost')
        database = os.getenv('DB_DATABASE', 'SchoolManagementDB')
        trusted_conn = os.getenv('DB_TRUSTED_CONNECTION', 'yes')
        trust_cert = os.getenv('DB_TRUST_CERT', 'yes')
        
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')

        # 2. Build Connection String dynamically
        self.conn_str = (
            f"DRIVER={driver};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"TrustServerCertificate={trust_cert};"
        )

        if trusted_conn.lower() == 'yes':
            self.conn_str += "Trusted_Connection=yes;"
        else:
            self.conn_str += f"UID={user};PWD={password};"

        self.conn = None

    def connect(self):
        try:
            self.conn = pyodbc.connect(self.conn_str)
            print("✅ Connected to Database Successfully")
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            print("👉 Check your .env file settings.")

    def close(self):
        if self.conn:
            self.conn.close()

    # ==========================================================
    # 1. ADMIN TASKS
    # ==========================================================
    
    def add_student(self, nom, prenom, email, password, cne, groupe_id, dob):
        cursor = self.conn.cursor()
        try:
            sql_user = "INSERT INTO Utilisateur (Nom, Prenom, Email, MotDePasse, Role) VALUES (?, ?, ?, ?, 'Etudiant');"
            cursor.execute(sql_user, (nom, prenom, email, password))
            cursor.execute("SELECT @@IDENTITY")
            user_id = cursor.fetchone()[0]

            sql_student = "INSERT INTO Etudiant (EtudiantID, CNE, GroupeID, DateNaissance) VALUES (?, ?, ?, ?);"
            cursor.execute(sql_student, (user_id, cne, groupe_id, dob))

            self.conn.commit()
            print(f"✅ Student {nom} {prenom} created with ID {user_id}")
            return user_id
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error adding student: {e}")
            return None

    def create_seance(self, date_debut, date_fin, salle, module_id, formateur_email, groupe_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT UserID FROM Utilisateur WHERE Email = ?", (formateur_email,))
            row = cursor.fetchone()
            if not row:
                print("❌ Formateur email not found.")
                return False
            formateur_id = row[0]

            sql = """
            INSERT INTO Seance (DateDebut, DateFin, Salle, ModuleID, FormateurID, GroupeID)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(sql, (date_debut, date_fin, salle, module_id, formateur_id, groupe_id))
            self.conn.commit()
            print("✅ Seance scheduled successfully.")
            return True
        except Exception as e:
            print(f"❌ Error creating seance: {e}")
            return False

    # ==========================================================
    # 2. SERVER TASKS
    # ==========================================================

    def get_students_for_seance(self, seance_id):
        cursor = self.conn.cursor()
        sql = """
        SELECT U.UserID, U.Nom, U.Prenom, E.CNE 
        FROM Etudiant E
        JOIN Utilisateur U ON E.EtudiantID = U.UserID
        WHERE E.GroupeID = (SELECT GroupeID FROM Seance WHERE SeanceID = ?)
        """
        cursor.execute(sql, (seance_id,))
        results = cursor.fetchall()
        
        students = []
        for row in results:
            students.append({
                "id": row.UserID,
                "name": f"{row.Nom} {row.Prenom}",
                "cne": row.CNE
            })
        return students

    def mark_presence(self, seance_id, etudiant_id, status):
        cursor = self.conn.cursor()
        try:
            sql = "INSERT INTO Presence (SeanceID, EtudiantID, Etat) VALUES (?, ?, ?)"
            cursor.execute(sql, (seance_id, etudiant_id, status))
            self.conn.commit()
            print(f"✅ Presence marked for Student {etudiant_id}")
        except pyodbc.IntegrityError:
            print(f"⚠️ Student {etudiant_id} is already marked for this session.")
        except Exception as e:
            print(f"❌ Error marking presence: {e}")