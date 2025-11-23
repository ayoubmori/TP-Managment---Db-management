import socket
import threading
import json
from src.db_manager import SchoolDB

# CONFIGURATION
HOST = '0.0.0.0'  # Listen on all network interfaces (Wifi, Ethernet)
PORT = 5000       # Port to open

def handle_client(client_socket, addr):
    """
    Handles a single connection from a Formateur or Student.
    """
    print(f"[NEW CONNECTION] {addr} connected.")
    
    # 1. Connect to DB for this specific thread
    db = SchoolDB()
    db.connect()

    try:
        while True:
            # 2. Receive Request (1024 bytes buffer)
            request_data = client_socket.recv(4096).decode('utf-8')
            if not request_data:
                break # Client disconnected

            print(f"[{addr}] Received: {request_data}")
            
            # 3. Parse JSON Command
            command = json.loads(request_data)
            response = {"status": "error", "message": "Unknown command"}

            # --- LOGIC SWITCH ---
            if command['action'] == "GET_STUDENTS":
                seance_id = command.get('seance_id')
                students = db.get_students_for_seance(seance_id)
                response = {"status": "success", "data": students}

            elif command['action'] == "MARK_PRESENCE":
                s_id = command.get('seance_id')
                e_id = command.get('etudiant_id')
                stat = command.get('status')
                db.mark_presence(s_id, e_id, stat)
                response = {"status": "success", "message": "Presence saved."}

            # 4. Send Response
            client_socket.send(json.dumps(response).encode('utf-8'))

    except Exception as e:
        print(f"[ERROR] {addr}: {e}")
    finally:
        db.close()
        client_socket.close()
        print(f"[DISCONNECTED] {addr}")

def start_server():
    print(f"--- 📡 DIRECTION SERVER RUNNING ON PORT {PORT} ---")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    
    print(f"[LISTENING] Waiting for Formateur apps...")
    
    while True:
        client_sock, addr = server.accept()
        # Start a new thread for each client so multiple formateurs can connect
        thread = threading.Thread(target=handle_client, args=(client_sock, addr))
        thread.start()

if __name__ == "__main__":
    start_server()