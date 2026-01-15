import subprocess
import json
import re

class KubernetesAgent:
    def __init__(self):
        # conversational context
        self.context = {
            "namespace": "default",
            "pod": None,
            "deployment": None,
            "resource": None
        }

    # -----------------------------
    # MAIN ENTRY
    # -----------------------------
    def handle(self, user_input: str, confirm: bool = False):
        user_input = user_input.lower().strip()

        # ROUTING
        if "failed pod" in user_input or "failed pods" in user_input:
            return self.failed_pods()

        if "create nginx" in user_input and "pod" in user_input:
            return self.create_nginx_pod()

        if "delete pod" in user_input:
            return self.delete_pod(user_input, confirm)

        if "describe pod" in user_input:
            return self.describe_pod(user_input)

        if "pod logs" in user_input or user_input == "logs":
            return self.pod_logs()

        if "logs for pod" in user_input:
            return self.logs_for_specific_pod(user_input)

        if "get services" in user_input:
            return self.get_services(user_input)

        if "get pods" in user_input or user_input == "pods":
            return self.get_pods(user_input)

        return "I understand Kubernetes operations like pods, logs, failures, services, deployments. Try again."

    # -----------------------------
    # KUBECTL EXECUTOR
    # -----------------------------
    def run(self, command):
        try:
            result = subprocess.check_output(
                ["bash", "-c", command],
                stderr=subprocess.STDOUT
            ).decode()
            return result
        except subprocess.CalledProcessError as e:
            return e.output.decode()

    # -----------------------------
    # FAILED PODS (SMART)
    # -----------------------------
    def failed_pods(self):
        cmd = (
            "kubectl get pods --all-namespaces "
            "--field-selector=status.phase=Failed"
        )
        output = self.run(cmd)

        # If none failed, check CrashLoopBackOff
        if "No resources found" in output:
            cmd = (
                "kubectl get pods --all-namespaces | "
                "grep -E 'CrashLoopBackOff|Error'"
            )
            output = self.run(cmd)

        # Capture first failing pod for context
        lines = output.strip().splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            self.context["namespace"] = parts[0]
            self.context["pod"] = parts[1]

        return output or "No failed pods found."

    # -----------------------------
    # POD LOGS (CONTEXT AWARE)
    # -----------------------------
    def pod_logs(self):
        if not self.context["pod"]:
            return "Which pod do you want logs for?"

        ns = self.context["namespace"]
        pod = self.context["pod"]

        cmd = f"kubectl logs {pod} -n {ns} --all-containers=true --tail=100"
        return self.run(cmd)

    def logs_for_specific_pod(self, user_input):
        match = re.search(r"pod\s+([a-z0-9\-]+)", user_input)
        if not match:
            return "Pod name not detected."

        pod = match.group(1)
        ns = self.context.get("namespace", "default")

        self.context["pod"] = pod
        cmd = f"kubectl logs {pod} -n {ns} --all-containers=true --tail=100"
        return self.run(cmd)

    # -----------------------------
    # DESCRIBE POD
    # -----------------------------
    def describe_pod(self, user_input):
        if not self.context["pod"]:
            return "Which pod should I describe?"

        pod = self.context["pod"]
        ns = self.context["namespace"]

        cmd = f"kubectl describe pod {pod} -n {ns}"
        return self.run(cmd)

    # -----------------------------
    # GET PODS
    # -----------------------------
    def get_pods(self, user_input):
        if "all namespace" in user_input:
            cmd = "kubectl get pods --all-namespaces"
        else:
            cmd = f"kubectl get pods -n {self.context['namespace']}"

        output = self.run(cmd)
        return output

    # -----------------------------
    # SERVICES
    # -----------------------------
    def get_services(self, user_input):
        if "all namespace" in user_input:
            cmd = "kubectl get svc --all-namespaces"
        else:
            cmd = f"kubectl get svc -n {self.context['namespace']}"

        return self.run(cmd)

    # -----------------------------
    # CREATE NGINX POD (SAFE)
    # -----------------------------
    def create_nginx_pod(self):
        cmd = (
            "kubectl run nginx "
            "--image=nginx "
            "--restart=Never "
            "-n default"
        )
        return self.run(cmd)

    # -----------------------------
    # DELETE POD (CONFIRM REQUIRED)
    # -----------------------------
    def delete_pod(self, user_input, confirm):
        match = re.search(r"delete pod\s+([a-z0-9\-]+)", user_input)
        if not match:
            return "Pod name missing."

        pod = match.group(1)
        ns = self.context["namespace"]

        if not confirm:
            return f"CONFIRM REQUIRED: delete pod {pod} in namespace {ns}"

        cmd = f"kubectl delete pod {pod} -n {ns}"
        return self.run(cmd)
