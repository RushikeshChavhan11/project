import base64
from PIL import Image
from io import BytesIO
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout, GlobalAveragePooling2D
from tensorflow.keras.preprocessing.image import img_to_array, load_img
from sklearn.model_selection import train_test_split
import csv
import json
from datetime import datetime
import cv2
from tensorflow.keras.layers import BatchNormalization
from flask import Flask, render_template, request, jsonify, send_file
import matplotlib.pyplot as plt
from scipy.spatial.distance import cosine
import pickle
from tensorflow.keras.applications import MobileNet
from tensorflow.keras.preprocessing.image import ImageDataGenerator

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Database Configuration
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Rushi@011",
    database="attendance_system"
)
cursor = db.cursor()

# Define Directories
IMAGE_DIR = r'C:\Users\rushikesh chauhan\Desktop\MCA project final Year\New folder\static\images'
TRAINED_IMAGE_DIR = r'C:\Users\rushikesh chauhan\Desktop\MCA project final Year\New folder\static\trained_images'
MODEL_DIR = r"C:\Users\rushikesh chauhan\Desktop\MCA project final Year\New folder\models"
TRAINED_IMAGES_DIR = "static/trained_images"
MODEL_PATH = "models/face_recognition_model.h5"
EMBEDDINGS_PATH = "models/face_embeddings.pkl"

# Ensure directories exist
os.makedirs(TRAINED_IMAGES_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# Load or initialize embeddings dictionary
if os.path.exists(EMBEDDINGS_PATH):
    with open(EMBEDDINGS_PATH, "rb") as f:
        embeddings_dict = pickle.load(f)
else:
    embeddings_dict = {}

# Load or initialize model
if os.path.exists(MODEL_PATH):
    model = tf.keras.models.load_model(MODEL_PATH)
    print("✅ Model loaded successfully!")
else:
    print("❌ Model not found. A new model will be created.")

# Face Detection Model
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Convert grayscale image to 3 channels
def convert_to_3_channels(image):
    if len(image.shape) == 2:  # Grayscale image
        image = np.stack((image,) * 3, axis=-1)  # Duplicate grayscale to 3 channels
    return image

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'GET':
        return render_template('add_student.html')

    try:
        name = request.form.get('name', '')
        student_id = request.form.get('student_id', '')
        student_class = request.form.get('course_name', '')
        year = request.form.get('year', '')
        images_data = request.form.get('captured_images', '')

        if not all([name, student_id, student_class, year, images_data]):
            return jsonify({"status": "error", "message": "❌ All fields are required!"}), 400

        images = json.loads(images_data)

        # Ensure student-specific folder exists
        student_folder = os.path.join(IMAGE_DIR, student_id)
        os.makedirs(student_folder, exist_ok=True)

        # Insert student details
        cursor.execute("INSERT INTO students (student_id, name, course_name, year) VALUES (%s, %s, %s, %s)",
                       (student_id, name, student_class, year))
        db.commit()

        # Save images and insert paths into `student_images` table
        for idx, image_data in enumerate(images):
            image_bytes = base64.b64decode(image_data.split(',')[1])
            image_path = os.path.join(student_folder, f"{idx + 1}.jpg")
            with open(image_path, "wb") as f:
                f.write(image_bytes)

            cursor.execute("INSERT INTO student_images (student_id, image_path) VALUES (%s, %s)", (student_id, image_path))
        db.commit()

        return jsonify({"status": "success", "message": "✅ Student added successfully!"})

    except Exception as e:
        return jsonify({"status": "error", "message": f"⚠ Error: {str(e)}"}), 500

@app.route('/train_images', methods=['GET'])
def train_images_page():
    return render_template('train_images.html')

@app.route('/train_images', methods=['POST'])
def train_images():
    print("🔹 Training Images API called!")

    images, labels = [], []
    label_dict = {}
    error_images = {}

    student_folders = os.listdir(IMAGE_DIR)

    if not student_folders:
        return jsonify({"status": "error", "message": "❌ No student images found!"})

    label_counter = 0

    base_model = MobileNet(weights='imagenet', include_top=False, input_shape=(100, 100, 3))
    base_model.trainable = False

    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(512, activation='relu')(x)
    x = Dropout(0.5)(x)
    predictions = Dense(len(student_folders), activation='softmax')(x)

    model = Model(inputs=base_model.input, outputs=predictions)
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

    embedding_model = Model(inputs=model.input, outputs=model.layers[-2].output)

    new_embeddings_dict = {}

    for student_id in student_folders:
        student_path = os.path.join(IMAGE_DIR, student_id)

        if not os.path.isdir(student_path):
            continue

        student_images = os.listdir(student_path)
        student_embeddings = []

        for filename in student_images:
            image_path = os.path.join(student_path, filename)

            try:
                img = cv2.imread(image_path)

                if img is None:
                    error_images[image_path] = "Image could not be loaded"
                    continue

                img = cv2.resize(img, (100, 100)) / 255.0

                embedding = embedding_model.predict(np.expand_dims(img, axis=0))
                student_embeddings.append(embedding)

                trained_image_path = os.path.join(TRAINED_IMAGE_DIR, f"{student_id}_{filename}")
                cv2.imwrite(trained_image_path, (img * 255).astype(np.uint8))

            except Exception as e:
                error_images[image_path] = str(e)

        if student_embeddings:
            new_embeddings_dict[student_id] = np.mean(student_embeddings, axis=0)

        label_counter += 1

    with open(EMBEDDINGS_PATH, "wb") as f:
        pickle.dump(new_embeddings_dict, f)

    model.save(MODEL_PATH)
    print(f"✅ Training completed! Model saved at: {MODEL_PATH}")

    return jsonify({
        "status": "success",
        "message": "✅ Training completed successfully!",
        "trained_students": len(new_embeddings_dict),
        "errors": error_images
    })


@app.route('/real_time_attendance')
def real_time_attendance():
    return render_template('real_time_attendance.html')

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    try:
        data = request.get_json()
        image_data = data.get('captured_image', '')
        subject = data.get('subject_name', 'Unknown Subject')

        if not image_data:
            return jsonify({"status": "error", "message": "❌ No image received!"}), 400

        image_bytes = base64.b64decode(image_data.split(',')[1])
        image_np = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({"status": "error", "message": "❌ Failed to decode image!"}), 400

        frame = cv2.resize(frame, (100, 100)) / 255.0

        embedding_model = Model(inputs=model.input, outputs=model.layers[-2].output)
        captured_embedding = embedding_model.predict(np.expand_dims(frame, axis=0))

        best_match = None
        best_similarity = 0.0

        for student_id, saved_embedding in embeddings_dict.items():
            similarity = 1 - cosine(captured_embedding.flatten(), saved_embedding.flatten())

            accuracy_percentage = round(similarity * 100, 2)
            print(f"🔹 {student_id} -> Accuracy: {accuracy_percentage}%")

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = student_id

        SIMILARITY_THRESHOLD = 0.70  # Adjust as needed
        

        if best_match and best_similarity >= SIMILARITY_THRESHOLD:
            cursor.execute("SELECT name, course_name FROM students WHERE student_id = %s", (best_match,))
            student_result = cursor.fetchone()

            if student_result:
                name, course_name = student_result

                cursor.execute("""
                    SELECT id FROM attendance 
                    WHERE student_id = %s AND subject = %s AND DATE(date) = CURDATE()
                """, (best_match, subject))
                existing_record = cursor.fetchone()

                if existing_record:
                    return jsonify({"status": "warning", "message": f"⚠ Attendance already marked for {name} today."})

                query = """
                    INSERT INTO attendance (student_id, name, course_name, subject, date, status)
                    VALUES (%s, %s, %s, %s, NOW(), 'Present')
                """
                cursor.execute(query, (best_match, name, course_name, subject))
                db.commit()

                return jsonify({"status": "success", "message": f"✅ Attendance marked for {name}!"})

        return jsonify({"status": "error", "message": "❌ Face not recognized!"}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": f"⚠ Error: {str(e)}"}), 500


@app.route('/capture_attendance')
def capture_attendance():
    subject = request.args.get('subject', 'Unknown Subject')
    return render_template('capture_attendance.html', subject=subject)

@app.route('/generate_reports')
def generate_reports():
    return render_template('generate_reports.html')

@app.route('/get_attendance', methods=['GET'])
def get_attendance():
    student_input = request.args.get('student_id', '').strip()
    year_of_study = request.args.get('year', '').strip()
    subject = request.args.get('subject', '').strip()
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()

    query = """
    SELECT a.student_id, s.name, COALESCE(s.course_name, 'Unknown') AS course_name, 
           s.year, a.subject, DATE(a.date), a.status 
    FROM attendance a 
    LEFT JOIN students s ON a.student_id = s.student_id
    WHERE 1=1
    """
    values = []

    if student_input:
        query += " AND (a.student_id = %s OR s.name LIKE %s)"
        values.append(student_input)
        values.append(f"%{student_input}%")

    if year_of_study:
        query += " AND s.year = %s"
        values.append(year_of_study)

    if subject:
        query += " AND a.subject = %s"
        values.append(subject)

    if from_date and to_date:
        query += " AND DATE(a.date) BETWEEN %s AND %s"
        values.append(from_date)
        values.append(to_date)
    elif from_date:
        query += " AND DATE(a.date) >= %s"
        values.append(from_date)
    elif to_date:
        query += " AND DATE(a.date) <= %s"
        values.append(to_date)

    query += " ORDER BY a.date DESC"

    cursor.execute(query, values)
    results = cursor.fetchall()

    attendance_data = [
        {
            "student_id": row[0],
            "name": row[1],
            "course_name": row[2],
            "year": row[3],
            "subject": row[4],
            "date": row[5].strftime('%Y-%m-%d'),
            "status": row[6]
        }
        for row in results
    ]

    return jsonify(attendance_data)

@app.route('/download_attendance', methods=['GET'])
def download_attendance():
    subject = request.args.get('subject', '').strip()

    query = "SELECT student_id, name, subject, DATE(date), TIME(date), status FROM attendance WHERE 1=1"
    values = []

    if subject:
        query += " AND subject = %s"
        values.append(subject)

    query += " ORDER BY DATE(date) ASC"

    cursor.execute(query, values)
    results = cursor.fetchall()

    if not results:
        return jsonify({"status": "error", "message": "No attendance records found."}), 404

    file_path = "attendance_report.csv"
    with open(file_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Student ID", "Name", "Subject", "Date", "Time", "Status"])
        writer.writerows(results)

    return send_file(file_path, as_attachment=True)

@app.route('/graph')
def graph():
    return render_template('graph.html')

@app.route('/get_subjects', methods=['GET'])
def get_subjects():
    cursor.execute("SELECT DISTINCT subject FROM attendance")
    subjects = [row[0] for row in cursor.fetchall()]
    return jsonify(subjects)

# ✅ API to fetch attendance data for the graph
import matplotlib.pyplot as plt
import io
import base64
from flask import Response, request

@app.route('/get_courses', methods=['GET'])
def get_courses():
    query = "SELECT DISTINCT course_name FROM students"
    cursor.execute(query)
    courses = [row[0] for row in cursor.fetchall()]
    return jsonify(courses)


import matplotlib.pyplot as plt
import base64
from io import BytesIO

@app.route('/get_attendance_graph', methods=['GET'])
def get_attendance_graph():
    try:
        subject = request.args.get('subject', '').strip()
        year = request.args.get('year', '').strip()
        course_name = request.args.get('course_name', '').strip()
        total_students = request.args.get('total_students', '').strip()
        from_date = request.args.get('from_date', '').strip()
        to_date = request.args.get('to_date', '').strip()

        if not subject or not total_students:
            return jsonify({"status": "error", "message": "❌ Please select a subject and enter the total number of students."})

        total_students = int(total_students)  # Convert total_students to integer

        # ✅ Prevent Matplotlib GUI Warning
        plt.switch_backend('Agg')

        # ✅ SQL Query to Fetch Attendance Data
        query = """
        SELECT DATE(a.date) AS attendance_date, COUNT(DISTINCT a.student_id) AS present_count
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.status = 'Present' AND a.subject = %s
        """
        values = [subject]

        if year:
            query += " AND s.year = %s"
            values.append(year)
        if course_name:
            query += " AND s.course_name = %s"
            values.append(course_name)
        if from_date and to_date:
            query += " AND DATE(a.date) BETWEEN %s AND %s"
            values.append(from_date)
            values.append(to_date)

        query += " GROUP BY DATE(a.date) ORDER BY DATE(a.date) ASC"

        cursor.execute(query, values)
        results = cursor.fetchall()

        # ✅ Extract Data for Graph
        dates = [row[0].strftime('%Y-%m-%d') for row in results]
        present_counts = [row[1] for row in results]

        if not dates:
            return jsonify({"status": "error", "message": "❌ No attendance data found for the selected filters."})

        # ✅ Create Bar Graph
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(dates, present_counts, color='blue', label="Students Present")
        ax.axhline(y=total_students, color='red', linestyle='--', label=f"Total Students: {total_students}")  # Reference Line for Total
        ax.set_title(f"Attendance Analysis for {subject}")
        ax.set_xlabel("Date")
        ax.set_ylabel("No. of Students Present")
        ax.legend()
        ax.grid(axis='y')

        # ✅ Save Graph as Image (Base64 Encoding)
        image_stream = BytesIO()
        plt.savefig(image_stream, format='png')
        plt.close(fig)
        image_stream.seek(0)
        graph_base64 = base64.b64encode(image_stream.read()).decode()

        return jsonify({"status": "success", "bar_chart": graph_base64})

    except Exception as e:
        return jsonify({"status": "error", "message": f"⚠ Error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)
