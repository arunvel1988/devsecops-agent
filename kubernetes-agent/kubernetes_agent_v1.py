# Kubernetes Troubleshooting Agent (v1)
# Author: Arunvel Arunachalam (Concept)
# Purpose: Agentic AI based Kubernetes troubleshooting

import sys
import json
from kubernetes import client, config
from rich import print
from rich.panel import Panel
from rich.table import Table

# ----------------------------
# CONFIGURATION
# ----------------------------
MODE = "ADVISE"  # ADVISE | APPROVE | AUTO
LOG_LINES = 50

# ----------------------------
# KUBERNETES CLIENT SETUP
# ----------------------------
def load_k8s():
    try:
        config.load_kube_config()
    except:
        config.load_incluster_config()
    return client.CoreV1Api(), client.AppsV1Api()

v1, apps_v1 = load_k8s()

# ----------------------------
# DATA COLLECTORS
# ----------------------------
def get_pod(namespace, pod):
    return v1.read_namespaced_pod(pod, namespace)


def get_events(namespace, pod):
    events = v1.list_namespaced_event(namespace)
    return [e.message for e in events.items if e.involved_object.name == pod]


def get_logs(namespace, pod):
    try:
        return v1.read_namespaced_pod_log(pod, namespace, tail_lines=LOG_LINES)
    except:
        return "No logs available"

# ----------------------------
# RULE BASED DETECTION (NO AI)
# ----------------------------
def rule_engine(pod):
    status = pod.status
    cs = status.container_statuses
    if not cs:
        return "Unknown"

    state = cs[0].state
    if state.waiting:
        return state.waiting.reason
    if state.terminated:
        return state.terminated.reason
    return status.phase

# ----------------------------
# LLM REASONING (SIMULATED)
# Replace this later with OpenAI / Llama
# ----------------------------
def llm_reasoning(context):
    issue = context['issue']

    explanations = {
        "CrashLoopBackOff": "Application is crashing repeatedly due to runtime error or misconfiguration.",
        "ImagePullBackOff": "Container image cannot be pulled due to wrong image name or registry auth issue.",
        "OOMKilled": "Container exceeded memory limits.",
        "Pending": "Pod is waiting for resources or scheduling constraints.",
    }

    fixes = {
        "CrashLoopBackOff": "Check application logs and environment variables. Consider restarting pod.",
        "ImagePullBackOff": "Verify image name and registry credentials.",
        "OOMKilled": "Increase memory limits or optimize application memory usage.",
        "Pending": "Check node resources, taints, and tolerations.",
    }

    return {
        "root_cause": explanations.get(issue, "Insufficient data to determine root cause."),
        "fix": fixes.get(issue, "Manual investigation required."),
        "confidence": "70%"
    }

# ----------------------------
# ACTION EXECUTOR
# ----------------------------
def restart_pod(namespace, pod):
    v1.delete_namespaced_pod(pod, namespace)

# ----------------------------
# MAIN AGENT LOGIC
# ----------------------------
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
    table.add_row("Root Cause", reasoning['root_cause'])
    table.add_row("Suggested Fix", reasoning['fix'])
    table.add_row("Confidence", reasoning['confidence'])

    print(table)

    if MODE == "AUTO" and issue in ["CrashLoopBackOff", "OOMKilled"]:
        restart_pod(namespace, pod_name)
        print(Panel("Pod restarted automatically", style="bold red"))

    if MODE == "APPROVE":
        choice = input("Approve pod restart? (yes/no): ")
        if choice.lower() == "yes":
            restart_pod(namespace, pod_name)
            print(Panel("Pod restarted", style="bold red"))

# ----------------------------
# CLI ENTRY POINT
# ----------------------------
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python kubernetes_agent_v1.py <namespace> <pod-name>")
        sys.exit(1)

    ns = sys.argv[1]
    pod = sys.argv[2]
    diagnose(ns, pod)
