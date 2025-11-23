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
            # Upsert Logic: Update if exists, Insert if not
            sql_update = "UPDATE Presence SET Etat = ?, DateEnregistrement = GETDATE() WHERE SeanceID = ? AND EtudiantID = ?"
            cursor.execute(sql_update, (status, seance_id, etudiant_id))
            
            if cursor.rowcount == 0:
                sql_insert = "INSERT INTO Presence (SeanceID, EtudiantID, Etat) VALUES (?, ?, ?)"
                cursor.execute(sql_insert, (seance_id, etudiant_id, status))
                print(f"✅ Presence ADDED for Student {etudiant_id}")
            else:
                print(f"🔄 Presence UPDATED for Student {etudiant_id}")

            self.conn.commit()
        except Exception as e:
            print(f"❌ Error marking presence: {e}")

    # ==========================================================
    # 3. CLASSROOM TASKS (Formateur)
    # ==========================================================

    def create_annonce(self, titre, contenu, formateur_id, groupe_id):
        cursor = self.conn.cursor()
        try:
            sql = "INSERT INTO Annonce (Titre, Contenu, FormateurID, GroupeID) VALUES (?, ?, ?, ?)"
            cursor.execute(sql, (titre, contenu, formateur_id, groupe_id))
            self.conn.commit()
            print(f"📢 Annonce '{titre}' posted.")
            return True
        except Exception as e:
            print(f"❌ Error posting annonce: {e}")
            return False

    def create_tp(self, titre, description, file_path, deadline, module_id, formateur_id, groupe_id):
        cursor = self.conn.cursor()
        try:
            sql = """
            INSERT INTO TP (Titre, Description, CheminFichier, DateLimite, ModuleID, FormateurID, GroupeID) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(sql, (titre, description, file_path, deadline, module_id, formateur_id, groupe_id))
            self.conn.commit()
            print(f"fyp TP '{titre}' assigned.")
            return True
        except Exception as e:
            print(f"❌ Error creating TP: {e}")
            return False

    # ==========================================================
    # 4. STUDENT TASKS (Student)
    # ==========================================================

    def get_tps_for_student(self, groupe_id):
        cursor = self.conn.cursor()
        sql = """
        SELECT TP.TPID, TP.Titre, TP.Description, TP.DateLimite, M.NomModule 
        FROM TP
        JOIN Module M ON TP.ModuleID = M.ModuleID
        WHERE TP.GroupeID = ?
        ORDER BY TP.DateLimite DESC
        """
        cursor.execute(sql, (groupe_id,))
        results = cursor.fetchall()
        
        tps = []
        for row in results:
            tps.append({
                "id": row.TPID,
                "titre": row.Titre,
                "description": row.Description,
                "deadline": str(row.DateLimite),
                "module": row.NomModule
            })
        return tps

    def get_tp_file_path(self, tp_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT CheminFichier FROM TP WHERE TPID = ?", (tp_id,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None

    def submit_rapport(self, tp_id, etudiant_id, rapport_link):
        cursor = self.conn.cursor()
        try:
            sql = """
            INSERT INTO Soumission (TPID, EtudiantID, LienRapport, DateSoumission) 
            VALUES (?, ?, ?, GETDATE())
            """
            cursor.execute(sql, (tp_id, etudiant_id, rapport_link))
            self.conn.commit()
            print(f"✅ Rapport Link submitted for Student {etudiant_id} on TP {tp_id}")
            return True
        except Exception as e:
            print(f"❌ Error submitting rapport: {e}")
            return False