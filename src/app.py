from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from db_manager import SchoolDB
import functools
import io # Needed for byte stream

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_demo'

def get_db():
    db = SchoolDB()
    db.connect()
    return db

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

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.login(request.form['email'], request.form['password'])
        db.close()
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

# --- ADMIN ---
@app.route('/admin')
@login_required('Direction')
def admin_dashboard():
    db = get_db()
    users = db.get_all_users()
    grouped_groups = db.get_groups_by_filiere()
    db.close()
    return render_template('admin.html', users=users, grouped_groups=grouped_groups)

@app.route('/admin/create_user', methods=['POST'])
@login_required('Direction')
def create_user():
    db = get_db()
    role = request.form['role']
    extra = {}
    if role == 'Etudiant': extra = {'groupe_id': request.form['groupe_id'], 'cne': request.form['matricule']}
    elif role == 'Formateur': extra = {'matricule': request.form['matricule']}
    db.create_user_account(request.form['nom'], request.form['prenom'], request.form['email'], request.form['password'], role, extra)
    db.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>')
@login_required('Direction')
def delete_user(user_id):
    db = get_db()
    db.delete_user(user_id)
    db.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/get_user/<int:user_id>')
@login_required('Direction')
def get_user(user_id):
    db = get_db()
    user = db.get_user_details(user_id)
    db.close()
    return jsonify(user)

@app.route('/admin/update_user', methods=['POST'])
@login_required('Direction')
def update_user():
    db = get_db()
    data = {k: request.form.get(k) for k in request.form}
    db.update_user(request.form['user_id'], data)
    db.close()
    return redirect(url_for('admin_dashboard'))

# --- PROFESSIONAL BLOB UPLOAD ---
@app.route('/publish_tp', methods=['POST'])
@login_required('Formateur')
def publish_tp():
    """
    Reads the file into memory (RAM) and saves it directly to SQL Server (BLOB).
    No local files are created.
    """
    title = request.form.get('titre')
    desc = request.form.get('description')
    deadline = request.form.get('deadline')
    file = request.files.get('file')

    if not file or file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})

    # Read bytes
    file_bytes = file.read()
    
    db = get_db()
    success = db.create_tp_with_blob(
        title, desc, 
        file_bytes, # <--- SENDING BYTES
        file.filename, 
        file.mimetype, 
        deadline, 
        1, session['user_id'], 1
    )
    db.close()
    
    if success:
        return jsonify({'status': 'success', 'message': 'TP Uploaded to Database!'})
    return jsonify({'status': 'error', 'message': 'Database Error'})

# --- STREAMING FROM DB ---
@app.route('/view_subject/<int:tp_id>')
def view_subject(tp_id):
    """
    Fetches bytes from DB and streams to browser inline.
    """
    db = get_db()
    file_info = db.get_tp_file_content(tp_id)
    db.close()

    if file_info and file_info['data']:
        return send_file(
            io.BytesIO(file_info['data']),
            mimetype=file_info['type'],
            as_attachment=False, # False = View in Browser, True = Download
            download_name=file_info['name']
        )
    return "File not found", 404

# --- VIEWS ---
@app.route('/formateur')
@login_required('Formateur')
def formateur_dashboard():
    db = get_db()
    students = db.get_students_for_seance(1)
    db.close()
    return render_template('formateur.html', students=students, seance_id=1)

@app.route('/student')
@login_required('Etudiant')
def student_dashboard():
    db = get_db()
    tps = db.get_tps_for_student(1)
    db.close()
    return render_template('student.html', tps=tps)

@app.route('/submit_rapport', methods=['POST'])
def submit_rapport():
    db = get_db()
    data = request.json
    db.submit_rapport(data['tp_id'], 3, data['link'])
    db.close()
    return jsonify({'status': 'success', 'message': 'Submitted'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)