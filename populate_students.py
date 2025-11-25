from src.db_manager import SchoolDB
from werkzeug.security import generate_password_hash
import random

def populate_students():
    print("--- 🚀 STARTING STUDENT POPULATION ---")
    
    # Data Sources
    filieres = ['ADIA', 'IL', 'IISE']
    first_names = ["Ali", "Sara", "Mohamed", "Fatima", "Omar", "Hiba", "Youssef", "Aya", "Mehdi"]
    last_names = ["Benali", "Amrani", "Idrissi", "Tazi", "Berrada", "Chraibi", "Fassi", "Alaoui", "Zerouali"]
    
    with SchoolDB() as db:
        cursor = db.conn.cursor()
        
        for filiere_name in filieres:
            print(f"\nProcessing Filiere: {filiere_name}...")
            
            # 1. Get Groups for this Filiere
            filiere_groups = db.get_groups_by_filiere_id(
                db.conn.execute("SELECT FiliereID FROM Filiere WHERE NomFiliere=?", (filiere_name,)).fetchone()[0]
            )
            
            if not filiere_groups:
                print(f"⚠️ No groups found for {filiere_name}. Skipping.")
                continue

            # 2. Create 9 Students (Distributed among groups)
            count = 0
            for i in range(9):
                # Distribute: Student 0,1,2 -> Grp 1 | 3,4,5 -> Grp 2 ...
                target_group = filiere_groups[i % len(filiere_groups)]
                
                fname = random.choice(first_names)
                lname = random.choice(last_names)
                email = f"{fname.lower()}.{lname.lower()}{random.randint(10,99)}@student.com"
                cne = f"{filiere_name[0]}{random.randint(100000, 999999)}"
                
                # Create User & Etudiant
                try:
                    # 1. Insert User
                    hashed_pw = generate_password_hash("123456")
                    cursor.execute(
                        "INSERT INTO Utilisateur (Nom, Prenom, Email, MotDePasse, Role) VALUES (?, ?, ?, ?, 'Etudiant')", 
                        (lname, fname, email, hashed_pw)
                    )
                    cursor.execute("SELECT @@IDENTITY")
                    user_id = cursor.fetchone()[0]
                    
                    # 2. Insert Etudiant
                    cursor.execute(
                        "INSERT INTO Etudiant (EtudiantID, CNE, GroupeID, DateNaissance) VALUES (?, ?, ?, GETDATE())",
                        (user_id, cne, target_group['id'])
                    )
                    
                    print(f"   ✅ Added {fname} {lname} -> {target_group['name']}")
                    count += 1
                except Exception as e:
                    print(f"   ❌ Failed to add {email}: {e}")
        
        db.conn.commit()
        print("\n--- 🎉 POPULATION COMPLETE ---")

if __name__ == "__main__":
    populate_students()