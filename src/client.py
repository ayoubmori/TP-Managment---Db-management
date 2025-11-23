import socket
import json
import time

# CONFIGURATION
# If testing on the SAME machine, use 'localhost'.
# If testing on TWO machines, put Machine A's IP here (e.g., '192.168.1.15')
SERVER_IP = 'localhost' 
PORT = 5000

def send_request(action, payload):
    """
    Helper function to send JSON and get JSON back.
    """
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((SERVER_IP, PORT))
        
        # Merge action into payload
        request = payload.copy()
        request['action'] = action
        
        # Send
        client.send(json.dumps(request).encode('utf-8'))
        
        # Receive
        response_data = client.recv(4096).decode('utf-8')
        return json.loads(response_data)
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        client.close()

def main():
    print("--- 📱 FORMATEUR APP (CLIENT) ---")
    
    # SCENARIO: Formateur logs in and sees Seance #1
    seance_id = 1
    print(f"\n[1] Requesting Student List for Seance {seance_id}...")
    
    response = send_request("GET_STUDENTS", {"seance_id": seance_id})
    
    if response['status'] == 'success':
        students = response['data']
        print(f"✅ Received {len(students)} students from Server:")
        for s in students:
            print(f"   - {s['name']} (ID: {s['id']})")
            
        # SCENARIO: Mark the first student as Present
        if students:
            target_student = students[0]
            print(f"\n[2] Sending Presence for {target_student['name']}...")
            
            res_presence = send_request("MARK_PRESENCE", {
                "seance_id": seance_id,
                "etudiant_id": target_student['id'],
                "status": "Present"
            })
            print(f"Server Replied: {res_presence['message']}")
            
    else:
        print(f"❌ Error from Server: {response.get('message')}")

if __name__ == "__main__":
    main()