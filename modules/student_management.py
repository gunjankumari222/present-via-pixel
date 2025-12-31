import sqlite3
import os

def get_all_students(db_path):
    """Fetch all students sorted by name."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT token_no, name, photo_path FROM students ORDER BY name ASC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_student(db_path, token_no):
    """Fetch a single student by token_no."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT token_no, name, photo_path FROM students WHERE token_no=?", (token_no,))
    r = cur.fetchone()
    conn.close()
    return r


def update_student(db_path, token_no, name):
    """Update student details by token_no."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE students SET name=? WHERE token_no=?", (name, token_no))
    conn.commit()
    conn.close()


def delete_student(db_path, token_no, known_dir, enc_dir):
    """Delete student by token_no and remove their files."""
    # Remove DB entry
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE token_no=?", (token_no,))
    conn.commit()
    conn.close()

    # Remove photo file
    for f in os.listdir(known_dir):
        if f.startswith(token_no + "_"):
            try:
                os.remove(os.path.join(known_dir, f))
            except:
                pass

    # Remove encoding file
    pkl = os.path.join(enc_dir, f"{token_no}.pkl")
    if os.path.exists(pkl):
        try:
            os.remove(pkl)
        except:
            pass
