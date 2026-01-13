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

REFRESH_METRICS_SEC = 2
REFRESH_AI_SEC = 5

SAFE_COMMANDS = ["df", "free", "top", "ps", "uptime"]

app = Flask(__name__)

latest_metrics = {}
latest_ai_response = ""
latest_ai_command = "NONE"
last_action_output = ""
last_action_status = ""

# ---------------- SYSTEM METRICS ----------------
def collect_metrics():
    return {
        "cpu": round(psutil.cpu_percent(interval=1), 1),
        "memory": round(psutil.virtual_memory().percent, 1),
        "disk": round(psutil.disk_usage("/").percent, 1),
    }

def monitor_loop():
    global latest_metrics
    while True:
        latest_metrics = collect_metrics()
        time.sleep(REFRESH_METRICS_SEC)

# ---------------- AI ANALYSIS ----------------
def ask_ai(metrics):
    prompt = f"""
You are an AIOps assistant for Linux.

GOAL:
- Analyze system metrics
- Suggest ONE useful diagnostic command
- If system is healthy, suggest NONE

STRICT RULES:
- Max 2 bullet points
- NO explanations
- ONE command only
- Allowed commands only:
  df -h
  free -h
  top -b -n 1
  ps aux --sort=-%cpu | head
  uptime

FORMAT (MANDATORY):

SUMMARY:
- short point
- short point

COMMAND:
<exact command OR NONE>

SYSTEM METRICS:
CPU={metrics['cpu']}%
MEMORY={metrics['memory']}%
DISK={metrics['disk']}%
"""
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=60
        )
        return r.json().get("response", "")
    except Exception as e:
        return f"SUMMARY:\n- AI error\n\nCOMMAND:\nNONE"

def extract_command(ai_text):
    for line in ai_text.splitlines():
        if line.strip().startswith("COMMAND:"):
            return line.replace("COMMAND:", "").strip()
    return "NONE"

def ai_loop():
    global latest_ai_response, latest_ai_command
    while True:
        if latest_metrics:
            latest_ai_response = ask_ai(latest_metrics)
            latest_ai_command = extract_command(latest_ai_response)
        time.sleep(REFRESH_AI_SEC)

# ---------------- SAFETY ----------------
def is_command_safe(cmd):
    if cmd == "NONE":
        return False
    base = cmd.split()[0]
    return base in SAFE_COMMANDS

def execute_action():
    global last_action_output

    cmd = latest_ai_command

    if cmd == "NONE":
        last_action_output = "No action required. System healthy."
        return

    if not is_command_safe(cmd):
        last_action_output = "Blocked unsafe AI command."
        return

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        last_action_output = f"$ {cmd}\n\n{result.stdout}"
    except Exception as e:
        last_action_output = f"Execution failed: {e}"

# ---------------- UI ----------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>AIOps Linux Monitor</title>
<style>
body { font-family: Arial; background: #eef2f7; }
.container { width: 1000px; margin: auto; }
.card {
    background: white;
    padding: 20px;
    border-radius: 12px;
    margin: 20px 0;
}
pre {
    background: #111;
    color: #0f0;
    padding: 15px;
    border-radius: 10px;
    height: 180px;
    overflow-y: auto;
}
button {
    padding: 10px 20px;
    border-radius: 8px;
    background: #2563eb;
    color: white;
    border: none;
}
</style>
</head>

<body>
<div class="container">
<h1>AIOps Linux Monitoring</h1>

<div class="card">
<h3>System Metrics</h3>
CPU: {{ metrics.cpu }}%<br>
Memory: {{ metrics.memory }}%<br>
Disk: {{ metrics.disk }}%
</div>

<div class="card">
<h3>AI Recommendation</h3>
<pre>{{ ai }}</pre>
</div>

<div class="card">
<h3>Executed Output</h3>
<pre>{{ output }}</pre>
</div>

<div class="card">
<h3>Approve AI Action</h3>
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
        output=last_action_output,
        status=last_action_status
    )

@app.route("/approve", methods=["POST"])
def approve():
    global last_action_status
    if request.form.get("password") == APPROVE_PASSWORD:
        execute_action()
        last_action_status = "Action approved & executed"
    else:
        last_action_status = "Invalid password"
    return redirect("/")

# ---------------- START ----------------
if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=ai_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
