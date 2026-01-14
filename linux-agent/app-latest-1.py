import psutil
import requests
import subprocess
import threading
import time
import os
from flask import Flask, render_template, request, redirect

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
    load1, load5, load15 = os.getloadavg()
    cpu_cores = psutil.cpu_count()

    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_idle = 100 - cpu_percent

    cpu_state = "OK"
    if cpu_percent > 70 or load1 > cpu_cores:
        cpu_state = "WARNING"
    if cpu_percent > 85 and load1 > cpu_cores:
        cpu_state = "CRITICAL"

    return {
        "cpu": round(cpu_percent, 1),
        "cpu_idle": round(cpu_idle, 1),
        "load": round(load1, 2),
        "cores": cpu_cores,
        "cpu_state": cpu_state,
        "memory": round(psutil.virtual_memory().percent, 1),
        "disk": round(psutil.disk_usage("/").percent, 1)
    }

# ---------------- AI ANALYSIS ----------------
def ask_ai(m):
    prompt = f"""
You are a senior Linux SRE and AIOps assistant.

GOAL:
- Determine whether CPU pressure exists
- Explain findings clearly for students
- Suggest ONE read-only diagnostic command if required
- If system is healthy say COMMAND: NONE

RULES:
- Use evidence (CPU %, load average, core count)
- Be concise and accurate
- Suggest only one command

FORMAT STRICTLY:

SUMMARY:
- ...

EVIDENCE:
- ...

SUGGESTED ACTION:
COMMAND: <exact command or NONE>
REASON: <why>

SYSTEM DATA:
CPU Usage: {m['cpu']}%
CPU Idle: {m['cpu_idle']}%
Load Average (1m): {m['load']}
CPU Cores: {m['cores']}
Memory Usage: {m['memory']}%
Disk Usage: {m['disk']}%
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

def extract_command(ai_text):
    for line in ai_text.splitlines():
        if line.strip().startswith("COMMAND:"):
            return line.replace("COMMAND:", "").strip()
    return "NONE"

# ---------------- BACKGROUND THREADS ----------------
def monitor_loop():
    global latest_metrics
    while True:
        latest_metrics = collect_metrics()
        time.sleep(3)

def ai_loop():
    global latest_ai_response
    while True:
        if latest_metrics:
            latest_ai_response = ask_ai(latest_metrics)
        time.sleep(6)

# ---------------- SAFE EXECUTION ----------------
READ_ONLY_ALLOWLIST = [
    "uptime",
    "top",
    "vmstat",
    "ps aux --sort=-%cpu | head",
    "free -h",
    "df -h"
]

def execute_action():
    global last_action_output

    command = extract_command(latest_ai_response)

    if command == "NONE":
        last_action_output = "System is healthy. No action required."
        return

    if command not in READ_ONLY_ALLOWLIST:
        last_action_output = "Blocked: command not in read-only allowlist."
        return

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        last_action_output = f"$ {command}\n\n{result.stdout}"
    except Exception as e:
        last_action_output = f"Execution failed: {e}"

# ---------------- ROUTES ----------------
@app.route("/")
def dashboard():
    return render_template(
        "index.html",
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
        last_action_status = "Approved and executed safely."
    else:
        last_action_status = "Invalid password."

    return redirect("/")

# ---------------- START ----------------
if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=ai_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
