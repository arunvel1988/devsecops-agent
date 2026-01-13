import psutil
import requests
import subprocess
import threading
import time
from flask import Flask, render_template_string, request, redirect

# ---------------- CONFIG ----------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"
APPROVE_PASSWORD = "admin123"

app = Flask(__name__)

latest_metrics = {}
latest_ai_response = ""
last_action_status = ""
last_action_output = ""

# ---------------- SYSTEM METRICS ----------------
def collect_metrics():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    return {
        "cpu": round(cpu, 1),
        "memory": round(memory, 1),
        "disk": round(disk, 1)
    }

# ---------------- AI ANALYSIS ----------------
def ask_ai(metrics):
    prompt = f"""
You are an AIOps assistant for Linux.

RULES:
- Keep the response SHORT.
- Use bullet points.
- End with exactly ONE action line.
- Allowed actions:
  ACTION: CHECK_CPU
  ACTION: CHECK_MEMORY
  ACTION: CHECK_DISK
  ACTION: NONE

FORMAT STRICTLY LIKE THIS:

SUMMARY:
- short point
- short point

ACTION: <ONE_ACTION_ONLY>

SYSTEM METRICS:
CPU: {metrics['cpu']}%
MEMORY: {metrics['memory']}%
DISK: {metrics['disk']}%
"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=60
        )
        return response.json().get("response", "No AI response")
    except Exception as e:
        return f"AI Error: {e}"

# ---------------- BACKGROUND THREADS ----------------
def monitor_loop():
    global latest_metrics
    while True:
        latest_metrics = collect_metrics()
        time.sleep(2)

def ai_loop():
    global latest_ai_response
    while True:
        if latest_metrics:
            latest_ai_response = ask_ai(latest_metrics)
        time.sleep(5)

# ---------------- AI → ACTION MAP ----------------
def decide_action(ai_text):
    text = ai_text.upper()

    if "ACTION: CHECK_DISK" in text:
        return "Disk usage checked", ["df", "-h"]

    if "ACTION: CHECK_MEMORY" in text:
        return "Memory usage checked", ["free", "-h"]

    if "ACTION: CHECK_CPU" in text:
        return "CPU load checked", ["top"]

    return "No action required (system healthy)", None

# ---------------- SAFE EXECUTION ----------------
def execute_action():
    global last_action_output

    message, command = decide_action(latest_ai_response)

    if not command:
        last_action_output = message
        return

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=10
        )
        last_action_output = f"{message}\n\n{result.stdout}"
    except Exception as e:
        last_action_output = f"Execution failed: {e}"

# ---------------- UI ----------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>AIOps Linux Monitor</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
<style>
body {
    font-family: Roboto;
    background: linear-gradient(135deg,#FFDEE9,#B5FFFC);
}
.container { width: 1000px; margin: 20px auto; }
.card {
    background: white;
    padding: 25px;
    border-radius: 20px;
    margin-bottom: 25px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
}
.bar-container { background: #ddd; border-radius: 25px; overflow: hidden; }
.bar {
    height: 30px; color: white; font-weight: bold;
    text-align: right; padding-right: 10px;
    transition: width 1s;
}
.cpu { background: linear-gradient(90deg,#ff6b6b,#ff4757); }
.memory { background: linear-gradient(90deg,#ffa502,#ff7f50); }
.disk { background: linear-gradient(90deg,#2ed573,#1eae63); }
.sparkle { box-shadow: 0 0 15px gold; }

pre {
    background: #fff9c4;
    padding: 15px;
    border-radius: 15px;
    height: 160px;
    overflow-y: auto;
    font-size: 15px;
}

button {
    padding: 12px 25px;
    border-radius: 12px;
    border: none;
    background: linear-gradient(90deg,#6a11cb,#2575fc);
    color: white;
    font-weight: bold;
    cursor: pointer;
}
input { padding: 12px; border-radius: 10px; }
</style>
</head>

<body>
<div class="container">
<h1 style="text-align:center;">AI Ops Linux Monitoring</h1>

<div class="card">
<h2>System Metrics</h2>

CPU: {{ metrics.cpu }}%
<div class="bar-container">
<div class="bar cpu {% if metrics.cpu > 70 %}sparkle{% endif %}" style="width:{{ metrics.cpu }}%">{{ metrics.cpu }}%</div>
</div>

Memory: {{ metrics.memory }}%
<div class="bar-container">
<div class="bar memory {% if metrics.memory > 70 %}sparkle{% endif %}" style="width:{{ metrics.memory }}%">{{ metrics.memory }}%</div>
</div>

Disk: {{ metrics.disk }}%
<div class="bar-container">
<div class="bar disk {% if metrics.disk > 70 %}sparkle{% endif %}" style="width:{{ metrics.disk }}%">{{ metrics.disk }}%</div>
</div>
</div>

<div class="card">
<h2>AI Analysis</h2>
<pre>{{ ai }}</pre>
</div>

<div class="card">
<h2>Approved Action Output</h2>
<pre>{{ action_output }}</pre>
</div>

<div class="card">
<h2>Approve Action</h2>
<form method="post" action="/approve">
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Approve</button>
</form>
<p>{{ status }}</p>
</div>

</div>
</body>
</html>
"""

# ---------------- ROUTES ----------------
@app.route("/")
def dashboard():
    return render_template_string(
        HTML_TEMPLATE,
        metrics=latest_metrics,
        ai=latest_ai_response,
        action_output=last_action_output,
        status=last_action_status
    )

@app.route("/approve", methods=["POST"])
def approve():
    global last_action_status

    if request.form.get("password") == APPROVE_PASSWORD:
        execute_action()
        last_action_status = "Action processed"
    else:
        last_action_status = "Invalid password"

    return redirect("/")

# ---------------- START ----------------
if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=ai_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
