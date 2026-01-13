import psutil
import requests
import subprocess
import threading
import time
from flask import Flask, render_template_string, request, redirect

# ------------------ CONFIG ------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"
APPROVE_PASSWORD = "admin123"

app = Flask(__name__)

latest_metrics = {}
latest_ai_response = ""
last_action_status = ""
last_action_output = ""

# ------------------ SYSTEM METRICS ------------------
def collect_metrics():
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

Analyze the system health.
Explain in simple words.
If there is an issue, suggest ONE SAFE action from this list only:
- check cpu load
- check memory usage
- check disk usage
- no action needed

Do NOT execute anything.
Do NOT suggest dangerous actions.

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
            timeout=60
        )
        return response.json().get("response", "No AI response")
    except Exception as e:
        return f"AI Error: {e}"

# ------------------ BACKGROUND LOOPS ------------------
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

# ------------------ AI → ACTION MAPPER ------------------
def decide_action(ai_text):
    text = ai_text.lower()

    if "check disk" in text:
        return "Checking disk usage", ["df", "-h"]

    if "check memory" in text:
        return "Checking memory usage", ["free", "-h"]

    if "check cpu" in text:
        return "Checking CPU load", ["uptime"]

    return "No action required", None

# ------------------ SAFE ACTION EXECUTION ------------------
def execute_action():
    global last_action_output

    action_name, command = decide_action(latest_ai_response)

    if not command:
        last_action_output = "AI suggested no executable action."
        return

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10
        )
        last_action_output = f"{action_name}\n\n{result.stdout}"
    except Exception as e:
        last_action_output = f"Action failed: {e}"

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
            background: linear-gradient(135deg, #FFDEE9, #B5FFFC);
        }
        .container { width: 1000px; margin: 20px auto; }
        h1 { text-align: center; font-size: 3em; }
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
        .sparkle { box-shadow: 0 0 15px 4px gold; }
        pre {
            background: #fff9c4;
            padding: 15px;
            border-radius: 15px;
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
<h1>AI Ops Linux Monitoring</h1>

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
<h2>AI Explanation & Suggestion</h2>
<pre>{{ ai }}</pre>
</div>

<div class="card">
<h2>⚙️ Approved Action Output</h2>
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

# ------------------ ROUTES ------------------
@app.route("/")
def dashboard():
    return render_template_string(
        HTML_TEMPLATE,
        metrics=latest_metrics,
        ai=latest_ai_response,
        status=last_action_status,
        action_output=last_action_output
    )

@app.route("/approve", methods=["POST"])
def approve():
    global last_action_status

    if request.form.get("password") == APPROVE_PASSWORD:
        execute_action()
        last_action_status = "Action approved and executed"
    else:
        last_action_status = "❌ Invalid password"

    return redirect("/")

# ------------------ START ------------------
if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=ai_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
