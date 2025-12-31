# app.py
import os
import sqlite3
import base64
import cv2
import face_recognition
import numpy as np
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    send_file, g, jsonify, Response
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Local imports
from modules.utils import init_db, get_db, load_all_encodings
from modules.face_registration import register_student_and_encode
from modules.export_data import export_attendance_csv, export_attendance_excel
from modules.student_management import get_all_students, delete_student
from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages
from werkzeug.security import check_password_hash, generate_password_hash

# ---------- Folder setup ----------
BASE = os.path.abspath(os.path.dirname(__file__))
KNOWN_DIR = os.path.join(BASE, "known_faces")
ENC_DIR = os.path.join(BASE, "encodings")
DB_DIR = os.path.join(BASE, "database")
ATT_DIR = os.path.join(BASE, "attendance_data")
os.makedirs(KNOWN_DIR, exist_ok=True)
os.makedirs(ENC_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(ATT_DIR, exist_ok=True)

# ---------- Flask App ----------
app = Flask(__name__)
app.secret_key = "replace-this-with-a-strong-secret-key"
DATABASE_PATH = os.path.join(DB_DIR, "attendance.db")

# ---------- Initialize DB ----------
init_db(DATABASE_PATH)

# ---------- Ensure attendance table has 'status' column ----------
def ensure_attendance_status_column(db_path):
    """
    Make sure attendance table has a 'status' TEXT column.
    If missing, add it with ALTER TABLE (safe, preserves data).
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(attendance)")
        cols = [r[1] for r in cur.fetchall()]  # second field is column name
        if 'status' not in cols:
            # Add column (default NULL). SQLite allows ADD COLUMN for simple cases.
            cur.execute("ALTER TABLE attendance ADD COLUMN status TEXT")
            conn.commit()
            print("✅ Added 'status' column to attendance table.")

    except Exception as e:
        print(f"⚠️ Could not verify/add 'status' column: {e}")
    finally:
        conn.close()

# call the schema-fixer right after init_db
ensure_attendance_status_column(DATABASE_PATH)


# ---------- Globals ----------
known_face_encodings, known_face_ids, known_face_names = load_all_encodings(ENC_DIR)
camera = None  # Global camera object


# ---------- Before/After request ----------
@app.before_request
def before_request():
    g.db = get_db(DATABASE_PATH)


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db:
        db.close()


# ---------- Ensure default users ----------
def ensure_default_users():
    db = get_db(DATABASE_PATH)
    cur = db.cursor()
    cur.execute("SELECT username FROM users")
    existing = [r[0] for r in cur.fetchall()]

    users = [
        ("admin", "admin123", "admin"),
    ]

    for username, password, role in users:
        if username not in existing:
            pwd = generate_password_hash(password)
            cur.execute("INSERT INTO users(username, password_hash, role) VALUES (?, ?, ?)",
                        (username, pwd, role))
    db.commit()


ensure_default_users()


# ---------- Helper for login ----------
def require_login():
    user = request.cookies.get("user")
    return bool(user and user.strip())


# ---------- Index Page ----------
@app.route("/")
def index():
    """Show main landing page"""
    return render_template("index.html")

@app.after_request
def add_header(response):
    # har response par cache band karega
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_db(DATABASE_PATH)
        cur = db.cursor()
        cur.execute("SELECT id, username, password_hash, role FROM users WHERE username=?", (username,))
        row = cur.fetchone()

        if row and check_password_hash(row[2], password):
            role = row[3]
            flash("Login successful", "delete")
            if role == "admin":
                resp = redirect(url_for("admin_dashboard"))
            elif role == "teacher":
                resp = redirect(url_for("teacher_dashboard"))
            else:
                resp = redirect(url_for("student_dashboard"))
            resp.set_cookie("user", username)
            resp.set_cookie("role", role)
            return resp
        else:
            flash("Invalid username or password", "error")
            return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    resp = redirect(url_for("index"))
    resp.delete_cookie("user")
    resp.delete_cookie("role")
    flash("Logged out successfully", "info")
    return resp


# ---------- Dashboards ----------
@app.route("/dashboard/student")
def student_dashboard():
    if not require_login():
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # ✅ Total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # ✅ Get today's date (string)
    today = datetime.now().strftime("%Y-%m-%d")

    # ✅ Present students today
    cursor.execute("SELECT COUNT(DISTINCT token_no) FROM attendance WHERE date=?", (today,))
    present_today = cursor.fetchone()[0]

    # ✅ Absent & percentage
    absent_today = total_students - present_today if total_students > 0 else 0
    average_percentage = round((present_today / total_students) * 100, 1) if total_students > 0 else 0

    # ✅ Get student attendance records for today
    cursor.execute("SELECT token_no, name, time FROM attendance WHERE date=?", (today,))
    records = cursor.fetchall()
    present_students = [{"token_no": r[0], "name": r[1], "time": r[2]} for r in records]

    conn.close()

    return render_template(
        "student_dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        average_percentage=average_percentage,
        present_students=present_students,
        current_date=today
    )

@app.route("/dashboard/teacher")
def teacher_dashboard():
    if not require_login():
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # ✅ Total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # ✅ Get today's date (string)
    today = datetime.now().strftime("%Y-%m-%d")

    # ✅ Present students today
    cursor.execute("SELECT COUNT(DISTINCT token_no) FROM attendance WHERE date=?", (today,))
    present_today = cursor.fetchone()[0]

    # ✅ Absent & percentage
    absent_today = total_students - present_today if total_students > 0 else 0
    average_percentage = round((present_today / total_students) * 100, 1) if total_students > 0 else 0

    # ✅ Get student attendance records for today
    cursor.execute("SELECT token_no, name, time FROM attendance WHERE date=?", (today,))
    records = cursor.fetchall()
    present_students = [{"token_no": r[0], "name": r[1], "time": r[2]} for r in records]

    conn.close()

    return render_template(
        "teacher_dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        average_percentage=average_percentage,
        present_students=present_students,
        current_date=today
    )

@app.route("/dashboard/admin")
def admin_dashboard():
    if not require_login():
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # ✅ Total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # ✅ Get today's date (string)
    today = datetime.now().strftime("%Y-%m-%d")

    # ✅ Present students today
    cursor.execute("SELECT COUNT(DISTINCT token_no) FROM attendance WHERE date=?", (today,))
    present_today = cursor.fetchone()[0]

    # ✅ Absent & percentage
    absent_today = total_students - present_today if total_students > 0 else 0
    average_percentage = round((present_today / total_students) * 100, 1) if total_students > 0 else 0

    # ✅ Get student attendance records for today
    cursor.execute("SELECT token_no, name, time FROM attendance WHERE date=?", (today,))
    records = cursor.fetchall()
    present_students = [{"token_no": r[0], "name": r[1], "time": r[2]} for r in records]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        average_percentage=average_percentage,
        present_students=present_students,
        current_date=today
    )



# ---------- Register Student ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if not require_login():
        return redirect(url_for("login"))

    global known_face_encodings, known_face_ids, known_face_names

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        token_no = request.form.get("token_no", "").strip()
        photo = request.files.get("photo")

        if not (name and token_no and photo and photo.filename):
            flash("❌ Fill name, token AND capture photo first!", "error")
            return redirect(url_for("register"))

        filename = secure_filename(f"{token_no}_{name}.jpg")
        save_path = os.path.join(KNOWN_DIR, filename)
        photo.save(save_path)

        try:
            success = register_student_and_encode(DATABASE_PATH, save_path, token_no, name, ENC_DIR)
            if success:
                flash("✅ Student registered successfully!", "success")
                known_face_encodings, known_face_ids, known_face_names = load_all_encodings(ENC_DIR)
            else:
                flash(f"❌ Token {token_no} already registered!", "error")
        except Exception as e:
            flash(f"❌ Error: {str(e)}", "error")

        return redirect(url_for("register"))

    # ✅ NO FLASH CLEARING NEEDED - HTML auto-hides after 5 sec
    return render_template("register_student.html")


# ---------- Student Management ----------
@app.route("/students")
def students():
    students_list = get_all_students(DATABASE_PATH)
    return render_template("student_management.html", students=students_list)


@app.route("/edit_student/<token_no>", methods=["GET", "POST"])
def edit_student(token_no):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name")
        new_token = request.form.get("token_no")

        if new_token and new_token != token_no:
            c.execute("SELECT token_no FROM students WHERE token_no=?", (new_token,))
            if c.fetchone():
                flash("Token No already exists.", "danger")
                conn.close()
                return redirect(url_for("edit_student", token_no=token_no))

        c.execute("UPDATE students SET token_no=?, name=? WHERE token_no=?", (new_token, name, token_no))
        conn.commit()
        conn.close()
        flash("Student updated successfully!", "delete")
        return redirect(url_for("students"))

    c.execute("SELECT token_no, name, photo_path FROM students WHERE token_no=?", (token_no,))
    student = c.fetchone()
    conn.close()

    if not student:
        flash("Student not found!", "danger")
        return redirect(url_for("students"))

    return render_template("edit_student.html", student=student)


@app.route("/delete_student/<token_no>")
def delete_student_route(token_no):
    delete_student(DATABASE_PATH, token_no, KNOWN_DIR, ENC_DIR)
    flash("Student deleted successfully!", "delete")
    return redirect(url_for("students"))


# ---------- Live Attendance ----------
@app.route("/attendance/live")
def live_attendance():
    if not require_login():
        return redirect(url_for("login"))
    return render_template("face_recognition.html")


@app.route("/start_attendance")
def start_attendance():
    if not require_login():
        return redirect(url_for("login"))
    return redirect(url_for("live_attendance"))


# ---------- MJPEG Stream Route ----------
# (gen_frames unchanged from your working version)
def gen_frames():
    """
    Robust frame generator:
     - tries to open camera on indices 0..3
     - works on a resized frame for speed
     - requires same recognized token_no in N consecutive frames before inserting attendance
     - reloads encodings from disk if empty (useful after new registrations)
    """
    global camera, known_face_encodings, known_face_ids, known_face_names

    # Try to open camera if not already opened
    if camera is None or not getattr(camera, "isOpened", lambda: False)():
        camera = None
        for i in range(0, 4):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(i)
            except Exception:
                cap = cv2.VideoCapture(i)
            if cap is not None and cap.isOpened():
                camera = cap
                print(f"✅ Camera opened at index {i}")
                break
            else:
                try:
                    cap.release()
                except Exception:
                    pass
        if camera is None:
            print("❌ Could not open any camera (indices 0..3).")
            return

    db = get_db(DATABASE_PATH)

    # parameters
    LATE_THRESHOLD = "09:15:00"
    tolerance = 0.5
    REQUIRED_CONSECUTIVE = 3  # require N consecutive matches before marking attendance

    # state for consecutive detection { token_no: count }
    consecutive_counts = {}
    # last seen timestamp to decay old counts
    last_seen_ts = {}

    # reload timing
    last_reload = 0
    RELOAD_INTERVAL = 5.0  # seconds

    print("🔎 gen_frames started.")

    while True:
        # If encodings list is empty, try reload periodically
        try:
            if (not known_face_encodings) or len(known_face_encodings) == 0:
                now_ts_try = datetime.now().timestamp()
                if now_ts_try - last_reload > RELOAD_INTERVAL:
                    try:
                        encs, ids, names = load_all_encodings(ENC_DIR)
                        # ensure dtype/numpy arrays
                        if encs:
                            known_face_encodings = [np.array(e) for e in encs]
                            known_face_ids = ids
                            known_face_names = names
                        print(f"🔁 Reloaded encodings: {len(known_face_encodings)}")
                    except Exception as e:
                        print(f"⚠️ Error reloading encodings: {e}")
                    last_reload = now_ts_try
        except Exception as e:
            print(f"⚠️ Encoding reload check failed: {e}")

        success, frame = camera.read()
        if not success:
            print("❌ camera.read() failed.")
            break

        # Resize for speed and easier coordinate scaling
        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        # detect faces & encodings on small frame
        face_locations = face_recognition.face_locations(rgb_small)
        face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

        # debug prints so you can see terminal output
        if len(face_locations) == 0:
            # only print sometimes to avoid flooding
            if int(datetime.now().timestamp()) % 5 == 0:
                print("ℹ️ No faces detected in this frame.")
        else:
            print(f"👀 Faces detected: {len(face_locations)}")

        # clean up stale counts older than 5 seconds
        now_ts = datetime.now().timestamp()
        stale_keys = [k for k, t in last_seen_ts.items() if now_ts - t > 5.0]
        for k in stale_keys:
            consecutive_counts.pop(k, None)
            last_seen_ts.pop(k, None)

        for encoding, loc in zip(face_encodings, face_locations):
            # ensure we have known encodings
            if len(known_face_encodings) == 0:
                # draw yellow box to show face but no encodings available
                top, right, bottom, left = [int(v * 2) for v in loc]
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 200), 2)
                cv2.putText(frame, "No known faces loaded", (left, top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 2)
                continue

            # convert to numpy array if needed
            enc = np.array(encoding)

            # compare & find best match
            try:
                face_distances = face_recognition.face_distance(known_face_encodings, enc)
            except Exception as e:
                print(f"❌ face_distance error: {e}")
                # try forcing conversion of known encodings
                known_face_encodings = [np.array(k) for k in known_face_encodings]
                face_distances = face_recognition.face_distance(known_face_encodings, enc)

            if len(face_distances) == 0:
                continue

            best_idx = np.argmin(face_distances)
            best_distance = float(face_distances[best_idx])
            is_match = best_distance <= tolerance

            print(f"🔎 best_distance={best_distance:.3f} (tolerance={tolerance})")

            if not is_match:
                # draw red box for non-match
                top, right, bottom, left = [int(v * 2) for v in loc]
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                cv2.putText(frame, f"Unknown ({best_distance:.2f})", (left, top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                continue

            token_no = known_face_ids[best_idx]
            name = known_face_names[best_idx]

            # update consecutive counters
            consecutive_counts[token_no] = consecutive_counts.get(token_no, 0) + 1
            last_seen_ts[token_no] = now_ts

            # if we have not reached required count yet, do not insert
            if consecutive_counts[token_no] < REQUIRED_CONSECUTIVE:
                top, right, bottom, left = [int(v * 2) for v in loc]
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 200), 2)
                cv2.putText(frame, f"{name} ({consecutive_counts[token_no]})", (left, top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 200), 2)
                continue

            # reached required consecutive frames -> attempt to insert once
            today = date.today().isoformat()
            now_time = datetime.now().strftime("%H:%M:%S")

            cur = db.cursor()
            # double-check no prior attendance for today (prevents race)
            cur.execute("SELECT * FROM attendance WHERE token_no=? AND date=?", (token_no, today))
            if cur.fetchone() is None:
                status = "Late" if now_time > LATE_THRESHOLD else "On Time"
                try:
                    cur.execute(
                        "INSERT INTO attendance(token_no, name, date, time, status) VALUES (?, ?, ?, ?, ?)",
                        (token_no, name, today, now_time, status),
                    )
                    db.commit()
                    print(f"✅ Inserted attendance: {token_no} | {name} | {status} | {now_time}")
                    # reset so we don't re-insert immediately
                    consecutive_counts[token_no] = 0
                    last_seen_ts[token_no] = now_ts
                except Exception as e:
                    print(f"❌ DB insert failed: {e}")
            else:
                consecutive_counts[token_no] = 0
                last_seen_ts[token_no] = now_ts

            # draw green box for confirmed attendance
            top, right, bottom, left = [int(v * 2) for v in loc]
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # encode & yield
        ret, buffer = cv2.imencode(".jpg", frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_stop")
def video_stop():
    global camera
    if camera and camera.isOpened():
        camera.release()
    flash("Camera stopped", "info")
    return redirect(url_for("student_dashboard"))


# ---------- View Attendance ----------
@app.route("/attendance/view")
def view_attendance():
    if not require_login():
        return redirect(url_for("login"))

    db = get_db(DATABASE_PATH)
    cur = db.cursor()

    today = date.today().isoformat()

    # Present students for today
    cur.execute("SELECT token_no, name, date, time, status FROM attendance WHERE date=? ORDER BY time ASC", (today,))
    rows = cur.fetchall()

    # Absent students: those in students table but not in today's attendance
    cur.execute("""
        SELECT token_no, name FROM students 
        WHERE token_no NOT IN (SELECT token_no FROM attendance WHERE date=?)
        ORDER BY name ASC
    """, (today,))
    absent_rows = cur.fetchall()

    return render_template("view_attendance.html", rows=rows, absent_rows=absent_rows, date=today)


# ---------- Export ----------
@app.route("/attendance/export")
def export_attendance():
    if not require_login():
        return redirect(url_for("login"))

    today = date.today().isoformat()
    selected_date = request.args.get("date") or today
    fmt = request.args.get("fmt") or "csv"

    csv_path = os.path.join(ATT_DIR, f"{selected_date}.csv")
    excel_path = os.path.join(ATT_DIR, f"{selected_date}.xlsx")

    export_attendance_csv(DATABASE_PATH, csv_path)
    export_attendance_excel(DATABASE_PATH, excel_path)

    if fmt == "excel":
        return send_file(excel_path, as_attachment=True)
    return send_file(csv_path, as_attachment=True)


from flask import session

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        token_no = request.form.get("token_no")
        db = get_db(DATABASE_PATH)
        cur = db.cursor()
        # Student info match in users and students table
        cur.execute("""
            SELECT users.username FROM users
            JOIN students ON users.username = ? AND students.token_no = ? AND students.name = users.username
        """, (username, token_no))
        user = cur.fetchone()
        if user:
            session['reset_user'] = username
            return redirect(url_for('reset_password'))
        else:
            flash("Username and token number do not match!", "danger")
            return redirect(url_for('forgot_password'))
    return render_template("forgot_password.html")

from werkzeug.security import check_password_hash, generate_password_hash

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    username = session.get('reset_user')
    if not username:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    db = get_db(DATABASE_PATH)
    cur = db.cursor()
    # Fetch user's password hash
    cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if not row:
        flash("User not found.", "danger")
        session.pop('reset_user', None)
        return redirect(url_for("forgot_password"))
    saved_hash = row[0]

    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        # Verify old password
        if not check_password_hash(saved_hash, old_password):
            flash("Old password is incorrect!", "danger")
            return render_template("reset_password.html")
        # Update to new password
        cur.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                    (generate_password_hash(new_password), username))
        db.commit()
        session.pop('reset_user', None)
        flash("Password reset successful! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html")





@app.route("/register_user", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()

        if role not in ["student", "teacher", "admin"]:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("register_user"))

        if not username or not password or not role:
            flash("Please fill all fields.", "danger")
            return redirect(url_for("register_user"))

        db = get_db(DATABASE_PATH)
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE username=?", (username,))
        if cur.fetchone():
            flash("Username already exists!", "danger")
            return redirect(url_for("register_user"))

        pwd_hash = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, pwd_hash, role)
        )
        db.commit()
        flash("User registered successfully!", "success")
        return redirect(url_for("login"))
    return render_template("register_user.html")

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
