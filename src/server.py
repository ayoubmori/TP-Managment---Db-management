import socket
import json
import time
import random

SERVER_IP = 'localhost' 
PORT = 5000

def send_request(action, payload):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((SERVER_IP, PORT))
        request = payload.copy()
        request['action'] = action
        client.send(json.dumps(request).encode('utf-8'))
        data = client.recv(4096 * 4) 
        return json.loads(data.decode('utf-8'))
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        client.close()

# ==========================================
# 🖼️ GUI SIMULATION (GOOGLE DRIVE PICKER)
# ==========================================
def open_google_drive_picker():
    """
    Simulates the Google Drive Import Window shown in your image.
    Returns the link of the selected file automatically.
    """
    print("\n" + "="*50)
    print("   GOOGLE DRIVE - IMPORT FILE")
    print("="*50)
    print(" [1] Récents")
    print(" [2] Importer (Upload from PC)")
    print(" [3] Mon Drive")
    print("="*50)
    
    choice = input("Select Tab (1-3): ")
    
    selected_file_name = ""
    
    if choice == '1':
        print("\n--- 📄 Récents ---")
        print(" 1. Rapport_TP_Final.pdf")
        print(" 2. Analyse_Donnees.pdf")
        file_choice = input("Select a file to import (1/2): ")
        selected_file_name = "Rapport_TP_Final.pdf" if file_choice == '1' else "Analyse_Donnees.pdf"

    elif choice == '2':
        print("\n--- 📤 Importer ---")
        print(" [ Browse Computer... ]")
        selected_file_name = input("Enter the name of the file you uploaded: ")
        print(" Uploading...")
        time.sleep(1) # Simulate upload delay
        print(" ✅ Upload Complete.")

    else:
        print("\n--- 📂 Mon Drive ---")
        print(" 1. Folder: Cours_Python/")
        print(" 2. File: Mon_Rapport.pdf")
        input("Select file (2): ") # Simulating selection
        selected_file_name = "Mon_Rapport.pdf"

    if not selected_file_name:
        selected_file_name = "Rapport_Default.pdf"

    print(f"\n✅ Selected: '{selected_file_name}'")
    
    # SYSTEM AUTOMATICALLY GENERATES THE LINK (User doesn't paste it)
    # In a real web app, this is what the API does in the background.
    generated_link = f"https://drive.google.com/file/d/{random.randint(10000,99999)}/{selected_file_name}/view"
    
    print(f"🔗 Importing Link: {generated_link}")
    time.sleep(0.5)
    return generated_link

# ==========================================
# 👨‍🏫 FORMATEUR WORKFLOW
# ==========================================
def upload_tp_demo():
    print("\n--- 📤 FORMATEUR: PUBLISH NEW TP ---")
    
    # Formateur also uses the Picker to select the Subject
    print("👉 Opening Drive to select Subject...")
    time.sleep(1)
    link = open_google_drive_picker()

    payload = {
        "titre": "TP Data Analysis", 
        "description": "Complete the tasks in the doc.",
        "link": link, 
        "deadline": "2024-12-05 23:59:00",
        "module_id": 1, 
        "formateur_id": 1, 
        "groupe_id": 1
    }
    
    print("Publishing TP...")
    resp = send_request("POST_TP", payload)
    print(f"Server Reply: {resp.get('message')}")

# ==========================================
# 🎓 STUDENT WORKFLOW
# ==========================================
def student_workflow():
    print("\n--- 🎓 STUDENT PORTAL ---")
    
    print("Fetching your assignments...")
    resp = send_request("GET_MY_TPS", {"groupe_id": 1})
    
    if resp['status'] != 'success' or not resp['data']:
        print("No assignments found.")
        return

    tps = resp['data']
    print(f"\nFound {len(tps)} Assignments:")
    for i, tp in enumerate(tps):
        print(f" [{i+1}] {tp['titre']} (Due: {tp['deadline']})")
        # print(f"     🔗 SUBJECT: {tp['link']}")

    choice = input("\nChoose TP Number to submit report for: ")
    try:
        selected_tp = tps[int(choice)-1]
    except:
        return

    # 2. SUBMIT RAPPORT (USING PICKER)
    print(f"\n--- SUBMITTING RAPPORT FOR: {selected_tp['titre']} ---")
    print("👉 Clicking 'Import from Drive'...")
    time.sleep(1)
    
    # This replaces the manual input
    generated_link = open_google_drive_picker()
    
    if generated_link:
        sub_resp = send_request("SUBMIT_RAPPORT", {
            "tp_id": selected_tp['id'],
            "etudiant_id": 3,
            "link": generated_link
        })
        print(f"Server: {sub_resp.get('message')}")

def main():
    print("--- 🏫 TP MANAGEMENT SYSTEM (CLOUD LINKS) ---")
    print("1. Login as Formateur")
    print("2. Login as Student")
    choice = input("Select User: ")

    if choice == '1':
        upload_tp_demo()
    elif choice == '2':
        student_workflow()

if __name__ == "__main__":
    main()