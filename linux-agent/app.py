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
    <style>
        body { font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 0; }
        .container { width: 900px; margin: 40px auto; }
        .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #2c3e50; }
        h2 { color: #34495e; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
        .metric { font-size: 18px; margin: 8px 0; }
        pre { background: #f0f0f0; padding: 15px; border-radius: 5px; white-space: pre-wrap; }
        .action-box { margin-top: 15px; }
        input[type=password] { padding: 8px; width: 200px; margin-right: 10px; }
        button { padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .status { margin-top: 10px; color: #c0392b; }
        .success { color: #27ae60; }
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Ops Linux Monitoring Dashboard</h1>

        <div class="card">
            <h2>System Metrics</h2>
            <div class="metric">CPU Usage: {{ metrics.cpu }}%</div>
            <div class="metric">Memory Usage: {{ metrics.memory }}%</div>
            <div class="metric">Disk Usage: {{ metrics.disk }}%</div>
        </div>

        <div class="card">
            <h2>AI Explanation and Suggestion</h2>
            <pre>{{ ai }}</pre>
        </div>

        <div class="card">
            <h2>Approve Action</h2>
            <form method="post" action="/approve">
                <input type="password" name="password" placeholder="Enter approval password" required>
                <button type="submit">Approve Action</button>
            </form>

            {% if status %}
                <div class="status {{ 'success' if success else '' }}">{{ status }}</div>
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
