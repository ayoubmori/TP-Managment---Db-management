import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from db_manager import SchoolDB
from dotenv import load_dotenv
import functools
import io 
import mimetypes
import base64

# 1. Secure Configuration
load_dotenv()
app = Flask(__name__)
# Use a real secret key from .env, or a fallback for dev
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_key_change_in_prod')

# --- AUTH DECORATOR ---
def login_required(role=None):
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session: return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash("Access Denied", "danger")
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# --- AUTH ROUTES ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        with SchoolDB() as db:
            user = db.login(request.form['email'], request.form['password'])
            if user:
                session['user_id'] = user['id']
                session['name'] = user['name']
                session['role'] = user['role']
                if user['role'] == 'Direction': return redirect(url_for('admin_dashboard'))
                if user['role'] == 'Formateur': return redirect(url_for('formateur_dashboard'))
                if user['role'] == 'Etudiant': return redirect(url_for('student_dashboard'))
            else:
                flash("Invalid Credentials", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMIN ROUTES ---
@app.route('/admin')
@login_required('Direction')
def admin_dashboard():
    with SchoolDB() as db:
        # Use the NEW extended fetcher
        users = db.get_all_users_extended() 
        grouped_groups = db.get_groups_by_filiere()
        modules = db.get_all_modules()
        # Fetch Global TPs for the new table
        all_tps = db.get_all_tps_global() 
    return render_template('admin.html', users=users, grouped_groups=grouped_groups, modules=modules, all_tps=all_tps)

@app.route('/admin/create_user', methods=['POST'])
@login_required('Direction')
def create_user():
    role = request.form['role']
    extra = {}
    
    # Logic for Extra Fields
    if role == 'Etudiant':
        extra = {
            'groupe_id': request.form.get('groupe_id'), 
            'cne': request.form.get('cne')
        }
    elif role == 'Formateur':
        extra = {
            'matricule': request.form.get('matricule')
        }

    with SchoolDB() as db:
        success = db.create_user_account(
            request.form['nom'], 
            request.form['prenom'], 
            request.form['email'], 
            request.form['password'], 
            role, 
            extra
        )
    
    if success:
        flash("User created successfully!", "success")
    else:
        flash("Error creating user. Email may exist.", "danger")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/assign_module', methods=['POST'])
@login_required('Direction')
def assign_module():
    """
    Changed to return JSON for AJAX support (Modal stays open)
    """
    formateur_id = request.form.get('formateur_id')
    groupe_id = request.form.get('groupe_id')
    module_id = request.form.get('module_id')
    
    with SchoolDB() as db:
        success = db.assign_formateur_to_module(formateur_id, groupe_id, module_id)
        
    if success:
        return jsonify({'status': 'success', 'message': 'Class successfully assigned!'})
    else:
        return jsonify({'status': 'error', 'message': 'Assignment failed or already exists.'})

@app.route('/admin/delete_user/<int:user_id>')
@login_required('Direction')
def delete_user(user_id):
    with SchoolDB() as db:
        db.delete_user(user_id)
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/get_user/<int:user_id>')
@login_required('Direction')
def get_user(user_id):
    with SchoolDB() as db:
        user = db.get_user_details(user_id)
    return jsonify(user)

@app.route('/admin/update_user', methods=['POST'])
@login_required('Direction')
def update_user():
    data = {k: request.form.get(k) for k in request.form}
    with SchoolDB() as db:
        db.update_user(request.form['user_id'], data)
    return redirect(url_for('admin_dashboard'))


# --- FORMATEUR ROUTES ---
@app.route('/formateur')
@login_required('Formateur')
def formateur_dashboard():
    with SchoolDB() as db:
        my_assignments = db.get_teacher_modules(session['user_id'])
        # Use the NEW mixed history function
        history = db.get_formateur_history_mixed(session['user_id']) 
        
    return render_template('formateur.html', assignments=my_assignments, history=history)

@app.route('/publish_tp', methods=['POST'])
@login_required('Formateur')
def publish_tp():
    # 1. basic validation
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part in request'})

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})

    # 2. Collect Form Data
    title = request.form.get('titre')
    desc = request.form.get('description')
    deadline = request.form.get('deadline')
    
    # Get dynamic IDs
    module_id = request.form.get('module_id') 
    groupe_id = request.form.get('groupe_id') 
    formateur_id = session.get('user_id')

    if not module_id or not groupe_id:
        return jsonify({'status': 'error', 'message': 'Please select a class/module first.'})

    try:
        # 3. Read the file bytes into RAM
        file_bytes = file.read()

        # 4. Insert into Database
        with SchoolDB() as db:
            success = db.create_tp_with_blob(
                titre=title,
                description=desc,
                file_bytes=file_bytes,
                filename=file.filename,
                filetype=file.mimetype,
                deadline=deadline,
                module_id=module_id,
                formateur_id=formateur_id,
                groupe_id=groupe_id
            )

        if success:
            return jsonify({'status': 'success', 'message': 'TP successfully published to Database!'})
        else:
            return jsonify({'status': 'error', 'message': 'Database Insertion Failed'})

    except Exception as e:
        print(f"Server Error during upload: {e}")
        return jsonify({'status': 'error', 'message': 'Internal Server Error'})

# --- STUDENT ROUTES ---
@app.route('/student')
@login_required('Etudiant')
def student_dashboard():
    with SchoolDB() as db:
        # Retrieve the student's group ID properly
        user_details = db.get_user_details(session['user_id'])
        group_id = user_details.get('groupe_id') if user_details else None
        
        tps = []
        if group_id:
            tps = db.get_tps_for_student(group_id)
            
    return render_template('student.html', tps=tps)

@app.route('/submit_rapport', methods=['POST'])
@login_required('Etudiant')
def submit_rapport():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file uploaded'})
    
    file = request.files['file']
    tp_id = request.form.get('tp_id')
    
    if file.filename == '' or not tp_id:
        return jsonify({'status': 'error', 'message': 'Missing file or TP ID'})

    etudiant_id = session['user_id']

    try:
        file_bytes = file.read()
        
        with SchoolDB() as db:
            success = db.submit_rapport_file(
                tp_id=tp_id,
                etudiant_id=etudiant_id,
                file_bytes=file_bytes,
                filename=file.filename,
                filetype=file.mimetype
            )

        if success:
            return jsonify({'status': 'success', 'message': 'Rapport submitted successfully!'})
        else:
            return jsonify({'status': 'error', 'message': 'Database error'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# --- SHARED: VIEW PDF ---
@app.route('/view_subject/<int:tp_id>')
def view_subject(tp_id):
    with SchoolDB() as db:
        file_info = db.get_tp_file_content(tp_id)

    if file_info and file_info['data']:
        # 1. Determine Mime Type (Database vs Guess)
        # If DB has generic 'application/octet-stream', try to guess from filename
        content_type = file_info['type']
        if not content_type or 'octet-stream' in content_type:
            content_type, _ = mimetypes.guess_type(file_info['name'])
        
        # Fallback if guess fails
        if not content_type:
            content_type = 'application/pdf' if file_info['name'].endswith('.pdf') else 'text/plain'

        return send_file(
            io.BytesIO(file_info['data']),
            mimetype=content_type,
            as_attachment=False, # False = Show in Browser (Inline)
            download_name=file_info['name']
        )
    return "File not found", 404

# ... Add these routes to app.py ...

@app.route('/admin/get_assignments/<int:formateur_id>')
@login_required('Direction')
def get_assignments(formateur_id):
    with SchoolDB() as db:
        assignments = db.get_teacher_assignments_detailed(formateur_id)
    return jsonify(assignments)

@app.route('/admin/delete_assignment/<int:assignment_id>', methods=['POST'])
@login_required('Direction')
def delete_assignment(assignment_id):
    with SchoolDB() as db:
        success = db.delete_assignment(assignment_id)
    
    if success:
        return jsonify({'status': 'success', 'message': 'Class removed.'})
    else:
        return jsonify({'status': 'error', 'message': 'Could not remove class.'})
    
    
# --- NEW ROUTES FOR PRESENCE ---

@app.route('/formateur/get_session_students', methods=['POST'])
@login_required('Formateur')
def get_session_students():
    groupe_id = request.form.get('groupe_id')
    module_id = request.form.get('module_id')
    date_str = request.form.get('date') # Format YYYY-MM-DD
    formateur_id = session['user_id']
    
    with SchoolDB() as db:
        # 1. Ensure a session exists in DB for this date
        seance_id = db.get_or_create_seance(formateur_id, groupe_id, module_id, date_str)
        
        # 2. Get students linked to this session
        students = db.get_students_with_presence(groupe_id, seance_id)
        
    return jsonify({'seance_id': seance_id, 'students': students})

@app.route('/formateur/save_presence', methods=['POST'])
@login_required('Formateur')
def save_presence():
    data = request.json
    seance_id = data.get('seance_id')
    presence_list = data.get('presence_list') # List of {student_id, status}
    
    with SchoolDB() as db:
        success = db.save_bulk_presence(seance_id, presence_list)
        
    if success:
        return jsonify({'status': 'success', 'message': 'Attendance saved!'})
    else:
        return jsonify({'status': 'error', 'message': 'Database error.'})
    
    
# --- ANALYTICS ROUTES ---

@app.route('/analytics')
@login_required() # Accessible to both Admin and Formateur
def analytics_dashboard():
    role = session['role']
    
    # If Student tries to access, kick them out
    if role == 'Etudiant':
        flash("Access Denied", "danger")
        return redirect(url_for('student_dashboard'))

    with SchoolDB() as db:
        # If Admin, we need the list of teachers for the Filter Dropdown
        teachers = []
        if role == 'Direction':
            # We reuse get_all_users but filter for Formateurs in python or write a new query
            # A simple query is better here
            cursor = db.conn.cursor()
            cursor.execute("SELECT UserID, Nom, Prenom FROM Utilisateur WHERE Role='Formateur'")
            teachers = [{"id": r.UserID, "name": f"{r.Nom} {r.Prenom}"} for r in cursor.fetchall()]
            
    return render_template('analytics.html', role=role, teachers=teachers)

@app.route('/api/analytics_data', methods=['POST'])
@login_required()
def get_analytics_data():
    role = session['role']
    target_id = None
    
    if role == 'Formateur':
        target_id = session['user_id']
    elif role == 'Direction':
        req_id = request.json.get('formateur_id')
        # Only set target_id if a specific ID is sent and it's not 'all'
        if req_id and str(req_id) != 'all':
            target_id = req_id

    with SchoolDB() as db:
        stats = db.get_presence_stats(target_id)
        kpis = db.get_global_kpis(target_id) # This is now crash-proof
        absences = db.get_absent_report(target_id) # New Data
        
    return jsonify({'stats': stats, 'kpis': kpis, 'absences': absences})


# ... inside app.py ...

@app.route('/publish_annonce', methods=['POST'])
@login_required('Formateur')
def publish_annonce():
    # 1. Collect Data
    title = request.form.get('titre')
    content = request.form.get('contenu')
    groupe_id = request.form.get('groupe_id')
    module_id = request.form.get('module_id')
    formateur_id = session['user_id']
    
    # 2. Handle Optional Image
    image_bytes = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '':
            image_bytes = file.read()

    # 3. Save to DB
    with SchoolDB() as db:
        success = db.create_annonce(title, content, image_bytes, formateur_id, groupe_id, module_id)
        
    if success:
        return jsonify({'status': 'success', 'message': 'Announcement posted!'})
    else:
        return jsonify({'status': 'error', 'message': 'Database error'})


# --- GRADING ROUTES (NEW) ---

@app.route('/api/submissions/<int:tp_id>')
@login_required('Formateur')
def get_tp_submissions(tp_id):
    with SchoolDB() as db:
        submissions = db.get_submissions_for_tp(tp_id)
    return jsonify(submissions)

@app.route('/api/grade_submission', methods=['POST'])
@login_required('Formateur')
def grade_submission():
    data = request.json
    try:
        # Validate grade is number 0-20
        grade = float(data['grade'])
        if grade < 0 or grade > 20:
            return jsonify({'status': 'error', 'message': 'Grade must be 0-20'})
            
        with SchoolDB() as db:
            db.save_grade(data['submission_id'], grade)
        return jsonify({'status': 'success', 'message': 'Saved!'})
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid number'})

@app.route('/download_report/<int:submission_id>')
@login_required('Formateur')
def download_report(submission_id):
    with SchoolDB() as db:
        file_info = db.get_submission_file(submission_id)
        
    if file_info and file_info['data']:
        return send_file(
            io.BytesIO(file_info['data']),
            mimetype=file_info['type'] or 'application/pdf',
            as_attachment=True, # Force download for reports
            download_name=file_info['name']
        )
    return "File not found", 404


# --- IDM-PROOF FILE VIEWER (MASKING STRATEGY) ---
@app.route('/view_subject_secure/<int:tp_id>', methods=['POST']) 
@login_required()
def view_subject_secure(tp_id):
    with SchoolDB() as db:
        file_info = db.get_tp_file_content(tp_id)

    if file_info and file_info['data']:
        # Check if data is actually there
        if len(file_info['data']) == 0:
            return jsonify({'error': 'File is empty'}), 404

        # MASKING TRICK: 
        # 1. Send as 'application/octet-stream' so IDM ignores it.
        # 2. Name it '.bin' so IDM doesn't trigger on extension.
        return send_file(
            io.BytesIO(file_info['data']),
            mimetype='application/octet-stream', 
            as_attachment=False,
            download_name='secure_content.bin' 
        )
    return jsonify({'error': 'File not found'}), 404


# --- THE NUCLEAR OPTION: BASE64 JSON BYPASS ---
@app.route('/api/get_file_base64/<int:tp_id>')
@login_required()
def get_file_base64(tp_id):
    with SchoolDB() as db:
        file_info = db.get_tp_file_content(tp_id)

    if file_info and file_info['data']:
        # 1. Encode binary data to Base64 String
        # This makes the file look like a long text string to IDM
        b64_data = base64.b64encode(file_info['data']).decode('utf-8')
        
        return jsonify({
            'status': 'success',
            'filename': file_info['name'],
            'file_data': b64_data, # The PDF is hidden inside this string
            'mime_type': 'application/pdf'
        })
        
    return jsonify({'status': 'error', 'message': 'File not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)