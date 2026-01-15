
from mcp.server.fastmcp import FastMCP
from kubernetes import client, config

# Load kubeconfig
config.load_kube_config()

v1 = client.CoreV1Api()

mcp = FastMCP("kubernetes")

@mcp.tool()
def list_pods(namespace: str = "default"):
    """List pods in a Kubernetes namespace"""
    pods = v1.list_namespaced_pod(namespace)
    return [p.metadata.name for p in pods.items]

@mcp.tool()
def list_nodes():
    """List Kubernetes nodes"""
    nodes = v1.list_node()
    return [n.metadata.name for n in nodes.items]

if __name__ == "__main__":
    mcp.run()

