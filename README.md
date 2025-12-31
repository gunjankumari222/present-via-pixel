# Present via Pixel 🎯  
Face Recognition Based Attendance System

---

## 📌 Project Overview

Present via Pixel is a web-based Face Recognition Attendance System developed
to automate the traditional attendance process in educational institutions.
The system captures live video through a webcam, detects faces, and marks
attendance automatically when a registered face is recognized.

This project eliminates manual roll calls, reduces proxy attendance, and
provides a fast, contactless, and reliable attendance solution.  
It is developed as a **Diploma Final Year Project** using Python and Flask.

---

## 🎯 Aim of the Project

The main aim of this project is to develop an automated attendance system that:
- Accurately identifies students using facial recognition
- Records attendance in real time
- Eliminates proxy attendance
- Saves classroom time
- Maintains digital attendance records

---

## 🎯 Objectives

- Automate the attendance process
- Prevent proxy attendance
- Reduce manual errors
- Store attendance records digitally
- Provide role-based dashboards
- Make attendance tracking fast and secure

---

## ❌ Drawbacks of Existing System

- Manual attendance is time-consuming
- High chances of proxy attendance
- Human errors in record keeping
- Paper-based registers are difficult to manage
- No centralized digital attendance history

---

## ✅ Advantages of Proposed System

- Fully automated attendance
- Face-based identification
- Contactless and hygienic
- High accuracy
- Secure and reliable
- Easy to use web interface
- Reduces workload for teachers

---

## 🧠 How the System Works

1. Admin registers students with their face image
2. Facial features are encoded and stored
3. During attendance:
   - Webcam captures live video
   - Face is detected and matched with stored encodings
   - If matched, attendance is marked automatically
4. Attendance is stored with date and time

---

## 👥 User Roles

### 👩‍💼 Admin
- Login to admin dashboard
- Register new students
- Manage student records
- View attendance reports

### 👨‍🏫 Teacher
- View student attendance
- Monitor attendance records

### 👩‍🎓 Student
- Login to student dashboard
- Mark attendance using face recognition
- View own attendance details

---

## 🛠️ Technologies Used

### Backend
- Python 3.9
- Flask Framework

### Frontend
- HTML
- CSS
- JavaScript

### Libraries
- OpenCV
- face_recognition
- NumPy
- SQLite

---

## 📁 Project Folder Structure
present_via_pixel/
│
├── app.py # Main Flask application
├── requirements.txt # Python dependencies
│
├── modules/ # Backend logic
│ ├── face_registration.py
│ ├── attendance_capture.py
│ ├── student_management.py
│ └── export_data.py
│
├── templates/ # HTML pages
│ ├── index.html
│ ├── login.html
│ ├── admin_dashboard.html
│ ├── student_dashboard.html
│ └── view_attendance.html
│
├── static/ # CSS, JS, images
│ ├── style.css
│ ├── toast.js
│ └── logo.png

## ▶️ How to Run the Project

### Step 1: Install Python
Ensure Python 3.9 is installed on your system.

### Step 2: Install Required Libraries
```bash
pip install -r requirements.txt

### Step 3: Run the Application
python app.py

### Step 4: Open Browser
Visit:
http://127.0.0.1:5000


## 📄 Project Report

The complete project report (PDF) is available here:  
[Click to view Project Report](documentation/Project_Report.pdf)
