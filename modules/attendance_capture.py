import cv2
import face_recognition
import numpy as np
import threading
import datetime
import os
import pandas as pd
from modules.utils import load_all_encodings

stop_event = threading.Event()

def eye_aspect_ratio(eye):
    A = np.linalg.norm(eye[1] - eye[5])
    B = np.linalg.norm(eye[2] - eye[4])
    C = np.linalg.norm(eye[0] - eye[3])
    return (A + B) / (2.0 * C + 1e-6)

def _webcam_loop(db_path, enc_dir, known_dir, stop_event):
    encodings, token_nos, names = load_all_encodings(enc_dir)
    print(f"📁 Encodings loaded: {len(encodings)} from {enc_dir}")

    if len(encodings) == 0:
        print("⚠️ No encodings found. Please register faces first.")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Unable to open webcam.")
        return

    BLINK_THRESH = 0.18
    BLINK_FRAMES = 3
    REQUIRED_BLINKS = 2

    # 🔹 head‑movement pattern thresholds
    REQUIRED_STABLE_FRAMES = 20        # face kam se kam itne frames dikhe
    MOVE_DELTA = 20                    # center itna pixel move
    # pattern: center  -> right  -> left  (3 states)

    attendance_marked = set()

    user_blinks = {}          # token_no -> total blinks
    blink_counters = {}       # token_no -> consecutive blink frames

    user_stable_frames = {}   # token_no -> frame count
    user_center_state = {}    # token_no -> "center" / "right" / "left"
    user_last_center = {}     # token_no -> (cx, cy)

    print("✅ Webcam started. Look at camera, double blink & move head RIGHT then LEFT! (Press Q to quit)")

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to capture frame.")
            break

        small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        faces = face_recognition.face_locations(rgb_small)
        encs = face_recognition.face_encodings(rgb_small, faces)
        face_landmarks_list = face_recognition.face_landmarks(rgb_small)

        prompt = "Double blink + move head RIGHT then LEFT!"
        cv2.putText(frame, prompt, (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        for idx, (face_enc, loc) in enumerate(zip(encs, faces)):
            matches = face_recognition.compare_faces(encodings, face_enc, tolerance=0.5)
            face_dist = face_recognition.face_distance(encodings, face_enc)
            best_match = np.argmin(face_dist)

            if not matches[best_match]:
                continue

            top_s, right_s, bottom_s, left_s = loc
            top, right, bottom, left = [v * 4 for v in (top_s, right_s, bottom_s, left_s)]

            token_no = token_nos[best_match]
            name = names[best_match]

            if token_no not in user_blinks:
                user_blinks[token_no] = 0
                blink_counters[token_no] = 0
                user_stable_frames[token_no] = 0
                user_center_state[token_no] = "center"
                user_last_center[token_no] = None

            # ---------- center & movement ----------
            cx = (left + right) // 2
            cy = (top + bottom) // 2
            center = (cx, cy)

            last_center = user_last_center[token_no]
            dx = 0
            if last_center is not None:
                dx = center[0] - last_center[0]

            user_stable_frames[token_no] += 1
            user_last_center[token_no] = center

            # state machine: center -> right -> left
            state = user_center_state[token_no]
            if state == "center" and dx >= MOVE_DELTA:
                user_center_state[token_no] = "right"
            elif state == "right" and dx <= -MOVE_DELTA:
                user_center_state[token_no] = "left"

            # ---------- blink detection ----------
            if idx < len(face_landmarks_list):
                landmark = face_landmarks_list[idx]
                left_eye = np.array(landmark['left_eye'])
                right_eye = np.array(landmark['right_eye'])
                left_ear = eye_aspect_ratio(left_eye)
                right_ear = eye_aspect_ratio(right_eye)
                ear = (left_ear + right_ear) / 2.0

                if ear < BLINK_THRESH:
                    blink_counters[token_no] += 1
                else:
                    if blink_counters[token_no] >= BLINK_FRAMES:
                        user_blinks[token_no] += 1
                    blink_counters[token_no] = 0

            # ---------- final liveness condition ----------
            pattern_ok = (user_center_state[token_no] == "left" and
                          user_stable_frames[token_no] >= REQUIRED_STABLE_FRAMES)

            if (user_blinks[token_no] >= REQUIRED_BLINKS and pattern_ok):

                if token_no not in attendance_marked:
                    _mark_attendance(name)
                    attendance_marked.add(token_no)

                    # reset user state (taaki bar‑bar entry na lage)
                    user_blinks[token_no] = 0
                    blink_counters[token_no] = 0
                    user_stable_frames[token_no] = 0
                    user_center_state[token_no] = "center"
                    user_last_center[token_no] = None

                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(frame, f"{name} ✅ Attendance marked!", (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    print(f"Attendance marked for: {name}")
                else:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(frame, f"{name} (Already marked)", (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                need_blinks = max(0, REQUIRED_BLINKS - user_blinks[token_no])
                msg = f"{name}: blink {need_blinks} more & move R->L"
                cv2.putText(frame, msg, (left, top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

        cv2.imshow("Attendance - Liveness (Q to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("🛑 Webcam closed.")


def _mark_attendance(name):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    folder_path = "attendance_data"
    os.makedirs(folder_path, exist_ok=True)

    attendance_file = os.path.join(folder_path, f"attendance_{today}.csv")

    if not os.path.exists(attendance_file):
        df = pd.DataFrame(columns=["Name", "Time", "Status"])
        df.to_csv(attendance_file, index=False)

    df = pd.read_csv(attendance_file)

    if name not in df["Name"].values:
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")

        late_cutoff = datetime.datetime.strptime("09:15:00", "%H:%M:%S").time()
        status = "On Time" if now.time() <= late_cutoff else "Late"

        new_data = pd.DataFrame([[name, time_str, status]], columns=["Name", "Time", "Status"])
        df = pd.concat([df, new_data], ignore_index=True)
        df.to_csv(attendance_file, index=False)
        print(f"✅ Attendance marked for {name} ({status})")
    else:
        print(f"⚠️ {name} already marked today")


def start_webcam_attendance_nonblocking(db_path, enc_dir, known_dir):
    global stop_event
    stop_event.clear()
    t = threading.Thread(target=_webcam_loop,
                         args=(db_path, enc_dir, known_dir, stop_event),
                         daemon=False)
    t.start()


def stop_webcam():
    global stop_event
    stop_event.set()
