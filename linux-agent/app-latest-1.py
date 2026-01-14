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

# ---------------- METRICS COLLECTION ----------------
def collect_metrics():
    load1, load5, load15 = os.getloadavg()
    cores = psutil.cpu_count()

    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu": round(cpu, 1),
        "load": round(load1, 2),
        "cores": cores,
        "memory": round(mem.percent, 1),
        "mem_available": round(mem.available / (1024 * 1024), 1),
        "disk": round(disk.percent, 1),
    }

# ---------------- INCIDENT SEVERITY ----------------
def calculate_severity(m):
    score = 0
    if m["cpu"] > 85:
        score += 3
    if m["load"] > m["cores"]:
        score += 2
    if m["memory"] > 85:
        score += 3
    if m["disk"] > 90:
        score += 3

    if score >= 7:
        return "CRITICAL"
    if score >= 5:
        return "MAJOR"
    if score >= 3:
        return "WARNING"
    return "INFO"

# ---------------- DECISION ENGINE ----------------
def cpu_decision(m):
    if m["load"] > m["cores"]:
        return "uptime", "Load average exceeds CPU core count."
    if m["cpu"] > 70:
        return "ps aux --sort=-%cpu | head", "High CPU usage detected."
    return None

def memory_decision(m):
    if m["memory"] > 85:
        return "free -h", "Critical memory usage."
    if m["memory"] > 75:
        return "vmstat", "Memory pressure detected."
    return None

def disk_decision(m):
    if m["disk"] > 90:
        return "df -h", "Disk usage above safe threshold."
    return None

def decide_action(m):
    for fn in [cpu_decision, memory_decision, disk_decision]:
        result = fn(m)
        if result:
            return result
    return "NONE", "System operating within normal limits."

# ---------------- AI ANALYSIS ----------------
def ask_ai(m):
    command, reason = decide_action(m)
    severity = calculate_severity(m)

    prompt = f"""
You are a senior Linux Site Reliability Engineer.

Explain the situation clearly for students.

SEVERITY: {severity}

SYSTEM METRICS:
- CPU Usage: {m['cpu']}%
- Load Average: {m['load']}
- CPU Cores: {m['cores']}
- Memory Usage: {m['memory']}%
- Available Memory: {m['mem_available']} MB
- Disk Usage: {m['disk']}%

DECISION:
COMMAND: {command}
REASON: {reason}

Explain:
- Why this is happening
- What risk it poses
- What the command helps observe
"""

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        return r.json().get("response", "No AI response")
    except Exception as e:
        return f"AI error: {e}"

def extract_command(text):
    for line in text.splitlines():
        if line.strip().startswith("COMMAND:"):
            return line.split("COMMAND:")[1].strip()
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
    "df -h",
]

def execute_action():
    global last_action_output

    cmd = extract_command(latest_ai_response)

    if cmd == "NONE":
        last_action_output = "No action required."
        return

    if cmd not in READ_ONLY_ALLOWLIST:
        last_action_output = "Blocked unsafe command."
        return

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        last_action_output = f"$ {cmd}\n\n{result.stdout}"
    except Exception as e:
        last_action_output = str(e)

# ---------------- FAULT INJECTION (LAB MODE) ----------------
@app.route("/inject/cpu")
def inject_cpu():
    subprocess.Popen("yes > /dev/null", shell=True)
    return redirect("/")

@app.route("/inject/memory")
def inject_memory():
    subprocess.Popen("stress --vm 1 --vm-bytes 512M", shell=True)
    return redirect("/")

@app.route("/inject/disk")
def inject_disk():
    subprocess.Popen("dd if=/dev/zero of=/tmp/fill bs=1M count=1024", shell=True)
    return redirect("/")

# ---------------- ROUTES ----------------
@app.route("/")
def dashboard():
    return render_template(
        "index.html",
        metrics=latest_metrics,
        ai=latest_ai_response,
        output=last_action_output,
        status=last_action_status,
        severity=calculate_severity(latest_metrics) if latest_metrics else "N/A",
    )

@app.route("/approve", methods=["POST"])
def approve():
    global last_action_status
    if request.form.get("password") == APPROVE_PASSWORD:
        execute_action()
        last_action_status = "Approved and executed."
    else:
        last_action_status = "Invalid password."
    return redirect("/")

# ---------------- START ----------------
if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=ai_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
