import os
import sqlite3
import pickle
import numpy as np

def init_db(db_path):
    """Create minimal DB schema if not exists (users, students, attendance)."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # users (Used for login/roles: admin, teacher, student)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT
    )
    """)

    # students (Used for registration/management)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_no TEXT PRIMARY KEY,
        name TEXT,
        photo_path TEXT,
        encoding_path TEXT
    )
    """)

    # attendance (Used for recording daily presence)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_no TEXT PRIMARY KEY,
        name TEXT,
        date TEXT,
        time TEXT,
        status TEXT
    )
    """)
    conn.commit()
    conn.close()

def get_db(db_path):
    """Returns a connection object to the SQLite database."""
    # check_same_thread=False is important for Flask/multithreading environments
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return conn

def load_all_encodings(enc_dir):
    """
    Load all .pkl (or .dat) files from enc_dir.
    Returns: (encodings_list (np.ndarray list), token_nos_list, names_list)
    Any corrupt/invalid file is skipped with a printed warning.
    """
    encodings = []
    ids = []
    names = []
    if not os.path.isdir(enc_dir):
        return encodings, ids, names

    files = sorted([f for f in os.listdir(enc_dir) if f.lower().endswith(".pkl") or f.lower().endswith(".dat")])
    for fn in files:
        path = os.path.join(enc_dir, fn)
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            # Expect either dict with keys or tuple/list
            if isinstance(data, dict):
                enc = data.get("encoding") or data.get("enc") or data.get("face_encoding")
                token = data.get("token_no") or data.get("id") or data.get("token")
                name = data.get("name") or data.get("fullname") or data.get("student_name")
            elif isinstance(data, (list, tuple)) and len(data) >= 3:
                token, name, enc = data[0], data[1], data[2]
            else:
                raise ValueError("Unknown data format inside encoding file")

            # convert enc to numpy array if not already
            if enc is None:
                raise ValueError("encoding missing")
            enc_arr = np.array(enc, dtype=np.float64)

            # basic validation shape: A standard face_recognition encoding has 128 dimensions.
            if enc_arr.ndim != 1 or enc_arr.size < 10:
                raise ValueError("encoding shape looks invalid")

            encodings.append(enc_arr)
            ids.append(str(token))
            names.append(str(name))
        except Exception as e:
            print(f"⚠️ Could not load encoding {path}: {e}")
            # skip corrupted file
            continue

    return encodings, ids, names