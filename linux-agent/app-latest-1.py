import psutil
import requests
import subprocess
import threading
import time
import os
from flask import Flask, render_template, request, redirect

# ---------------- CONFIG ----------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"          # Reliable for strict output
APPROVE_PASSWORD = "admin123"

app = Flask(__name__)

latest_metrics = {}
latest_ai_response = ""
last_action_status = ""
last_action_output = ""

# ---------------- METRICS ----------------
def collect_metrics():
    load1, _, _ = os.getloadavg()
    cores = psutil.cpu_count()

    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu": round(cpu, 1),
        "load": round(load1, 2),
        "cores": cores,
        "memory": round(mem.percent, 1),
        "mem_free": round(mem.available / (1024 * 1024), 1),
        "disk": round(disk.percent, 1),
    }

# ---------------- SEVERITY ----------------
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
def decide_action(m):
    if m["memory"] > 85:
        return "free -h", "Memory pressure detected"
    if m["disk"] > 90:
        return "df -h", "Disk nearing capacity"
    if m["cpu"] > 75:
        return "ps aux --sort=-%cpu | head", "High CPU usage"
    if m["load"] > m["cores"]:
        return "uptime", "Load exceeds CPU cores"
    return "NONE", "System operating normally"

# ---------------- AI ----------------
def ask_ai(m):
    command, reason = decide_action(m)
    severity = calculate_severity(m)

    prompt = f"""
You are a Linux SRE decision engine.
RULES:
- EXACTLY 3 lines
- ONE short sentence per line
- NO paragraphs or markdown
FORMAT:
STATUS: <INFO|WARNING|MAJOR|CRITICAL>
REASON: <short sentence>
COMMAND: <exact command or NONE>
DATA:
CPU={m['cpu']}%
LOAD={m['load']}
CORES={m['cores']}
MEMORY={m['memory']}%
DISK={m['disk']}%
DECISION:
STATUS={severity}
COMMAND={command}
REASON={reason}
"""
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        return sanitize_ai(r.json().get("response", ""))
    except Exception:
        return "STATUS: ERROR\nREASON: AI unavailable\nCOMMAND: NONE"

def sanitize_ai(text):
    out = {"STATUS": None, "REASON": None, "COMMAND": None}
    for line in text.splitlines():
        line = line.strip()
        for key in out.keys():
            if line.upper().startswith(key):
                out[key] = line.split(":", 1)[1].strip()
    return f"STATUS: {out['STATUS'] or 'UNKNOWN'}\nREASON: {out['REASON'] or 'No AI response'}\nCOMMAND: {out['COMMAND'] or 'NONE'}"

def extract_command(text):
    for line in text.splitlines():
        if line.startswith("COMMAND:"):
            return line.split("COMMAND:")[1].strip()
    return "NONE"

# ---------------- THREADS ----------------
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
        time.sleep(4)

# ---------------- SAFE EXECUTION ----------------
ALLOWLIST = [
    "uptime",
    "free -h",
    "df -h",
    "ps aux --sort=-%cpu | head",
]

def execute_action():
    global last_action_output
    cmd = extract_command(latest_ai_response)
    if cmd == "NONE":
        last_action_output = "No action required."
        return
    if cmd not in ALLOWLIST:
        last_action_output = "Blocked unsafe command."
        return
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        last_action_output = f"$ {cmd}\n\n{r.stdout}"
    except Exception as e:
        last_action_output = str(e)

# ---------------- FAULT INJECTION ----------------
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
        severity=calculate_severity(latest_metrics) if latest_metrics else "INFO",
    )

@app.route("/approve", methods=["POST"])
def approve():
    global last_action_status
    if request.form.get("password") == APPROVE_PASSWORD:
        execute_action()
        last_action_status = "Approved and executed"
    else:
        last_action_status = "Invalid password"
    return redirect("/")

# ---------------- START ----------------
if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=ai_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
