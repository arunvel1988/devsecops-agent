 cat k8s_mcp_server.py 
from mcp.server.fastmcp import FastMCP
from kubernetes import client, config

print(">>> Starting Kubernetes MCP server...")

config.load_kube_config()
v1 = client.CoreV1Api()

mcp = FastMCP("kubernetes")

@mcp.tool()
def list_nodes():
    """List Kubernetes nodes"""
    nodes = v1.list_node()
    return [n.metadata.name for n in nodes.items]

if __name__ == "__main__":
    mcp.run()
