from src.db_manager import SchoolDB

def main():
    # 1. Initialize Connection
    db = SchoolDB()
    db.connect()

    if db.conn is None:
        return

    print("\n--- 👨‍🏫 FORMATEUR CONSOLE : TP SESSION MANAGER ---")

    # ---------------------------------------------------------
    # SCENARIO: Formateur starts "Python" session (Seance ID 1)
    # ---------------------------------------------------------
    # We assume Seance ID 1 exists because your SQL script created it.
    target_seance_id = 1
    
    print(f"\n[Action] Requesting student list for Seance #{target_seance_id}...")
    
    # 1. RETRIEVE (Read operation)
    students = db.get_students_for_seance(target_seance_id)
    
    if not students:
        print("❌ No students found for this session. (Did you run the SQL INSERT script?)")
    else:
        print(f"✅ Found {len(students)} students expected in class:")
        print("-" * 40)
        print(f"{'ID':<5} {'FULL NAME':<25} {'CNE':<15}")
        print("-" * 40)
        
        for s in students:
            print(f"{s['id']:<5} {s['name']:<25} {s['cne']:<15}")
            
        print("-" * 40)

        # 2. MARK PRESENCE (Write operation for the Formateur)
        # This simulates the Formateur clicking "Present" for the first student
        first_student = students[0]
        print(f"\n[Action] Marking '{first_student['name']}' as PRESENT...")
        
        db.mark_presence(
            seance_id=target_seance_id, 
            etudiant_id=first_student['id'], 
            status="Present"
        )

    # Clean up
    db.close()

if __name__ == "__main__":
    main()