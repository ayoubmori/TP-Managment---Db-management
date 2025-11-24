import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

class SchoolDB:
    def __init__(self):
        driver = os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')
        server = os.getenv('DB_SERVER', 'localhost')
        database = os.getenv('DB_DATABASE', 'SchoolManagementDB')
        trusted_conn = os.getenv('DB_TRUSTED_CONNECTION', 'yes')
        trust_cert = os.getenv('DB_TRUST_CERT', 'yes')
        
        self.conn_str = (
            f"DRIVER={driver};SERVER={server};DATABASE={database};"
            f"Trusted_Connection={trusted_conn};TrustServerCertificate={trust_cert};"
        )
        self.conn = None

    def connect(self):
        try:
            self.conn = pyodbc.connect(self.conn_str)
        except Exception as e:
            print(f"❌ Connection Error: {e}")

    def close(self):
        if self.conn: self.conn.close()

    def login(self, email, password):
        cursor = self.conn.cursor()
        sql = "SELECT UserID, Nom, Prenom, Role FROM Utilisateur WHERE Email = ? AND MotDePasse = ?"
        cursor.execute(sql, (email, password))
        row = cursor.fetchone()
        return {"id": row.UserID, "name": f"{row.Nom} {row.Prenom}", "role": row.Role} if row else None

    # --- ADMIN ---
    def get_groups_by_filiere(self):
        cursor = self.conn.cursor()
        sql = """
        SELECT F.NomFiliere, G.GroupeID, G.NomGroupe 
        FROM Groupe G JOIN Filiere F ON G.FiliereID = F.FiliereID
        ORDER BY F.NomFiliere, G.NomGroupe
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        organized = {}
        for r in rows:
            if r.NomFiliere not in organized: organized[r.NomFiliere] = []
            organized[r.NomFiliere].append({'id': r.GroupeID, 'name': r.NomGroupe})
        return organized

    def get_all_users(self):
        cursor = self.conn.cursor()
        sql = "SELECT UserID, Nom, Prenom, Email, Role FROM Utilisateur ORDER BY Role, Nom"
        cursor.execute(sql)
        return [{"id": r.UserID, "name": f"{r.Nom} {r.Prenom}", "email": r.Email, "role": r.Role} for r in cursor.fetchall()]

    def get_user_details(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Utilisateur WHERE UserID = ?", (user_id,))
        u = cursor.fetchone()
        if not u: return None
        
        data = {"id": u.UserID, "nom": u.Nom, "prenom": u.Prenom, "email": u.Email, "role": u.Role, "password": u.MotDePasse, "cne":"", "matricule":"", "groupe_id":""}
        
        if u.Role == 'Etudiant':
            cursor.execute("SELECT CNE, GroupeID FROM Etudiant WHERE EtudiantID=?", (user_id,))
            ext = cursor.fetchone()
            if ext: data.update({'cne': ext.CNE, 'groupe_id': ext.GroupeID})
        elif u.Role == 'Formateur':
            cursor.execute("SELECT Matricule FROM Formateur WHERE FormateurID=?", (user_id,))
            ext = cursor.fetchone()
            if ext: data.update({'matricule': ext.Matricule})
        return data

    def update_user(self, user_id, data):
        cursor = self.conn.cursor()
        try:
            sql = "UPDATE Utilisateur SET Nom=?, Prenom=?, Email=?, MotDePasse=? WHERE UserID=?"
            cursor.execute(sql, (data['nom'], data['prenom'], data['email'], data['password'], user_id))
            if data['role'] == 'Etudiant':
                cursor.execute("UPDATE Etudiant SET CNE=?, GroupeID=? WHERE EtudiantID=?", (data['cne'], data['groupe_id'] or None, user_id))
            elif data['role'] == 'Formateur':
                cursor.execute("UPDATE Formateur SET Matricule=? WHERE FormateurID=?", (data['matricule'], user_id))
            self.conn.commit()
            return True
        except Exception: return False

    def delete_user(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM Utilisateur WHERE UserID = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception: return False

    def create_user_account(self, nom, prenom, email, password, role, extra):
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO Utilisateur (Nom, Prenom, Email, MotDePasse, Role) VALUES (?,?,?,?,?)", (nom, prenom, email, password, role))
            cursor.execute("SELECT @@IDENTITY")
            uid = cursor.fetchone()[0]
            if role == 'Etudiant':
                cursor.execute("INSERT INTO Etudiant (EtudiantID, CNE, GroupeID, DateNaissance) VALUES (?,?,?,GETDATE())", (uid, extra.get('cne'), extra.get('groupe_id')))
            elif role == 'Formateur':
                cursor.execute("INSERT INTO Formateur (FormateurID, Matricule, Specialite) VALUES (?,?,?)", (uid, extra.get('matricule'), 'General'))
            self.conn.commit()
            return True
        except Exception: return False

    # --- PROFESSIONAL FILE HANDLING (BLOBs) ---
    
    def create_tp_with_blob(self, titre, description, file_bytes, filename, filetype, deadline, module_id, formateur_id, groupe_id):
        """
        Inserts the actual PDF bytes into the SQL Database.
        No local files are stored.
        """
        cursor = self.conn.cursor()
        try:
            safe_deadline = deadline.replace("T", " ") if deadline else None
            sql = """
            INSERT INTO TP (Titre, Description, FichierData, FichierNom, FichierType, DateLimite, ModuleID, FormateurID, GroupeID) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            # Pass 'file_bytes' directly. pyodbc handles the VARBINARY conversion.
            cursor.execute(sql, (titre, description, pyodbc.Binary(file_bytes), filename, filetype, safe_deadline, module_id, formateur_id, groupe_id))
            self.conn.commit()
            print("✅ TP (BLOB) Created Successfully")
            return True
        except Exception as e:
            print(f"❌ FATAL DB ERROR: {e}")
            self.conn.rollback()
            return False

    def get_tp_file_content(self, tp_id):
        """
        Retrieves the binary data for a specific TP to serve it to the browser.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT FichierData, FichierNom, FichierType FROM TP WHERE TPID = ?", (tp_id,))
        row = cursor.fetchone()
        if row:
            return {
                "data": row.FichierData,
                "name": row.FichierNom,
                "type": row.FichierType
            }
        return None

    def get_tps_for_student(self, groupe_id):
        cursor = self.conn.cursor()
        # We don't select FichierData here because it's heavy. We fetch it only when clicked.
        sql = "SELECT TP.TPID, TP.Titre, TP.Description, TP.DateLimite, M.NomModule FROM TP JOIN Module M ON TP.ModuleID = M.ModuleID WHERE TP.GroupeID = ? ORDER BY TP.DateLimite DESC"
        cursor.execute(sql, (groupe_id,))
        return [{"id": r.TPID, "titre": r.Titre, "description": r.Description, "deadline": str(r.DateLimite), "module": r.NomModule} for r in cursor.fetchall()]

    def get_students_for_seance(self, seance_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT U.UserID, U.Nom, U.Prenom, E.CNE FROM Etudiant E JOIN Utilisateur U ON E.EtudiantID = U.UserID WHERE E.GroupeID = (SELECT GroupeID FROM Seance WHERE SeanceID = ?)", (seance_id,))
        return [{"id": r.UserID, "name": f"{r.Nom} {r.Prenom}", "cne": r.CNE} for r in cursor.fetchall()]

    def mark_presence(self, seance_id, etudiant_id, status):
        cursor = self.conn.cursor()
        try:
            cursor.execute("UPDATE Presence SET Etat=?, DateEnregistrement=GETDATE() WHERE SeanceID=? AND EtudiantID=?", (status, seance_id, etudiant_id))
            if cursor.rowcount == 0:
                cursor.execute("INSERT INTO Presence (SeanceID, EtudiantID, Etat) VALUES (?,?,?)", (seance_id, etudiant_id, status))
            self.conn.commit()
        except Exception: pass
        
    def submit_rapport(self, tp_id, etudiant_id, rapport_link):
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO Soumission (TPID, EtudiantID, LienRapport, DateSoumission) VALUES (?, ?, ?, GETDATE())", (tp_id, etudiant_id, rapport_link))
            self.conn.commit()
            return True
        except Exception: return False