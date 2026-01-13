import psutil
import requests
import subprocess
import threading
import time
from flask import Flask, render_template_string, request, redirect

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"

app = Flask(__name__)

latest_metrics = {}
latest_ai_response = ""

# ------------------ SYSTEM METRICS ------------------
def collect_metrics():
    return {
        "cpu": psutil.cpu_percent(interval=1),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent
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
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=30
    )
    return response.json()["response"]

# ------------------ BACKGROUND MONITOR ------------------
def monitor_loop():
    global latest_metrics, latest_ai_response
    while True:
        latest_metrics = collect_metrics()
        latest_ai_response = ask_ai(latest_metrics)
        time.sleep(10)

# ------------------ ACTION (SAFE DEMO) ------------------
def execute_action():
    # Safe demo action
    subprocess.run(["echo", "Action approved by user"], check=False)

# ------------------ WEB UI ------------------
HTML_TEMPLATE = """
<html>
<head>
    <title>AI Ops Linux Monitor</title>
</head>
<body>
    <h1>AI Ops Linux Monitoring Dashboard</h1>

    <h2>System Metrics</h2>
    <ul>
        <li>CPU Usage: {{ metrics.cpu }}%</li>
        <li>Memory Usage: {{ metrics.memory }}%</li>
        <li>Disk Usage: {{ metrics.disk }}%</li>
    </ul>

    <h2>AI Explanation and Suggestion</h2>
    <pre>{{ ai }}</pre>

    <h2>Action</h2>
    <form method="post" action="/approve">
        <button type="submit">Approve Suggested Action</button>
    </form>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(
        HTML_TEMPLATE,
        metrics=latest_metrics,
        ai=latest_ai_response
    )

@app.route("/approve", methods=["POST"])
def approve():
    execute_action()
    return redirect("/")

# ------------------ START APPLICATION ------------------
if __name__ == "__main__":
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)
