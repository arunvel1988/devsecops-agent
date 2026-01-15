# mcp_server.py
import subprocess
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kubernetes-agent")

def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as e:
        return e.output.decode()

@mcp.tool()
def list_nodes() -> str:
    """List Kubernetes nodes"""
    return run(["kubectl", "get", "nodes", "-o", "wide"])

@mcp.tool()
def list_pods(namespace: str = "default") -> str:
    """List pods in a namespace"""
    return run(["kubectl", "get", "pods", "-n", namespace])

@mcp.tool()
def list_services(namespace: str = "default") -> str:
    """List services in a namespace"""
    return run(["kubectl", "get", "svc", "-n", namespace])

@mcp.tool()
def describe(resource: str, name: str, namespace: str = "default") -> str:
    """Describe any Kubernetes resource"""
    return run(["kubectl", "describe", resource, name, "-n", namespace])

@mcp.tool()
def get_logs(pod: str, namespace: str = "default") -> str:
    """Get pod logs"""
    return run(["kubectl", "logs", pod, "-n", namespace])

if __name__ == "__main__":
    mcp.run()
