import pandas as pd
from flask import Flask, request, jsonify
from sklearn.cluster import KMeans
import os
from dotenv import load_dotenv
import mysql.connector

# .env dosyasını yükle
load_dotenv()

# 📌 MySQL Bağlantısı (env'den okuyoruz)
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "sql7.freesqldatabase.com"),
    user=os.getenv("DB_USER", "sql7773114"),
    password=os.getenv("DB_PASS", "U15bN418Bxl"),
    database=os.getenv("DB_NAME", "sql7773114")
)

# 1️⃣ Verileri MySQL'den oku
df = pd.read_sql("SELECT * FROM user_study_sessions", conn)
df['date'] = pd.to_datetime(df['date'])

# 2️⃣ Kullanıcı bazında ortalamaları hesapla
user_stats = df.groupby("user_id").agg(
    avg_session_duration=("session_duration", "mean"),
    avg_break_duration=("break_duration", "mean"),
    avg_productivity_score=("productivity_score", "mean"),
    avg_focus_level=("focus_level", "mean"),
    total_tasks_completed=("task_completed", "sum")
).reset_index()

# 3️⃣ Kullanıcıları K-Means ile gruplandır
def perform_clustering():
    features = user_stats[[
        "avg_session_duration", "avg_break_duration",
        "avg_productivity_score", "avg_focus_level",
        "total_tasks_completed"
    ]]
    kmeans = KMeans(n_clusters=3, random_state=42)
    user_stats["cluster"] = kmeans.fit_predict(features)

perform_clustering()

# 4️⃣ Kişiselleştirilmiş öneri üretme
def generate_recommendation(user_id):
    user_data = user_stats[user_stats["user_id"] == user_id]
    if user_data.empty:
        return "No data available for this user."
    user_data = user_data.iloc[0]
    cluster = user_data["cluster"]
    recommendations = []

    if cluster == 0:
        recommendations.append("Your overall performance is low; consider reducing session duration and increasing breaks.")
    elif cluster == 1:
        recommendations.append("Your performance is average; try adjusting your routine to boost productivity.")
    elif cluster == 2:
        recommendations.append("Excellent performance! Maintain your current routine and consistency.")

    if user_data["avg_session_duration"] > 60:
        recommendations.append("Your work sessions are long, try shorter Pomodoro cycles.")
    else:
        recommendations.append("Your work session duration is optimal.")

    if user_data["avg_break_duration"] < 5:
        recommendations.append("Consider extending your break duration to improve focus.")
    else:
        recommendations.append("Your break durations are well balanced.")

    if user_data["avg_productivity_score"] < 3:
        recommendations.append("Your productivity seems low; experiment with new techniques.")
    else:
        recommendations.append("Your productivity scores are good.")

    if user_data["avg_focus_level"] < 6:
        recommendations.append("Your focus level is below average; consider concentration improvement techniques.")
    else:
        recommendations.append("Your focus level is impressive!")

    return {
        "user_id": user_id,
        "study_report": recommendations,
        "cluster": int(cluster)
    }

# 5️⃣ Haftalık ilerleme verisi hesaplama
def get_weekly_progress(user_id):
    base_progress = {"M": 0.0, "T": 0.0, "W": 0.0, "T2": 0.0, "F": 0.0, "S": 0.0, "S2": 0.0}
    user_data = df[df["user_id"] == user_id]
    if user_data.empty:
        return base_progress

    weekly_progress = user_data.groupby(user_data["date"].dt.strftime('%A'))["session_duration"].mean().to_dict()
    day_map = {"Monday": "M", "Tuesday": "T", "Wednesday": "W", "Thursday": "T2", "Friday": "F", "Saturday": "S", "Sunday": "S2"}
    
    for day, duration in weekly_progress.items():
        key = day_map.get(day, day)
        base_progress[key] = round(duration / 90, 2)

    return base_progress

# 6️⃣ Flask API Tanımla
app = Flask(__name__)

@app.route('/stats', methods=['GET'])
def stats():
    try:
        user_id = int(request.args.get('user_id'))
    except:
        return jsonify({"error": "Please provide a valid user_id"}), 400

    report = generate_recommendation(user_id)
    weekly_progress = get_weekly_progress(user_id)
    total_sessions = df[df["user_id"] == user_id].shape[0]
    user_data = user_stats[user_stats["user_id"] == user_id].iloc[0]
    avg_focus = user_data["avg_focus_level"]
    focus_rate_calculated = f"{round(avg_focus * 10)}%"
    latest_data = df[df["user_id"] == user_id].sort_values("date", ascending=False).iloc[0]

    return jsonify({
        "user_id": user_id,
        "today_focus_time": f"{latest_data['session_duration']} min",
        "completed_pomodoros": str(total_sessions),
        "focus_rate": focus_rate_calculated,
        "weekly_progress": weekly_progress,
        "study_report": report["study_report"],
        "avg_session_duration": round(user_data["avg_session_duration"], 2),
        "avg_break_duration": round(user_data["avg_break_duration"], 2),
        "avg_productivity_score": round(user_data["avg_productivity_score"], 2),
        "avg_focus_level": round(user_data["avg_focus_level"], 2),
        "total_tasks_completed": int(user_data["total_tasks_completed"]),
    })

@app.route('/studyReport', methods=['GET'])
def study_report_endpoint():
    try:
        user_id = int(request.args.get('user_id'))
    except:
        return jsonify({"error": "Please provide a valid user_id"}), 400

    report = generate_recommendation(user_id)
    return jsonify(report)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

