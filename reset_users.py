from src.db_manager import SchoolDB
from werkzeug.security import generate_password_hash

def reset_users():
    print("--- 🔄 RESETTING USERS WITH SECURE HASHES ---")
    
    with SchoolDB() as db:
        cursor = db.conn.cursor()
        
        # 1. Clear old users (Optional: Remove if you want to keep existing data)
        # Note: We must delete from child tables first to avoid Foreign Key errors
        try:
            cursor.execute("DELETE FROM Soumission")
            cursor.execute("DELETE FROM Presence")
            cursor.execute("DELETE FROM Affectation")
            cursor.execute("DELETE FROM TP")
            cursor.execute("DELETE FROM Seance")
            cursor.execute("DELETE FROM Annonce")
            cursor.execute("DELETE FROM Etudiant")
            cursor.execute("DELETE FROM Formateur")
            cursor.execute("DELETE FROM Utilisateur")
            db.conn.commit()
            print("✅ Old data cleared.")
        except Exception as e:
            print(f"⚠️ Warning during cleanup: {e}")
            db.conn.rollback()

        # 2. Helper to Create User
        def create_user(nom, prenom, email, raw_password, role, extra=None):
            # THE MAGIC PART: Hashing the password
            hashed_pw = generate_password_hash(raw_password)
            
            # Insert into Base Table
            cursor.execute(
                "INSERT INTO Utilisateur (Nom, Prenom, Email, MotDePasse, Role) VALUES (?, ?, ?, ?, ?)", 
                (nom, prenom, email, hashed_pw, role)
            )
            
            # Get the ID
            cursor.execute("SELECT @@IDENTITY")
            user_id = cursor.fetchone()[0]
            
            # Insert into Specific Table
            if role == 'Etudiant':
                # Assuming Group 1 (ADIA-Grp1) exists from your previous SQL script
                # We need to find the ID for 'ADIA-Grp1' dynamically
                cursor.execute("SELECT GroupeID FROM Groupe WHERE NomGroupe = 'ADIA-Grp1'")
                grp_row = cursor.fetchone()
                grp_id = grp_row[0] if grp_row else 1 # Fallback to 1
                
                cursor.execute(
                    "INSERT INTO Etudiant (EtudiantID, CNE, GroupeID, DateNaissance) VALUES (?, ?, ?, GETDATE())",
                    (user_id, extra['cne'], grp_id)
                )
            elif role == 'Formateur':
                cursor.execute(
                    "INSERT INTO Formateur (FormateurID, Matricule, Specialite) VALUES (?, ?, ?)",
                    (user_id, extra['matricule'], 'General')
                )
                
            print(f"👤 Created {role}: {email} (Password: {raw_password})")

        # 3. Create the Default Accounts
        try:
            # Admin
            create_user('Admin', 'Super', 'admin@school.com', '123456', 'Direction')
            
            # Formateur
            create_user('Taouabi', 'Ayoub', 'ayoub@school.com', '123456', 'Formateur', {'matricule': 'F-100'})
            
            # Student
            create_user('Doe', 'Jane', 'jane@student.com', '123456', 'Etudiant', {'cne': 'D13000'})
            
            db.conn.commit()
            print("\n✅ SUCCESS: Users reset. You can now login with password '123456'")
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            db.conn.rollback()

if __name__ == "__main__":
    reset_users()