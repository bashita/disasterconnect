import traceback
import json
import re
from math import asin, cos, radians, sin, sqrt
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
import os
import pymysql

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "disasterconnect-secret-key-2025")

# Set GEMINI_API_KEY in the environment. Do not commit API keys to source code.
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')

TASK_SKILL_RULES = {
    'flood': ['rescue', 'swimming'],
    'water': ['rescue', 'swimming'],
    'medical': ['first aid', 'cpr'],
    'injury': ['first aid', 'cpr'],
    'fire': ['fire safety'],
    'blood': ['medical assistance'],
    'food': ['logistics'],
    'distribution': ['logistics'],
    'rescue': ['rescue'],
}

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'mysql-2690e34-lalithashree1202-458a.h.aivencloud.com'),
    'user': os.getenv('MYSQL_USER', 'avnadmin'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE', 'disaster'),
    'port':int(os.getenv('DB_PORT',26505)),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True,
}

DB_AVAILABLE = False


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def get_db():
    return get_connection()


def ensure_table_column(conn, table_name, column_name, column_definition):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS column_count
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND column_name = %s
            """,
            (DB_CONFIG['database'], table_name, column_name)
        )
        result = cursor.fetchone()
        if not result or result.get('column_count', 0) == 0:
            cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {column_definition}")
    conn.commit()


def normalize_task_table_schema(conn):
    with conn.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM tasks")
        columns = {row['Field']: row for row in cursor.fetchall()}

        if 'emergency_id' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN emergency_id INT NULL")
        if 'required_skills' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN required_skills TEXT")
        if 'created_at' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        cursor.execute("ALTER TABLE tasks MODIFY COLUMN priority VARCHAR(50) NOT NULL DEFAULT 'Normal'")
    conn.commit()


def normalize_emergency_table_schema(conn):
    with conn.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM emergencies")
        columns = {row['Field']: row for row in cursor.fetchall()}

        if 'title' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN title VARCHAR(200) NOT NULL DEFAULT ''")
        if 'description' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN description TEXT")
        if 'location_name' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN location_name VARCHAR(200)")
        if 'latitude' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN latitude DECIMAL(10,8)")
        if 'longitude' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN longitude DECIMAL(11,8)")
        if 'severity' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN severity VARCHAR(50) DEFAULT 'Medium'")
        if 'required_skills' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN required_skills TEXT")
        if 'volunteer_count' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN volunteer_count INT DEFAULT 1")
        if 'coordinator_id' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN coordinator_id INT")
        if 'status' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN status VARCHAR(20) DEFAULT 'Active'")
        if 'created_at' not in columns:
            cursor.execute("ALTER TABLE emergencies ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    conn.commit()


def normalize_volunteer_table_schema(conn):
    with conn.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM volunteers")
        columns = {row['Field']: row for row in cursor.fetchall()}

        if 'is_available' not in columns:
            cursor.execute("ALTER TABLE volunteers ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT TRUE")
        if 'latitude' not in columns:
            cursor.execute("ALTER TABLE volunteers ADD COLUMN latitude DECIMAL(10,8)")
        if 'longitude' not in columns:
            cursor.execute("ALTER TABLE volunteers ADD COLUMN longitude DECIMAL(11,8)")
    conn.commit()


def normalize_notification_table_schema(conn):
    with conn.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM notifications")
        columns = {row['Field']: row for row in cursor.fetchall()}

        if 'title' not in columns:
            cursor.execute("ALTER TABLE notifications ADD COLUMN title VARCHAR(150) NOT NULL DEFAULT 'Notification'")
    conn.commit()


def init_db():
    global DB_AVAILABLE
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            charset='utf8mb4',
            autocommit=True,
        )
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.close()

        db = get_connection()
        with db.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS volunteers (
                    volunteer_id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(150) NOT NULL,
                    email VARCHAR(150) NOT NULL UNIQUE,
                    phone VARCHAR(30) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    skills VARCHAR(255) NOT NULL,
                    blood_group VARCHAR(20) NOT NULL,
                    availability VARCHAR(50) NOT NULL,
                    emergency_contact VARCHAR(30) NOT NULL,
                    state VARCHAR(100) NOT NULL,
                    location VARCHAR(200) NOT NULL,
                    certificate VARCHAR(255),
                    is_available BOOLEAN NOT NULL DEFAULT TRUE,
                    latitude DECIMAL(10,8),
                    longitude DECIMAL(11,8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id INT AUTO_INCREMENT PRIMARY KEY,
                    volunteer_id INT NOT NULL,
                    emergency_id INT NULL,
                    task_title VARCHAR(200) NOT NULL,
                    description TEXT NOT NULL,
                    location VARCHAR(200) NOT NULL,
                    priority VARCHAR(50) NOT NULL DEFAULT 'Normal',
                    status VARCHAR(50) NOT NULL DEFAULT 'Open',
                    assigned_date DATETIME NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deadline DATETIME,
                    assigned_by VARCHAR(150),
                    required_skills TEXT,
                    FOREIGN KEY (volunteer_id) REFERENCES volunteers(volunteer_id)
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS coordinators (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(150) NOT NULL,
                    email VARCHAR(150) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS emergencies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(200) NOT NULL DEFAULT '',
                    description TEXT,
                    location_name VARCHAR(200),
                    latitude DECIMAL(10,8),
                    longitude DECIMAL(11,8),
                    severity VARCHAR(50) DEFAULT 'Medium',
                    required_skills TEXT,
                    volunteer_count INT DEFAULT 1,
                    coordinator_id INT,
                    status VARCHAR(20) DEFAULT 'Active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    volunteer_id INT NOT NULL,
                    title VARCHAR(150) NOT NULL DEFAULT 'Notification',
                    message VARCHAR(255) NOT NULL,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (volunteer_id) REFERENCES volunteers(volunteer_id) ON DELETE CASCADE
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    volunteer_id INT NOT NULL,
                    sender VARCHAR(100) NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (volunteer_id) REFERENCES volunteers(volunteer_id) ON DELETE CASCADE
                )
                '''
            )
            ensure_table_column(db, 'tasks', 'emergency_id', 'INT NULL')
            ensure_table_column(db, 'tasks', 'required_skills', 'TEXT')
            ensure_table_column(db, 'tasks', 'created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            normalize_task_table_schema(db)
            normalize_emergency_table_schema(db)
            normalize_volunteer_table_schema(db)
            normalize_notification_table_schema(db)
        db.close()
        DB_AVAILABLE = True
    except Exception as exc:
        DB_AVAILABLE = False
        print(f"MySQL unavailable: {exc}")


init_db()


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('fullName', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        skills = request.form.get('skills', '').strip()
        blood_group = request.form.get('bloodGroup', '').strip()
        availability = request.form.get('availability', '').strip()
        emergency_contact = request.form.get('emergencyContact', '').strip()
        state = request.form.get('state', '').strip()
        location = request.form.get('location', '').strip()
        latitude=request.form.get('latitude','').strip()
        longitude=request.form.get('longitude','').strip()
        age=request.form.get('age','').strip()
        gender=request.form.get('gender','').strip()
        is_available = request.form.get('is_available', '').strip()

        if not all([full_name, email, phone, password, skills, blood_group, availability, emergency_contact, state, location,latitude, longitude,age,gender,is_available]):
            flash('Please fill in all required volunteer information.')
            return render_template('volunteer_registration.html')

        if not DB_AVAILABLE:
            flash('Database is unavailable. Please configure MySQL before registering.')
            return render_template('volunteer_registration.html')

        certificate = request.files.get('certificate')
        filename = ''
        if certificate and certificate.filename:
            filename = secure_filename(certificate.filename)
            certificate.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        try:
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    '''
                    INSERT INTO volunteers (
                        full_name, email, phone, password, skills, blood_group,
                        availability, emergency_contact, state, location, certificate, latitude, longitude, age, gender, is_available
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''',
                    (full_name, email, phone, password, skills, blood_group,
                     availability, emergency_contact, state, location, filename, latitude, longitude, age, gender, is_available)
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            flash(f'Registration failed: {exc}')
            return render_template('volunteer_registration.html')

        flash('Registration successful! Please log in.')
        return redirect(url_for('volunteer_login'))

    return render_template('volunteer_registration.html')


@app.route('/volunteer-login', methods=['GET', 'POST'])
def volunteer_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            return render_template('volunteer_login.html', error='Email and password are required.')

        if not DB_AVAILABLE:
            return render_template('volunteer_login.html', error='MySQL is not configured. Set MYSQL_USER and MYSQL_PASSWORD before logging in.')

        try:
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM volunteers WHERE email = %s', (email,))
                volunteer = cursor.fetchone()
            conn.close()

            if volunteer and volunteer.get('password') == password:
                session['volunteer_id'] = volunteer['volunteer_id']
                session['volunteer_name'] = volunteer['full_name']
                return redirect(url_for('volunteer_dashboard'))

            if volunteer:
                return render_template('volunteer_login.html', error='Invalid email or password.')

            return render_template('volunteer_login.html', error='Invalid email or password.')
        except Exception as exc:
            traceback.print_exc()
            return render_template('volunteer_login.html', error=f'Login error: {exc}')

    return render_template('volunteer_login.html')


@app.route('/volunteer-dashboard')
def volunteer_dashboard():

    if 'volunteer_id' not in session:
        return redirect(url_for('volunteer_login'))

    volunteer_id = session['volunteer_id']

    try:

        conn = get_connection()

        with conn.cursor() as cursor:

            # Volunteer Details
            cursor.execute(
                '''
                SELECT full_name, email, phone, skills, state, location
                FROM volunteers
                WHERE volunteer_id = %s
                ''',
                (volunteer_id,)
            )
            volunteer = cursor.fetchone()

            # Assigned Tasks
            cursor.execute(
                '''
                SELECT task_id,
                       task_title,
                       description,
                       location,
                       priority,
                       status,
                       assigned_date
                FROM tasks
                WHERE volunteer_id = %s
                ORDER BY assigned_date DESC
                ''',
                (volunteer_id,)
            )
            tasks = cursor.fetchall()

            # Notifications
            cursor.execute(
                '''
                SELECT title, message
                FROM notifications
                WHERE volunteer_id = %s
                ORDER BY created_at DESC
                ''',
                (volunteer_id,)
            )
            notifications = cursor.fetchall()

            if not volunteer:
                session.pop('volunteer_id', None)
                return redirect(url_for('volunteer_login'))

            # Dashboard Statistics
            completed_tasks = [
                task for task in tasks
                if task['status'] == 'Completed'
            ]

            completed_count = len(completed_tasks)
            hours_served = completed_count * 4

            # Real leaderboard scoring: more completed work and time served = more points
            volunteer_points = completed_count * 100 + hours_served * 10

            # Calculate rank against all volunteers using points descending
            cursor.execute(
                '''
                SELECT v.volunteer_id, COUNT(t.task_id) AS completed_count
                FROM volunteers v
                LEFT JOIN tasks t
                    ON t.volunteer_id = v.volunteer_id
                   AND t.status = 'Completed'
                GROUP BY v.volunteer_id
                '''
            )
            leaderboard_data = cursor.fetchall()

            leaderboard_points = {}
            for row in leaderboard_data:
                volunteer_id_value = row['volunteer_id']
                completed_total = row['completed_count'] or 0
                leaderboard_points[volunteer_id_value] = (completed_total * 100) + (completed_total * 4 * 10)

            leaderboard_rank = 1
            for other_volunteer_id, other_points in leaderboard_points.items():
                if other_volunteer_id != volunteer_id and other_points > volunteer_points:
                    leaderboard_rank += 1

            # Convert notifications into strings
            notifications = [
                f"{note['title']}: {note['message']}"
                for note in notifications
            ]

        return render_template(
            'volunteer_dashboard.html',
            volunteer=volunteer,
            assigned=len(tasks),
            tasks=tasks,
            completed=completed_count,
            hours_served=hours_served,
            leaderboard_rank=leaderboard_rank,
            notifications=notifications
        )

    except Exception as exc:
        traceback.print_exc()
        return render_template(
            'volunteer_login.html',
            error=f'Dashboard error: {exc}'
        )

    
@app.route('/volunteer-profile')
def volunteer_profile():
    if "volunteer_id" not in session:
        return redirect(url_for("volunteer_login"))

    volunteer_id = session["volunteer_id"]

    db = get_connection()
    cursor = db.cursor()

    volunteer_sql = """
    SELECT full_name,
           email,
           phone,
           blood_group,
           emergency_contact,
           location,
           skills,
           certificate,
           availability
    FROM volunteers
    WHERE volunteer_id = %s
    """
    cursor.execute(volunteer_sql, (volunteer_id,))
    volunteer = cursor.fetchone()

    if volunteer is None:
        cursor.close()
        db.close()
        return "Volunteer not found"

    task_sql = """
    SELECT task_id, status
    FROM tasks
    WHERE volunteer_id = %s
    """
    cursor.execute(task_sql, (volunteer_id,))
    tasks = cursor.fetchall()

    completed_tasks = [
        task for task in tasks
        if task.get('status') == 'Completed'
    ]
    completed_count = len(completed_tasks)
    total_hours = completed_count * 4

    leaderboard_rank = 1
    cursor.execute(
        '''
        SELECT v.volunteer_id, COUNT(t.task_id) AS completed_count
        FROM volunteers v
        LEFT JOIN tasks t
            ON t.volunteer_id = v.volunteer_id
           AND t.status = 'Completed'
        GROUP BY v.volunteer_id
        '''
    )
    leaderboard_data = cursor.fetchall()
    for row in leaderboard_data:
        if row['volunteer_id'] != volunteer_id and (row['completed_count'] or 0) > completed_count:
            leaderboard_rank += 1

    cursor.close()
    db.close()

    return render_template(
        "volunteer_profile.html",
        name=volunteer['full_name'],
        emailid=volunteer['email'],
        mobileno=volunteer['phone'],
        bloodgroup=volunteer['blood_group'],
        contactno=volunteer['emergency_contact'],
        city=volunteer['location'],
        skills=volunteer['skills'],
        certificate=volunteer['certificate'],
        availability=volunteer['availability'],
        completed_count=completed_count,
        total_hours=total_hours,
        leaderboard_rank=leaderboard_rank
    )

@app.route("/task-details")
def task_details():

    if "volunteer_id" not in session:
        return redirect(url_for("volunteer_login"))

    volunteer_id = session["volunteer_id"]

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM tasks
        WHERE volunteer_id=%s
        ORDER BY assigned_date DESC
    """,(volunteer_id,))

    tasks = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "task_details.html",
        tasks=tasks
    )

@app.route("/update-task-status/<int:task_id>", methods=["POST"])
def update_task_status(task_id):

    if "volunteer_id" not in session:
        return redirect(url_for("volunteer_login"))

    volunteer_id = session["volunteer_id"]

    status = request.form["status"]

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE tasks
        SET status=%s
        WHERE task_id=%s
        AND volunteer_id=%s
    """,(status,task_id,volunteer_id))

    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("task_details"))

@app.route("/task_detail/<int:task_id>")
def task_detail(task_id):

    if "volunteer_id" not in session:
        return redirect(url_for("volunteer_login"))

    volunteer_id = session["volunteer_id"]

    sql = """
    SELECT
        task_id,
        task_title,
        description,
        location,
        priority,
        status,
        assigned_date,
        deadline,
        assigned_by
    FROM tasks
    WHERE task_id = %s
    AND volunteer_id = %s
    """
    db = get_connection()
    cursor = db.cursor()
    cursor.execute(sql, (task_id, volunteer_id))
    task = cursor.fetchone()

    if not task:
        return "Task not found"

    return render_template(
        "task_details.html",
        taskid=task['task_id'],
        title=task['task_title'],
        description=task['description'],
        location=task['location'],
        priority=task['priority'],
        status=task['status'],
        assigned_date=task['assigned_date'],
        mobileno="+91 9876543210",
        name="Volunteer",
        role="Field Volunteer"
    )

@app.route("/notifications")
def notifications():

    if "volunteer_id" not in session:
        return redirect(url_for("volunteer_login"))

    volunteer_id = session["volunteer_id"]

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, title, message, created_at
        FROM notifications
        WHERE volunteer_id = %s
        ORDER BY created_at DESC
    """, (volunteer_id,))
    notifications = cursor.fetchall()
    cursor.close()
    db.close()

    emergency_count = 0
    task_count = 0
    for note in notifications:
        text = f"{note.get('title') or ''} {note.get('message') or ''}".lower()
        if 'emergency' in text:
            emergency_count += 1
        else:
            task_count += 1

    return render_template(
        "notifications.html",
        notifications=notifications,
        emergency_count=emergency_count,
        task_count=task_count
    )

@app.route("/chat", methods=["GET", "POST"])
def chat():

    if "volunteer_id" not in session:
        return redirect(url_for("volunteer_login"))

    volunteer_id = session["volunteer_id"]

    db = get_connection()
    cursor = db.cursor()

    # Volunteer sends message
    if request.method == "POST":

        message = request.form.get("message")

        if message.strip() != "":

            sql = """
            INSERT INTO chat_messages
            (volunteer_id,sender,message)
            VALUES(%s,%s,%s)
            """

            cursor.execute(sql,
                          (volunteer_id,
                           "Volunteer",
                           message))

            db.commit()

        return redirect(url_for("chat"))

    # Display chat

    sql = """
    SELECT sender,
           message,
           sent_at
    FROM chat_messages
    WHERE volunteer_id=%s
    ORDER BY sent_at
    """

    cursor.execute(sql,(volunteer_id,))
    messages = cursor.fetchall()

    db.close()

    return render_template(
        "chat.html",
        messages=messages
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing_page'))

#Coordinator routes and other functions
def infer_task_requirements(title, description):
    task_text = f'{title} {description}'.lower()
    matched_skills = []
    categories = []
    for keyword, skills in TASK_SKILL_RULES.items():
        if keyword in task_text:
            categories.append(keyword.title())
            matched_skills.extend(skills)
    return {
        'category': categories[0] if categories else 'General Emergency Response',
        'required_skills': sorted(set(matched_skills)),
        'volunteer_count': 1,
        'urgency': 'High' if any(word in task_text for word in ('urgent', 'critical', 'emergency', 'immediate')) else 'Medium',
        'duration': '2-4 hours',
        'location': None,
        'additional_requirements': []
    }


def get_gemini_recommendation(task_title, task_description, emergency, volunteers):
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_api_key:
        requirements = infer_task_requirements(task_title, task_description)
        return {'volunteers': get_local_ranking(emergency, volunteers, requirements['required_skills']),
                'requirements': requirements, 'source': 'local'}

    volunteer_data = [
        {
            'id': volunteer['id'],
            'name': volunteer['full_name'],
            'skills': volunteer.get('skills') or '',
            'available': bool(volunteer.get('is_available')),
            'latitude': float(volunteer['latitude']) if volunteer.get('latitude') is not None else None,
            'longitude': float(volunteer['longitude']) if volunteer.get('longitude') is not None else None,
            'active_tasks': volunteer.get('active_tasks', 0),
            'completed_tasks': volunteer.get('completed_tasks', 0)
        }
        for volunteer in volunteers
    ]
    prompt = f"""You are helping a disaster-response coordinator assign a task.
Task title: {task_title}
Task description: {task_description or 'Not provided'}
Current emergency location: {emergency['location_name']}
Emergency severity: {emergency['severity']}

Available volunteers:
{json.dumps(volunteer_data)}

Infer the task requirements and rank volunteer IDs. Return JSON only in this format:
{{"requirements": {{"category": "Medical", "required_skills": ["First Aid"], "volunteer_count": 1, "urgency": "High", "duration": "2 hours", "location": "location or null", "additional_requirements": ["first aid certification"]}}, "volunteer_ids": [12, 5], "confidence": 0.92, "reason": "brief explanation", "matching_skills": {{"12": ["First Aid"]}}}}
Use only IDs from the provided list and prefer available volunteers."""
    payload = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.2, 'maxOutputTokens': 300}
    }).encode('utf-8')
    endpoint = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{GEMINI_MODEL}:generateContent?key={gemini_api_key}'
    )
    try:
        response_request = Request(
            endpoint,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urlopen(response_request, timeout=20) as response:
            response_data = json.loads(response.read().decode('utf-8'))
        response_text = response_data['candidates'][0]['content']['parts'][0]['text']
        response_text = re.sub(r'^```(?:json)?\s*|\s*```$', '', response_text.strip())
        recommendation = json.loads(response_text)
        volunteers_by_id = {volunteer['id']: volunteer for volunteer in volunteers}
        ranked = []
        for volunteer_id in recommendation.get('volunteer_ids', []):
            if str(volunteer_id).isdigit() and int(volunteer_id) in volunteers_by_id:
                ranked.append(volunteers_by_id[int(volunteer_id)])
        requirements = recommendation.get('requirements') or infer_task_requirements(task_title, task_description)
        local_details = {volunteer['id']: volunteer for volunteer in get_local_ranking(
            emergency, volunteers, requirements.get('required_skills', []))}
        for volunteer in ranked:
            volunteer['matching_skills'] = recommendation.get('matching_skills', {}).get(str(volunteer['id']), [])
            volunteer['confidence'] = recommendation.get('confidence')
            volunteer['distance_km'] = local_details[volunteer['id']].get('distance_km')
            volunteer['match_score'] = local_details[volunteer['id']].get('match_score')
        return {'volunteers': ranked, 'requirements': requirements, 'reason': recommendation.get('reason', ''),
            'confidence': recommendation.get('confidence'), 'source': 'gemini'}
    except HTTPError as error:
        try:
            error_body = json.loads(error.read().decode('utf-8'))
            error_message = error_body.get('error', {}).get('message', str(error))
        except (json.JSONDecodeError, UnicodeDecodeError):
            error_message = str(error)
        if error.code == 429:
            requirements = infer_task_requirements(task_title, task_description)
            return {'volunteers': get_local_ranking(emergency, volunteers, requirements['required_skills']), 'requirements': requirements, 'source': 'local', 'error': 'Gemini quota is unavailable.'}
        if error.code in (401, 403):
            requirements = infer_task_requirements(task_title, task_description)
            return {'volunteers': get_local_ranking(emergency, volunteers, requirements['required_skills']), 'requirements': requirements, 'source': 'local', 'error': 'Gemini API key is invalid or unavailable.'}
        return {'volunteers': [], 'source': 'gemini', 'error': f'Gemini recommendation unavailable: {error_message}'}
    except (URLError, KeyError, IndexError, json.JSONDecodeError) as error:
        requirements = infer_task_requirements(task_title, task_description)
        return {'volunteers': get_local_ranking(emergency, volunteers, requirements['required_skills']),
            'requirements': requirements, 'source': 'local', 'error': f'Gemini unavailable; backend ranking used: {error}'}


def get_skill_words(value):
    if isinstance(value, (list, tuple, set)):
        value = ' '.join(value)
    return set(re.findall(r'[a-z0-9]+', (value or '').lower()))


def calculate_distance(emergency, volunteer):
    if None in (emergency.get('latitude'), emergency.get('longitude'), volunteer.get('latitude'), volunteer.get('longitude')):
        return None
    lat1, lon1, lat2, lon2 = map(radians, [float(emergency['latitude']), float(emergency['longitude']),
                                           float(volunteer['latitude']), float(volunteer['longitude'])])
    distance = 2 * asin(sqrt(sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2))
    return round(6371 * distance, 1)


def get_local_ranking(emergency, volunteers, required_skills=''):
    required_words = get_skill_words(required_skills)
    if not required_words:
        required_words = get_skill_words(' '.join([
            emergency.get('title') or '', emergency.get('description') or '', emergency.get('severity') or ''
        ]))
    ranked = []
    for volunteer in volunteers:
        matching_words = sorted(required_words & get_skill_words(volunteer.get('skills')))
        distance = calculate_distance(emergency, volunteer)
        skill_score = min(len(matching_words) / max(len(required_words), 1), 1) * 40
        distance_score = max(0, 1 - min(distance or 100, 100) / 100) * 30
        availability_score = 15 if volunteer.get('is_available') else 0
        workload_score = max(0, 10 - min(volunteer.get('active_tasks', 0), 10))
        experience_score = min(volunteer.get('completed_tasks', 0), 10) / 10 * 5
        score = skill_score + distance_score + availability_score + workload_score + experience_score
        ranked.append((score, distance, volunteer, matching_words))

    ranked.sort(key=lambda item: (-item[0], item[1] if item[1] is not None else float('inf'), item[2]['full_name'].lower()))
    result = []
    for score, distance, volunteer, matching_words in ranked:
        volunteer = dict(volunteer)
        volunteer['matching_skills'] = matching_words
        volunteer['distance_km'] = distance
        volunteer['match_score'] = score
        volunteer['active_tasks'] = volunteer.get('active_tasks', 0)
        volunteer['completed_tasks'] = volunteer.get('completed_tasks', 0)
        result.append(volunteer)
    return result

# COORDINATOR LOGIN

@app.route('/coordinator/login', methods=['GET', 'POST'])
def coordinator_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM coordinators WHERE email = %s AND password_hash = %s", (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session['coordinator_id'] = user['id']
            session['coordinator_name'] = user['full_name']
            return redirect(url_for('coordinator_dashboard'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('coordinator_login'))

    return render_template('coordinator_login.html')

# COORDINATOR DASHBOARD

@app.route('/coordinator/dashboard')
def coordinator_dashboard():
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM volunteers")
    total_volunteers = cur.fetchone()['total']

    cur.execute("SELECT COUNT(*) AS active FROM volunteers WHERE is_available = TRUE")
    active_volunteers = cur.fetchone()['active']

    cur.execute("SELECT COUNT(*) AS active FROM emergencies WHERE status = 'Active'")
    active_emergencies = cur.fetchone()['active']

    cur.execute("SELECT COUNT(*) AS completed FROM tasks WHERE status = 'Completed'")
    completed_tasks = cur.fetchone()['completed']

    cur.execute("SELECT * FROM emergencies ORDER BY created_at DESC")
    emergencies = cur.fetchall()

    cur.execute("""
        SELECT volunteers.*,
               volunteers.volunteer_id AS id,
          (SELECT COUNT(*) FROM tasks
           WHERE tasks.volunteer_id = volunteers.volunteer_id
             AND tasks.status IN ('Pending', 'Accepted')) AS active_tasks,
          (SELECT COUNT(*) FROM tasks
           WHERE tasks.volunteer_id = volunteers.volunteer_id
             AND tasks.status = 'Completed') AS completed_tasks
        FROM volunteers
        ORDER BY volunteers.full_name ASC
    """)
    volunteers = cur.fetchall()

    cur.execute("SELECT severity, COUNT(*) AS total FROM emergencies GROUP BY severity")
    emergencies_by_type = cur.fetchall()
    cur.execute("""
        SELECT DATE(assigned_date) AS day, COUNT(*) AS total
        FROM tasks
        WHERE status = 'Completed'
        GROUP BY DATE(assigned_date)
        ORDER BY day DESC
        LIMIT 7
    """)
    completed_by_day = list(reversed(cur.fetchall()))
    for item in completed_by_day:
        item['day'] = item['day'].isoformat()
    cur.execute("""
        SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, emergencies.created_at, tasks.assigned_date)), 1) AS average
        FROM tasks JOIN emergencies ON emergencies.id = tasks.emergency_id
        WHERE tasks.status = 'Completed'
    """)
    average_response_time = cur.fetchone()['average'] or 0

    map_emergencies = [
        {
            'id': emergency['id'],
            'title': emergency['title'],
            'location_name': emergency['location_name'],
            'severity': emergency['severity'],
            'latitude': float(emergency['latitude']) if emergency['latitude'] is not None else None,
            'longitude': float(emergency['longitude']) if emergency['longitude'] is not None else None
        }
        for emergency in emergencies
    ]

    cur.close()
    conn.close()

    return render_template(
        'coordinator_dashboard.html',
        total_volunteers=total_volunteers,
        active_volunteers=active_volunteers,
        active_emergencies=active_emergencies,
        completed_tasks=completed_tasks,
        emergencies=emergencies,
        volunteers=volunteers,
        emergencies_by_type=emergencies_by_type,
        completed_by_day=completed_by_day,
        average_response_time=average_response_time,
        map_emergencies=map_emergencies
    )

# COORDINATOR: CREATE EMERGENCY
# =====================================================
@app.route('/coordinator/create_emergency', methods=['GET', 'POST'])
def create_emergency():
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        location_name = request.form.get('location_name') or request.form.get('location')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        severity = request.form.get('severity') or request.form.get('priority', 'Medium').capitalize()
        required_skills = ', '.join(request.form.getlist('skills[]'))
        volunteer_count = request.form.get('volunteersCount') or 1

        #conn = get_db()
        #cur = conn.cursor()
        #cur.execute("ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS required_skills TEXT")
        #cur.execute("ALTER TABLE emergencies ADD COLUMN IF NOT EXISTS volunteer_count INT DEFAULT 1")
        #cur.execute("""
        #    INSERT INTO emergencies (title, description, location_name, latitude, longitude, severity, required_skills, volunteer_count, coordinator_id)
         #   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        #""", (title, description, location_name, latitude, longitude, severity, required_skills, volunteer_count, session['coordinator_id']))
        #conn.commit()
        #cur.close()
        #conn.close()

        conn = get_db()
        ensure_table_column(conn, 'emergencies', 'required_skills', 'TEXT')
        ensure_table_column(conn, 'emergencies', 'volunteer_count', 'INT DEFAULT 1')
        ensure_table_column(conn, 'tasks', 'required_skills', 'TEXT')

        cur = conn.cursor()

        cur.execute("""
            INSERT INTO emergencies
            (title, description, location_name, latitude, longitude,
            severity, required_skills, volunteer_count, coordinator_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            title,
            description,
            location_name,
            latitude,
            longitude,
            severity,
            required_skills,
            volunteer_count,
            session['coordinator_id']
        ))

        conn.commit()
        cur.close()
        conn.close()

        flash('Emergency created successfully.', 'success')
        return redirect(url_for('coordinator_dashboard'))

    return render_template('create_emergency.html')

# COORDINATOR: VOLUNTEER MANAGEMENT (list all volunteers)

@app.route('/coordinator/volunteers')
def manage_volunteers():
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT volunteers.*,
               volunteers.volunteer_id AS id,
               (SELECT COUNT(*) FROM tasks
                WHERE tasks.volunteer_id = volunteers.volunteer_id
                  AND tasks.status IN ('Pending', 'Accepted')) AS active_tasks
        FROM volunteers
        ORDER BY volunteers.full_name ASC
    """)
    volunteers = cur.fetchall()
    cur.execute("SELECT * FROM emergencies WHERE status = 'Active' ORDER BY created_at DESC LIMIT 1")
    latest_emergency = cur.fetchone()
    if latest_emergency:
        volunteers = get_local_ranking(latest_emergency, volunteers)
    cur.close()
    conn.close()

    return render_template('volunteer.html', volunteers=volunteers)


@app.route('/coordinator/volunteers/<int:volunteer_id>')
def view_volunteer(volunteer_id):
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT *, volunteer_id AS id FROM volunteers WHERE volunteer_id = %s", (volunteer_id,))
    volunteer = cur.fetchone()
    cur.close()
    conn.close()
    if not volunteer:
        flash('Volunteer was not found.', 'error')
        return redirect(url_for('manage_volunteers'))
    return render_template('volunteer_detail.html', volunteer=volunteer)


@app.route('/coordinator/volunteers/<int:volunteer_id>/remove', methods=['POST'])
def remove_volunteer(volunteer_id):
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE volunteers SET is_available = FALSE WHERE volunteer_id = %s", (volunteer_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Volunteer removed from the active roster.', 'success')
    return redirect(url_for('manage_volunteers'))


@app.route('/coordinator/analytics')
def coordinator_analytics():
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM volunteers WHERE is_available = TRUE")
    volunteers_online = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) AS total FROM tasks WHERE status = 'Completed'")
    completed_tasks = cur.fetchone()['total']
    cur.execute("""
        SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, emergencies.created_at, tasks.created_at)), 1) AS average
        FROM tasks JOIN emergencies ON emergencies.id = tasks.emergency_id
        WHERE tasks.status = 'Completed'
    """)
    response_time = cur.fetchone()['average'] or 0
    cur.execute("SELECT severity AS label, COUNT(*) AS total FROM emergencies GROUP BY severity ORDER BY total DESC")
    emergencies_by_type = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('analytics.html', volunteers_online=volunteers_online,
                           completed_tasks=completed_tasks, response_time=response_time,
                           emergencies_by_type=emergencies_by_type)

# COORDINATOR: ASSIGN TASK PAGE
# =====================================================
@app.route('/coordinator/assign_task')
def assign_task_page():
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM emergencies WHERE status = 'Active' ORDER BY created_at DESC LIMIT 1")
    selected_emergency = cur.fetchone()

    cur.execute("""
        SELECT volunteers.*,
               volunteers.volunteer_id AS id,
          (SELECT COUNT(*) FROM tasks active_tasks
           WHERE active_tasks.volunteer_id = volunteers.volunteer_id
             AND active_tasks.status IN ('Pending', 'Accepted')) AS active_tasks,
          (SELECT COUNT(*) FROM tasks completed_tasks
           WHERE completed_tasks.volunteer_id = volunteers.volunteer_id
             AND completed_tasks.status = 'Completed') AS completed_tasks
        FROM volunteers
        WHERE volunteers.is_available = TRUE
        ORDER BY volunteers.full_name ASC
    """)
    volunteers = cur.fetchall()

    cur.close()
    conn.close()

    ai_recommendation = None
    title = request.args.get('title', '')
    description = request.args.get('description', '')
    if selected_emergency and request.args.get('analyze') == '1' and title:
        ai_recommendation = get_gemini_recommendation(title, description, selected_emergency, volunteers)

    return render_template(
        'assign_task.html',
        volunteers=volunteers,
        selected_emergency=selected_emergency,
        ai_recommendation=ai_recommendation,
        title=title,
        description=description
    )

# COORDINATOR: SUBMIT TASK ASSIGNMENT
# =====================================================
@app.route('/coordinator/assign_task', methods=['POST'])
def submit_task_assignment():
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))

    emergency_id = request.form.get('emergency_id')
    title = request.form.get('title')
    description = request.form.get('description')
    requirements = infer_task_requirements(title, description)
    required_skills = ', '.join(requirements['required_skills'])
    volunteer_id = request.form.get('volunteer_id')
    priority = (request.form.get('priority') or 'Normal').strip()[:50]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM emergencies WHERE id = %s AND status = 'Active'", (emergency_id,))
    emergency = cur.fetchone()
    if not emergency:
        cur.close()
        conn.close()
        flash('Select an active emergency.', 'error')
        return redirect(url_for('assign_task_page'))

    if request.form.get('assignment_mode') == 'automatic':
        cur.execute("SELECT *, volunteer_id AS id FROM volunteers WHERE is_available = TRUE")
        available_volunteers = cur.fetchall()
        cur.execute("""
            SELECT volunteer_id, status, COUNT(*) AS total
            FROM tasks
            WHERE volunteer_id IS NOT NULL
            GROUP BY volunteer_id, status
        """)
        task_counts = {}
        for task_count in cur.fetchall():
            counts = task_counts.setdefault(task_count['volunteer_id'], {})
            counts[task_count['status']] = task_count['total']
        for volunteer in available_volunteers:
            counts = task_counts.get(volunteer['id'], {})
            volunteer['active_tasks'] = counts.get('Pending', 0) + counts.get('Accepted', 0)
            volunteer['completed_tasks'] = counts.get('Completed', 0)
        ranked = get_local_ranking(emergency, available_volunteers, required_skills)
        volunteer_id = ranked[0]['id'] if ranked else None
    if not volunteer_id:
        cur.close()
        conn.close()
        flash('No suitable volunteer was found.', 'error')
        return redirect(url_for('assign_task_page', emergency_id=emergency_id))

    cur.execute("SELECT volunteer_id AS id FROM volunteers WHERE volunteer_id = %s AND is_available = TRUE", (volunteer_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        flash('Selected volunteer was not found.', 'error')
        return redirect(url_for('assign_task_page', emergency_id=emergency_id))
    cur.close()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tasks (
            volunteer_id, emergency_id, task_title, description, location, priority, status,
            assigned_date, deadline, assigned_by, required_skills
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'Pending', NOW(), NULL, %s, %s)
    """, (volunteer_id, emergency_id, title, description, emergency.get('location_name') or '', priority, session['coordinator_id'], required_skills))
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            volunteer_id INT NOT NULL,
            message VARCHAR(255) NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (volunteer_id) REFERENCES volunteers(volunteer_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.execute(
        "INSERT INTO notifications (volunteer_id, message) VALUES (%s, %s)",
        (volunteer_id, f'New task assigned: {title}')
    )
    conn.commit()
    cur.close()
    conn.close()

    flash('Task successfully assigned to volunteer.', 'success')
    return redirect(url_for('coordinator_dashboard'))

# MAP PAGE (coordinator side)
# =====================================================
@app.route('/coordinator/map')
def live_map():
    if 'coordinator_id' not in session:
        return redirect(url_for('coordinator_login'))
    return render_template('map.html')

# MAP DATA API (used by map.html via fetch/AJAX)
# =====================================================
@app.route('/api/map-data')
def map_data_api():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT volunteer_id, full_name, latitude, longitude, is_available
        FROM volunteers
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    volunteers = cur.fetchall()

    cur.execute("""
        SELECT id, title, description, location_name, latitude, longitude, severity, status
        FROM emergencies
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND status = 'Active'
    """)
    emergencies = cur.fetchall()

    for volunteer in volunteers:
        volunteer['latitude'] = float(volunteer['latitude'])
        volunteer['longitude'] = float(volunteer['longitude'])

    for emergency in emergencies:
        emergency['latitude'] = float(emergency['latitude'])
        emergency['longitude'] = float(emergency['longitude'])

    cur.close()
    conn.close()

    return jsonify({
        'volunteers': volunteers,
        'emergencies': emergencies
    })

@app.route("/coordinator/send-message",methods=["POST"])
def coordinator_send_message():

    volunteer_id=request.form["volunteer_id"]

    message=request.form["message"]

    db=get_connection()

    cursor=db.cursor()

    cursor.execute("""
    INSERT INTO chat_messages
    (volunteer_id,sender,message)
    VALUES(%s,'Coordinator',%s)
    """,(volunteer_id,message))

    db.commit()

    return redirect(url_for(
        "coordinator_chat",
        volunteer_id=volunteer_id
    ))

@app.route("/coordinator-chat")
def coordinator_chat():

    db=get_connection()

    cursor=db.cursor()

    cursor.execute("""
    SELECT volunteer_id,
           full_name
    FROM volunteers
    ORDER BY full_name
    """)

    volunteers=cursor.fetchall()

    volunteer_id=request.args.get("volunteer_id")

    messages=[]

    if volunteer_id:

        cursor.execute("""
        SELECT sender,
               message,
               sent_at
        FROM chat_messages
        WHERE volunteer_id=%s
        ORDER BY sent_at
        """,(volunteer_id,))

        messages=cursor.fetchall()

    db.close()

    return render_template(
        "coordinator_chat.html",
        volunteers=volunteers,
        messages=messages,
        selected_volunteer=volunteer_id
    )

#Contact
@app.route("/contact", methods=["GET","POST"])
def contact():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        subject = request.form["subject"]
        message = request.form["message"]

        try:

            db = get_connection()
            cursor = db.cursor()

            cursor.execute("""
                INSERT INTO contact_messages
                (name,email,subject,message)
                VALUES(%s,%s,%s,%s)
            """,(name,email,subject,message))

            db.commit()

            cursor.close()
            db.close()

            flash("Message sent successfully!")

        except Exception as e:

            flash(f"Error : {e}")

        return redirect(url_for("contact"))

    return render_template("contact.html")

# contact messages read
@app.route("/contact-messages")
def contact_messages():

    db = get_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM contact_messages
        ORDER BY submitted_at DESC
    """)

    messages = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "contact_messages.html",
        messages=messages
    )

#about
@app.route("/about")
def about():
    return render_template("about.html")
if __name__ == '__main__':
    app.run(debug=True)
