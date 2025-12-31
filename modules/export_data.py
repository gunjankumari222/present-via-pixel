import sqlite3
import pandas as pd
import os
from datetime import date, datetime

def get_status(time_str):
    """Return attendance status based on time (On Time / Late)."""
    try:
        time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
        cutoff = datetime.strptime("09:15:00", "%H:%M:%S").time()
        return "Late" if time_obj > cutoff else "On Time"
    except Exception:
        return "Unknown"

def export_attendance_csv(db_path, out_path):
    """Export today's attendance as CSV with On Time / Late/Absent status."""
    today = date.today().isoformat()

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT token_no, name, date, time FROM attendance WHERE date=? ORDER BY time ASC",
        conn,
        params=(today,)
    )

    # Status for present students
    if not df.empty:
        df["Status"] = df["time"].apply(get_status)
    else:
        df["Status"] = []

    # Fetch absent students
    absent_query = """
        SELECT token_no, name FROM students
        WHERE token_no NOT IN (
            SELECT token_no FROM attendance WHERE date=?
        )
        ORDER BY name ASC
    """
    absent_students = pd.read_sql_query(absent_query, conn, params=(today,))
    conn.close()

    if not absent_students.empty:
        absent_students["date"] = today
        absent_students["time"] = "--:--:--"
        absent_students["Status"] = "Absent"

    # Combine present and absent DataFrames
    export_df = pd.concat([df, absent_students], ignore_index=True, sort=False)
    export_df = export_df[["token_no", "name", "date", "time", "Status"]]  # Ensure column order

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    export_df.to_csv(out_path, index=False)
    print(f"✅ CSV exported successfully at: {out_path}")

def export_attendance_excel(db_path, out_path):
    """Export today's attendance as Excel with On Time / Late/Absent status."""
    today = date.today().isoformat()

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT token_no, name, date, time FROM attendance WHERE date=? ORDER BY time ASC",
        conn,
        params=(today,)
    )

    # Status for present students
    if not df.empty:
        df["Status"] = df["time"].apply(get_status)
    else:
        df["Status"] = []

    # Fetch absent students
    absent_query = """
        SELECT token_no, name FROM students
        WHERE token_no NOT IN (
            SELECT token_no FROM attendance WHERE date=?
        )
        ORDER BY name ASC
    """
    absent_students = pd.read_sql_query(absent_query, conn, params=(today,))
    conn.close()

    if not absent_students.empty:
        absent_students["date"] = today
        absent_students["time"] = "--:--:--"
        absent_students["Status"] = "Absent"

    # Combine present and absent DataFrames
    export_df = pd.concat([df, absent_students], ignore_index=True, sort=False)
    export_df = export_df[["token_no", "name", "date", "time", "Status"]]

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    export_df.to_excel(out_path, index=False)
    print(f"✅ Excel exported successfully at: {out_path}")
