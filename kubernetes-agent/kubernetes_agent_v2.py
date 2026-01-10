# Kubernetes Agent v1.2 – Agentic AI with Local LLM (Ollama)
# Author: Arunvel Arunachalam 
# Purpose: Kubernetes troubleshooting using Rules + Local LLM + Safe Actions

import sys
import json
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from rich import print
from rich.table import Table
from rich.panel import Panel
from openai import OpenAI

# ============================================================
# CONFIGURATION
# ============================================================
MODE = "ADVISE"      # ADVISE | APPROVE | AUTO
LOG_LINES = 50
LLM_MODEL = "llama3.1:8b"  # Ollama local model

# ============================================================
# LLM CLIENT (LOCAL OLLAMA – OPENAI COMPATIBLE)
# ============================================================
llm_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # dummy key
)

# ============================================================
# KUBERNETES CLIENT SETUP
# ============================================================

def load_k8s():
    try:
        config.load_kube_config()
    except:
        config.load_incluster_config()
    return client.CoreV1Api(), client.AppsV1Api()

v1, apps_v1 = load_k8s()

# ============================================================
# DATA COLLECTORS
# ============================================================

def get_pod(namespace, pod):
    try:
        return v1.read_namespaced_pod(pod, namespace)
    except ApiException as e:
        if e.status == 404:
            print(f"[red]Pod '{pod}' not found in namespace '{namespace}'[/red]")
            sys.exit(1)
        raise


def get_events(namespace, pod):
    events = v1.list_namespaced_event(namespace)
    return [e.message for e in events.items if e.involved_object.name == pod]


def get_logs(namespace, pod):
    try:
        return v1.read_namespaced_pod_log(pod, namespace, tail_lines=LOG_LINES)
    except:
        return "No logs available"

# ============================================================
# RULE ENGINE (DETERMINISTIC – SRE LOGIC)
# ============================================================

def rule_engine(pod):
    status = pod.status
    cs = status.container_statuses

    if not cs:
        return status.phase

    c = cs[0]

    # Use restart history (very important)
    if c.restart_count and c.restart_count > 3:
        return "CrashLoopBackOff"

    if c.state.waiting:
        reason = c.state.waiting.reason
        if reason in ["CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"]:
            return reason
        if reason == "ContainerCreating":
            return "ContainerCreating"

    if c.state.terminated:
        if c.state.terminated.reason == "OOMKilled":
            return "OOMKilled"
        return "Error"

    return status.phase

# ============================================================
# LLM REASONING (LOCAL AI BRAIN)
# ============================================================

def llm_reasoning(context):
    prompt = f"""
You are a Senior Kubernetes SRE.

Pod: {context['pod']}
Namespace: {context['namespace']}
Detected Issue: {context['issue']}
Events: {context['events']}
Recent Logs:
{context['logs']}

Tasks:
1. Identify the most likely root cause
2. Suggest the SAFEST remediation
3. Decide if auto-remediation is safe (yes/no)

Return STRICT JSON only:
{{
  "root_cause": "...",
  "fix": "...",
  "auto_safe": "yes/no",
  "confidence": "0-100%"
}}
"""

    response = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    return json.loads(response.choices[0].message.content)

# ============================================================
# ACTION EXECUTOR (SAFE HANDS)
# ============================================================

def restart_pod(namespace, pod):
    v1.delete_namespaced_pod(pod, namespace)

# ============================================================
# MAIN AGENT LOGIC (OBSERVE → THINK → ACT)
# ============================================================

def diagnose(namespace, pod_name):
    pod = get_pod(namespace, pod_name)
    events = get_events(namespace, pod_name)
    logs = get_logs(namespace, pod_name)

    issue = rule_engine(pod)

    context = {
        "namespace": namespace,
        "pod": pod_name,
        "issue": issue,
        "events": events,
        "logs": logs
    }

    reasoning = llm_reasoning(context)

    # OUTPUT
    table = Table(title="Kubernetes Agent Diagnosis")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Pod", pod_name)
    table.add_row("Namespace", namespace)
    table.add_row("Detected Issue", issue)
    table.add_row("Root Cause", reasoning.get("root_cause"))
    table.add_row("Suggested Fix", reasoning.get("fix"))
    table.add_row("Confidence", reasoning.get("confidence"))

    print(table)

    # DECISION & ACTION
    if MODE == "AUTO" and reasoning.get("auto_safe") == "yes":
        restart_pod(namespace, pod_name)
        print(Panel("Pod restarted automatically", style="bold red"))

    if MODE == "APPROVE" and reasoning.get("auto_safe") == "yes":
        choice = input("Approve pod restart? (yes/no): ")
        if choice.lower() == "yes":
            restart_pod(namespace, pod_name)
            print(Panel("Pod restarted", style="bold red"))

# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python kubernetes_agent_v1.py <namespace> <pod-name>")
        sys.exit(1)

    ns = sys.argv[1]
    pod = sys.argv[2]
    diagnose(ns, pod)
