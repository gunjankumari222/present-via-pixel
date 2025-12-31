import os
import pickle
import face_recognition
import sqlite3


def register_student_and_encode(db_path, image_path, token_no, name, enc_dir):
    """
    Registers a new student, generates their face encoding,
    saves it as a .pkl file (safe format) and updates DB.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # ✅ DUPLICATE CHECK
    cur.execute("SELECT name FROM students WHERE token_no = ?", (token_no,))
    row = cur.fetchone()
    if row is not None:
        existing_name = row[0]
        conn.close()
        print(f"⚠️ Token {token_no} is already registered for {existing_name}.")
        return False

    # ✅ FACE ENCODING
    image = face_recognition.load_image_file(image_path)
    encs = face_recognition.face_encodings(image)

    if len(encs) == 0:
        conn.close()
        raise ValueError("No face detected in uploaded image.")

    encoding = encs[0]
    os.makedirs(enc_dir, exist_ok=True)
    pkl_path = os.path.join(enc_dir, f"{token_no}.pkl")

    to_save = {
        "token_no": token_no,
        "name": name,
        "encoding": encoding.tolist()
    }

    with open(pkl_path, "wb") as f:
        pickle.dump(to_save, f)

    # ✅ INSERT
    cur.execute("""
        INSERT OR IGNORE INTO students(token_no, name, photo_path, encoding_path)
        VALUES (?, ?, ?, ?)
    """, (token_no, name, image_path, pkl_path))
    conn.commit()
    conn.close()

    print(f"✅ Student {name} (Token: {token_no}) registered!")
    return True
