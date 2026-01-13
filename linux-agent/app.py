import psutil
import requests
import subprocess
import threading
import time
from flask import Flask, render_template_string, request, redirect

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"
APPROVE_PASSWORD = "admin123"

app = Flask(__name__)

latest_metrics = {}
latest_ai_response = ""
last_action_status = ""

# ------------------ SYSTEM METRICS ------------------
def collect_metrics():
    # Accurate CPU usage across all cores
    cpu_percents = psutil.cpu_percent(interval=1, percpu=True)
    return {
        "cpu": round(sum(cpu_percents) / len(cpu_percents), 1),
        "memory": round(psutil.virtual_memory().percent, 1),
        "disk": round(psutil.disk_usage("/").percent, 1)
    }

# ------------------ AI ANALYSIS ------------------
def ask_ai(metrics):
    prompt = f"""
You are a Linux system administrator.

Explain the system health in simple words.
If there is an issue, suggest one safe action.
Do not execute anything.

CPU usage: {metrics['cpu']}%
Memory usage: {metrics['memory']}%
Disk usage: {metrics['disk']}%
"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=60  # AI timeout
        )
        return response.json().get("response", "No AI response")
    except Exception as e:
        return f"AI Error: {e}"

# ------------------ BACKGROUND MONITORS ------------------
def monitor_loop():
    global latest_metrics
    while True:
        latest_metrics = collect_metrics()
        time.sleep(2)  # update metrics frequently

def ai_loop():
    global latest_ai_response
    while True:
        if latest_metrics:
            latest_ai_response = ask_ai(latest_metrics)
        time.sleep(5)  # AI updates every 5 seconds

# ------------------ ACTION ------------------
def execute_action():
    # Safe demo action
    subprocess.run(["echo", "Approved action executed"], check=False)

# ------------------ FANCY UI ------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Ops Linux Monitor</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Roboto', sans-serif;
            background: linear-gradient(135deg, #FFDEE9 0%, #B5FFFC 100%);
            margin: 0;
            padding: 0;
        }
        .container {
            width: 1000px;
            margin: 20px auto;
        }
        h1 {
            text-align: center;
            color: #34495e;
            margin-bottom: 25px;
            font-size: 3em;
            text-shadow: 2px 2px 5px #7f8c8d;
        }
        .card {
            background: linear-gradient(145deg, #f9f9f9, #e0f7fa);
            padding: 25px;
            border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            margin-bottom: 25px;
            transition: transform 0.2s;
        }
        .card:hover {
            transform: scale(1.02);
        }
        h2 {
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 1.8em;
        }
        .metric {
            margin: 10px 0;
            font-size: 18px;
        }
        .bar-container {
            background: #e0e0e0;
            border-radius: 25px;
            overflow: hidden;
            margin-bottom: 15px;
            position: relative;
        }
        .bar {
            height: 30px;
            line-height: 30px;
            color: white;
            font-weight: bold;
            text-align: right;
            padding-right: 10px;
            border-radius: 25px;
            transition: width 1s ease-in-out, box-shadow 0.5s ease-in-out;
        }
        .cpu {background: linear-gradient(90deg, #FF6B6B, #FF4757);}
        .memory {background: linear-gradient(90deg, #FFA502, #FF7F50);}
        .disk {background: linear-gradient(90deg, #2ed573, #1eae63);}
        /* sparkle animation */
        .sparkle {
            animation: sparkle 1s infinite;
            box-shadow: 0 0 10px 3px #fff;
        }
        @keyframes sparkle {
            0% { box-shadow: 0 0 10px 2px rgba(255,255,255,0.6); }
            50% { box-shadow: 0 0 20px 6px rgba(255,255,255,1); }
            100% { box-shadow: 0 0 10px 2px rgba(255,255,255,0.6); }
        }
        pre {
            background: #fff9c4;
            padding: 15px;
            border-radius: 15px;
            white-space: pre-wrap;
            font-size: 16px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .action-box input[type=password] {
            padding: 12px;
            width: 250px;
            margin-right: 10px;
            border-radius: 10px;
            border: 2px solid #2c3e50;
        }
        .action-box button {
            padding: 12px 25px;
            background: linear-gradient(90deg, #6a11cb, #2575fc);
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-weight: bold;
            transition: 0.3s;
        }
        .action-box button:hover {
            background: linear-gradient(90deg, #2575fc, #6a11cb);
        }
        .status {
            margin-top: 15px;
            font-weight: bold;
            font-size: 1.2em;
        }
        .success {color: #27ae60;}
        .error {color: #c0392b;}
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Ops Linux Monitoring</h1>

        <div class="card">
            <h2>CPU Usage</h2>
            <div class="metric">{{ metrics.cpu }}%</div>
            <div class="bar-container">
                <div class="bar cpu {% if metrics.cpu > 70 %}sparkle{% endif %}" style="width: {{ metrics.cpu }}%">{{ metrics.cpu }}%</div>
            </div>

            <h2>Memory Usage</h2>
            <div class="metric">{{ metrics.memory }}%</div>
            <div class="bar-container">
                <div class="bar memory {% if metrics.memory > 70 %}sparkle{% endif %}" style="width: {{ metrics.memory }}%">{{ metrics.memory }}%</div>
            </div>

            <h2>Disk Usage</h2>
            <div class="metric">{{ metrics.disk }}%</div>
            <div class="bar-container">
                <div class="bar disk {% if metrics.disk > 70 %}sparkle{% endif %}" style="width: {{ metrics.disk }}%">{{ metrics.disk }}%</div>
            </div>
        </div>

        <div class="card">
            <h2>AI Explanation & Suggestion</h2>
            <pre>{{ ai }}</pre>
        </div>

        <div class="card action-box">
            <h2>Approve Action</h2>
            <form method="post" action="/approve">
                <input type="password" name="password" placeholder="Enter password" required>
                <button type="submit">Approve Action</button>
            </form>
            {% if status %}
                <div class="status {{ 'success' if success else 'error' }}">{{ status }}</div>
            {% endif %}
        </div>
    </div>
</body>
</html>

"""

@app.route("/")
def dashboard():
    return render_template_string(
        HTML_TEMPLATE,
        metrics=latest_metrics,
        ai=latest_ai_response,
        status=last_action_status,
        success="success" in last_action_status.lower()
    )

@app.route("/approve", methods=["POST"])
def approve():
    global last_action_status
    password = request.form.get("password")

    if password == APPROVE_PASSWORD:
        execute_action()
        last_action_status = "Action executed successfully"
    else:
        last_action_status = "Invalid password. Action not executed"

    return redirect("/")

# ------------------ START APPLICATION ------------------
if __name__ == "__main__":
    # Start background threads
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=ai_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
