import pyodbc
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import random

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
        
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

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
            # 1. Check if the admin typed a new password
            new_password = data.get('password')
            
            if new_password and new_password.strip():
                # ✅ CASE A: Password Changed -> HASH IT
                hashed_pw = generate_password_hash(new_password)
                
                sql = "UPDATE Utilisateur SET Nom=?, Prenom=?, Email=?, MotDePasse=? WHERE UserID=?"
                params = (data['nom'], data['prenom'], data['email'], hashed_pw, user_id)
            else:
                # ✅ CASE B: Password Empty -> KEEP OLD PASSWORD
                sql = "UPDATE Utilisateur SET Nom=?, Prenom=?, Email=? WHERE UserID=?"
                params = (data['nom'], data['prenom'], data['email'], user_id)

            # Execute the User Table Update
            cursor.execute(sql, params)

            # 2. Update Role-Specific Tables (Etudiant / Formateur)
            if data['role'] == 'Etudiant':
                # Handle potential empty CNE or Groupe
                cne = data.get('cne')
                groupe_id = data.get('groupe_id')
                cursor.execute(
                    "UPDATE Etudiant SET CNE=?, GroupeID=? WHERE EtudiantID=?", 
                    (cne, groupe_id, user_id)
                )
            elif data['role'] == 'Formateur':
                matricule = data.get('matricule')
                cursor.execute(
                    "UPDATE Formateur SET Matricule=? WHERE FormateurID=?", 
                    (matricule, user_id)
                )
            
            self.conn.commit()
            return True

        except Exception as e:
            print(f"❌ Error updating user: {e}")
            self.conn.rollback() # Undo changes if error
            return False

    def delete_user(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM Utilisateur WHERE UserID = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception: return False

    def create_user_account(self, nom, prenom, email, password, role, extra):
        cursor = self.conn.cursor()
        hashed_pw = generate_password_hash(password) 
        
        try:
            # 1. Insert into Base Table (Utilisateur)
            cursor.execute(
                "INSERT INTO Utilisateur (Nom, Prenom, Email, MotDePasse, Role) VALUES (?,?,?,?,?)", 
                (nom, prenom, email, hashed_pw, role)
            )
            
            # 2. Get the new ID safely
            cursor.execute("SELECT @@IDENTITY")
            user_id = cursor.fetchone()[0]

            # 3. Insert into Role Table
            if role == 'Etudiant':
                # Handle Student
                cne = extra.get('cne')
                if not cne: cne = f"S-{random.randint(10000,99999)}" # Auto-generate CNE if missing
                
                cursor.execute(
                    "INSERT INTO Etudiant (EtudiantID, CNE, GroupeID, DateNaissance) VALUES (?, ?, ?, GETDATE())",
                    (user_id, cne, extra.get('groupe_id'))
                )
                
            elif role == 'Formateur':
                # Handle Formateur
                matricule = extra.get('matricule')
                # AUTO-FIX: If matricule is empty, generate one to prevent DB Error
                if not matricule: 
                    matricule = f"PROF-{random.randint(1000, 9999)}"
                
                cursor.execute(
                    "INSERT INTO Formateur (FormateurID, Matricule, Specialite) VALUES (?, ?, ?)",
                    (user_id, matricule, 'General')
                )
            
            self.conn.commit()
            print(f"✅ User {email} created successfully.")
            return True

        except Exception as e:
            print(f"❌ DATABASE ERROR: {e}") # <--- Check your terminal for this!
            self.conn.rollback()
            return False
        
    def login(self, email, password):
        cursor = self.conn.cursor()
        # Fetch the HASH, not the password
        sql = "SELECT UserID, Nom, Prenom, Role, MotDePasse FROM Utilisateur WHERE Email = ?"
        cursor.execute(sql, (email,))
        row = cursor.fetchone()
        
        # Verify the hash
        if row and check_password_hash(row.MotDePasse, password):
             return {"id": row.UserID, "name": f"{row.Nom} {row.Prenom}", "role": row.Role}
        return None

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
        
    # --- GETTERS FOR DROPDOWNS ---
    
    def get_all_filieres(self):
        """Returns list of Filieres (ADIA, IL, IISE)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT FiliereID, NomFiliere FROM Filiere")
        return [{"id": row.FiliereID, "name": row.NomFiliere} for row in cursor.fetchall()]

    def get_groups_by_filiere_id(self, filiere_id):
        """Returns groups strictly for one major"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT GroupeID, NomGroupe FROM Groupe WHERE FiliereID = ?", (filiere_id,))
        return [{"id": row.GroupeID, "name": row.NomGroupe} for row in cursor.fetchall()]

    def get_all_modules(self):
        """Returns list of Modules (Python, BI, ML...)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT ModuleID, NomModule FROM Module")
        return [{"id": row.ModuleID, "name": row.NomModule} for row in cursor.fetchall()]

    # --- SMART ASSIGNMENT LOGIC ---
    
    def assign_formateur_to_module(self, formateur_id, groupe_id, module_id):
        """
        Links a teacher to a class. 
        Example: Mr. Ayoub -> ADIA Grp 1 -> Python
        """
        cursor = self.conn.cursor()
        try:
            sql = "INSERT INTO Affectation (FormateurID, GroupeID, ModuleID) VALUES (?, ?, ?)"
            cursor.execute(sql, (formateur_id, groupe_id, module_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error assigning formateur: {e}")
            return False
        
    def get_teacher_assignments_detailed(self, formateur_id):
        """
        Returns a list of all classes assigned to a specific teacher.
        Used for the Admin 'Manage Classes' modal.
        """
        cursor = self.conn.cursor()
        sql = """
        SELECT A.AffectationID, G.NomGroupe, M.NomModule 
        FROM Affectation A
        JOIN Groupe G ON A.GroupeID = G.GroupeID
        JOIN Module M ON A.ModuleID = M.ModuleID
        WHERE A.FormateurID = ?
        ORDER BY G.NomGroupe
        """
        cursor.execute(sql, (formateur_id,))
        return [
            {"id": r.AffectationID, "group": r.NomGroupe, "module": r.NomModule} 
            for r in cursor.fetchall()
        ]

    def delete_assignment(self, assignment_id):
        """
        Removes a specific class assignment.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM Affectation WHERE AffectationID = ?", (assignment_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting assignment: {e}")
            return False

    def get_teacher_modules(self, formateur_id):
        """
        When a teacher logs in, this gets ONLY the groups/modules assigned to them.
        """
        cursor = self.conn.cursor()
        sql = """
        SELECT M.ModuleID, M.NomModule, G.GroupeID, G.NomGroupe 
        FROM Affectation A
        JOIN Module M ON A.ModuleID = M.ModuleID
        JOIN Groupe G ON A.GroupeID = G.GroupeID
        WHERE A.FormateurID = ?
        """
        cursor.execute(sql, (formateur_id,))
        return [{"module_id": r.ModuleID, "module_name": r.NomModule, 
                 "group_id": r.GroupeID, "group_name": r.NomGroupe} for r in cursor.fetchall()]
        
    
    def submit_rapport_file(self, tp_id, etudiant_id, file_bytes, filename, filetype):
        """
        Saves the Student's PDF report directly into the Database.
        """
        cursor = self.conn.cursor()
        try:
            # Check if submission already exists (Optional: to allow re-upload)
            # For simplicity, we just insert a new attempt
            sql = """
            INSERT INTO Soumission (TPID, EtudiantID, FichierData, FichierNom, FichierType, DateSoumission) 
            VALUES (?, ?, ?, ?, ?, GETDATE())
            """
            
            # Use pyodbc.Binary to handle the bytes safely
            cursor.execute(sql, (tp_id, etudiant_id, pyodbc.Binary(file_bytes), filename, filetype))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error submitting rapport: {e}")
            return False
        
        
    # --- ADMIN: USER MANAGEMENT ENHANCED ---
    def get_all_users_extended(self):
        """
        Fetches users with extra context:
        - Students: Includes their Group Name.
        - Formateurs: We will attach their assigned groups later in Python.
        """
        cursor = self.conn.cursor()
        
        # 1. Fetch Basic Info + Student Group Name
        sql = """
        SELECT U.UserID, U.Nom, U.Prenom, U.Email, U.Role, 
               G.NomGroupe, F.Matricule, E.CNE
        FROM Utilisateur U
        LEFT JOIN Etudiant E ON U.UserID = E.EtudiantID
        LEFT JOIN Groupe G ON E.GroupeID = G.GroupeID
        LEFT JOIN Formateur F ON U.UserID = F.FormateurID
        ORDER BY U.Role, U.Nom
        """
        cursor.execute(sql)
        users = []
        for row in cursor.fetchall():
            user = {
                "id": row.UserID, 
                "name": f"{row.Nom} {row.Prenom}", 
                "email": row.Email, 
                "role": row.Role,
                "student_group": row.NomGroupe, # Only for students
                "matricule": row.Matricule,
                "cne": row.CNE,
                "teacher_groups": [] # Will populate below
            }
            users.append(user)
            
        # 2. Fetch All Teacher Assignments in one go to be efficient
        sql_assign = """
        SELECT A.FormateurID, G.NomGroupe, M.NomModule
        FROM Affectation A
        JOIN Groupe G ON A.GroupeID = G.GroupeID
        JOIN Module M ON A.ModuleID = M.ModuleID
        """
        cursor.execute(sql_assign)
        assignments = cursor.fetchall()
        
        # 3. Map Assignments to Teachers
        for assign in assignments:
            # Find the teacher in our list and append the group
            for u in users:
                if u['id'] == assign.FormateurID:
                    u['teacher_groups'].append(f"{assign.NomGroupe} ({assign.NomModule})")
        
        return users

    # --- TP MANAGEMENT ---
    def get_tps_by_formateur(self, formateur_id):
        """ For Formateur Dashboard: See their own history """
        cursor = self.conn.cursor()
        sql = """
        SELECT TP.TPID, TP.Titre, TP.DateLimite, G.NomGroupe, M.NomModule
        FROM TP
        JOIN Groupe G ON TP.GroupeID = G.GroupeID
        JOIN Module M ON TP.ModuleID = M.ModuleID
        WHERE TP.FormateurID = ?
        ORDER BY TP.DateLimite DESC
        """
        cursor.execute(sql, (formateur_id,))
        return [{"id": r.TPID, "titre": r.Titre, "deadline": str(r.DateLimite), "group": r.NomGroupe, "module": r.NomModule} for r in cursor.fetchall()]

    def get_all_tps_global(self):
        """ For Admin Dashboard: See EVERYTHING """
        cursor = self.conn.cursor()
        sql = """
        SELECT TP.TPID, TP.Titre, TP.DateLimite, 
               G.NomGroupe, M.NomModule, 
               U.Nom, U.Prenom
        FROM TP
        JOIN Groupe G ON TP.GroupeID = G.GroupeID
        JOIN Module M ON TP.ModuleID = M.ModuleID
        JOIN Utilisateur U ON TP.FormateurID = U.UserID
        ORDER BY TP.DateLimite DESC
        """
        cursor.execute(sql)
        return [{
            "id": r.TPID, 
            "titre": r.Titre, 
            "deadline": str(r.DateLimite), 
            "group": r.NomGroupe, 
            "module": r.NomModule,
            "teacher": f"{r.Nom} {r.Prenom}"
        } for r in cursor.fetchall()]
        
        
        
    # --- PRESENCE MANAGEMENT ---
    
    def get_or_create_seance(self, formateur_id, groupe_id, module_id, date_str):
        """
        Checks if a session exists for this specific Teacher/Class/Date.
        If not, creates a new 2-hour session automatically.
        """
        cursor = self.conn.cursor()
        
        # 1. Check existing
        # SQL Server Date check: CAST(DateDebut AS DATE) = ?
        sql_check = """
        SELECT SeanceID FROM Seance 
        WHERE FormateurID=? AND GroupeID=? AND ModuleID=? 
        AND CAST(DateDebut AS DATE) = ?
        """
        cursor.execute(sql_check, (formateur_id, groupe_id, module_id, date_str))
        row = cursor.fetchone()
        
        if row:
            return row[0] # Return existing ID
            
        # 2. Create New (Defaulting to 8:00 AM - 10:00 AM for simplicity, or current time)
        # In a real app, you might ask for specific start time.
        sql_insert = """
        INSERT INTO Seance (DateDebut, DateFin, Salle, ModuleID, FormateurID, GroupeID)
        VALUES (?, ?, 'Virtual', ?, ?, ?)
        """
        # Create timestamps
        start_dt = f"{date_str} 08:00:00"
        end_dt = f"{date_str} 10:00:00"
        
        cursor.execute(sql_insert, (start_dt, end_dt, module_id, formateur_id, groupe_id))
        self.conn.commit()
        
        # Get the ID we just created
        cursor.execute("SELECT @@IDENTITY")
        return cursor.fetchone()[0]

    def get_students_with_presence(self, groupe_id, seance_id):
        """
        Fetches all students in a group, AND their presence status for a specific session.
        """
        cursor = self.conn.cursor()
        sql = """
        SELECT E.EtudiantID, U.Nom, U.Prenom, E.CNE, P.Etat
        FROM Etudiant E
        JOIN Utilisateur U ON E.EtudiantID = U.UserID
        LEFT JOIN Presence P ON E.EtudiantID = P.EtudiantID AND P.SeanceID = ?
        WHERE E.GroupeID = ?
        ORDER BY U.Nom
        """
        cursor.execute(sql, (seance_id, groupe_id))
        return [
            {"id": r.EtudiantID, "name": f"{r.Nom} {r.Prenom}", "cne": r.CNE, "status": r.Etat or "Pending"} 
            for r in cursor.fetchall()
        ]
        
    def save_bulk_presence(self, seance_id, presence_data):
        """
        Updates presence for multiple students at once.
        presence_data = [{'student_id': 10, 'status': 'Present'}, ...]
        """
        cursor = self.conn.cursor()
        try:
            for item in presence_data:
                # Upsert Logic
                sql_update = "UPDATE Presence SET Etat=?, DateEnregistrement=GETDATE() WHERE SeanceID=? AND EtudiantID=?"
                cursor.execute(sql_update, (item['status'], seance_id, item['student_id']))
                if cursor.rowcount == 0:
                    sql_insert = "INSERT INTO Presence (SeanceID, EtudiantID, Etat) VALUES (?,?,?)"
                    cursor.execute(sql_insert, (seance_id, item['student_id'], item['status']))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving presence: {e}")
            return False
        
        
    # --- ANALYTICS & DASHBOARD ---

    def get_presence_stats(self, formateur_id=None):
        """ Aggregates presence data for charts. """
        cursor = self.conn.cursor()
        where_clause = "WHERE S.FormateurID = ?" if formateur_id else ""
        params = (formateur_id,) if formateur_id else ()
        
        sql = f"""
        SELECT 
            CAST(S.DateDebut AS DATE) as SessionDate, 
            G.NomGroupe,
            M.NomModule,
            COUNT(CASE WHEN P.Etat = 'Present' THEN 1 END) as TotalPresent,
            COUNT(P.PresenceID) as TotalStudents
        FROM Seance S
        JOIN Groupe G ON S.GroupeID = G.GroupeID
        JOIN Module M ON S.ModuleID = M.ModuleID
        LEFT JOIN Presence P ON S.SeanceID = P.SeanceID
        {where_clause}
        GROUP BY CAST(S.DateDebut AS DATE), G.NomGroupe, M.NomModule
        ORDER BY SessionDate ASC
        """
        cursor.execute(sql, params)
        results = []
        for row in cursor.fetchall():
            total = row.TotalStudents
            present = row.TotalPresent
            # Avoid Python Division by Zero
            rate = round((present / total * 100), 1) if total > 0 else 0
            
            results.append({
                "date": str(row.SessionDate),
                "group": row.NomGroupe,
                "module": row.NomModule,
                "present": present,
                "total": total,
                "rate": rate
            })
        return results

    def get_global_kpis(self, formateur_id=None):
        """ 
        Gets big numbers (CRASH PROOF VERSION). 
        Uses NULLIF to handle cases where there are 0 sessions.
        """
        cursor = self.conn.cursor()
        where_sql = "WHERE FormateurID = ?" if formateur_id else ""
        params = (formateur_id,) if formateur_id else ()
        
        # 1. Total Sessions
        cursor.execute(f"SELECT COUNT(*) FROM Seance {where_sql}", params)
        total_sessions = cursor.fetchone()[0]
        
        # 2. Global Attendance Rate (Safe Division)
        # NULLIF(COUNT(*), 0) returns NULL if count is 0, preventing the crash.
        sql_rate = f"""
        SELECT 
            ISNULL(
                (COUNT(CASE WHEN P.Etat = 'Present' THEN 1 END) * 100.0) / NULLIF(COUNT(*), 0), 
                0
            )
        FROM Presence P
        JOIN Seance S ON P.SeanceID = S.SeanceID
        {where_sql}
        """
        cursor.execute(sql_rate, params)
        row = cursor.fetchone()
        avg_rate = round(row[0], 1) if row and row[0] is not None else 0
        
        return {"total_sessions": total_sessions, "avg_rate": avg_rate}

    def get_absent_report(self, formateur_id=None):
        """ 
        Returns comprehensive absence data including specific dates.
        Groups data by Student+Module to calculate the "3 Strikes" rule.
        """
        cursor = self.conn.cursor()
        
        where_sql = "AND S.FormateurID = ?" if formateur_id else ""
        params = (formateur_id,) if formateur_id else ()

        sql = f"""
        SELECT 
            U.Nom, U.Prenom, E.CNE, G.NomGroupe, M.NomModule, S.DateDebut
        FROM Presence P
        JOIN Seance S ON P.SeanceID = S.SeanceID
        JOIN Etudiant E ON P.EtudiantID = E.EtudiantID
        JOIN Utilisateur U ON E.EtudiantID = U.UserID
        JOIN Groupe G ON S.GroupeID = G.GroupeID
        JOIN Module M ON S.ModuleID = M.ModuleID
        WHERE P.Etat = 'Absent' {where_sql}
        ORDER BY U.Nom, M.NomModule, S.DateDebut DESC
        """
        cursor.execute(sql, params)
        
        report_map = {}
        for r in cursor.fetchall():
            key = f"{r.CNE}-{r.NomModule}"
            if key not in report_map:
                report_map[key] = {
                    "name": f"{r.Nom} {r.Prenom}",
                    "cne": r.CNE,
                    "group": r.NomGroupe,
                    "module": r.NomModule,
                    "count": 0,
                    "dates": []
                }
            report_map[key]["count"] += 1
            report_map[key]["dates"].append(r.DateDebut.strftime("%d %b %H:%M"))
            
        final_report = list(report_map.values())
        final_report.sort(key=lambda x: x['count'], reverse=True)
        return final_report


    def create_annonce(self, titre, contenu, image_bytes, formateur_id, groupe_id, module_id):
        cursor = self.conn.cursor()
        try:
            sql = """
            INSERT INTO Annonce (Titre, Contenu, ImageBin, FormateurID, GroupeID, ModuleID, DatePublication)
            VALUES (?, ?, ?, ?, ?, ?, GETDATE())
            """
            # Handle optional image
            img_data = pyodbc.Binary(image_bytes) if image_bytes else None
            
            cursor.execute(sql, (titre, contenu, img_data, formateur_id, groupe_id, module_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error creating annonce: {e}")
            return False

    def get_formateur_history_mixed(self, formateur_id):
        """
        Fetches BOTH TPs and Announcements, sorts them by date, and labels them.
        """
        cursor = self.conn.cursor()
        
        # 1. Get TPs
        sql_tp = """
        SELECT TPID as ID, Titre, DateLimite as DateItem, 'TP' as Type, G.NomGroupe, M.NomModule
        FROM TP 
        JOIN Groupe G ON TP.GroupeID = G.GroupeID
        JOIN Module M ON TP.ModuleID = M.ModuleID
        WHERE FormateurID = ?
        """
        
        # 2. Get Announcements
        sql_ann = """
        SELECT AnnonceID as ID, Titre, DatePublication as DateItem, 'Annonce' as Type, G.NomGroupe, M.NomModule
        FROM Annonce 
        JOIN Groupe G ON Annonce.GroupeID = G.GroupeID
        JOIN Module M ON Annonce.ModuleID = M.ModuleID
        WHERE FormateurID = ?
        """
        
        # Union them to get a single timeline
        final_sql = f"{sql_tp} UNION ALL {sql_ann} ORDER BY DateItem DESC"
        
        cursor.execute(final_sql, (formateur_id, formateur_id))
        
        return [
            {
                "id": r.ID, 
                "title": r.Titre, 
                "date": str(r.DateItem)[:16], 
                "type": r.Type,
                "group": r.NomGroupe,
                "module": r.NomModule
            } 
            for r in cursor.fetchall()
        ]
        
        
    # --- GRADING SYSTEM ---

    def get_submissions_for_tp(self, tp_id):
        """ Returns list of students who submitted work for a specific TP """
        cursor = self.conn.cursor()
        sql = """
        SELECT S.SoumissionID, U.Nom, U.Prenom, S.DateSoumission, S.Note, S.FichierNom
        FROM Soumission S
        JOIN Etudiant E ON S.EtudiantID = E.EtudiantID
        JOIN Utilisateur U ON E.EtudiantID = U.UserID
        WHERE S.TPID = ?
        ORDER BY U.Nom
        """
        cursor.execute(sql, (tp_id,))
        return [
            {
                "id": r.SoumissionID,
                "student": f"{r.Nom} {r.Prenom}",
                "date": r.DateSoumission.strftime("%d %b %H:%M"),
                "grade": r.Note if r.Note is not None else "",
                "file_name": r.FichierNom
            }
            for r in cursor.fetchall()
        ]

    def get_submission_file(self, submission_id):
        """ Downloads the student's report file """
        cursor = self.conn.cursor()
        cursor.execute("SELECT FichierData, FichierNom, FichierType FROM Soumission WHERE SoumissionID=?", (submission_id,))
        row = cursor.fetchone()
        if row:
            return {"data": row.FichierData, "name": row.FichierNom, "type": row.FichierType}
        return None

    def save_grade(self, submission_id, grade):
        """ Updates the grade for a student submission """
        cursor = self.conn.cursor()
        try:
            cursor.execute("UPDATE Soumission SET Note = ? WHERE SoumissionID = ?", (grade, submission_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving grade: {e}")
            return False