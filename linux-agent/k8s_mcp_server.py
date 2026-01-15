import subprocess
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kubernetes-universal-agent")

def run(cmd):
    try:
        return subprocess.check_output(
            cmd, stderr=subprocess.STDOUT
        ).decode()
    except subprocess.CalledProcessError as e:
        return e.output.decode()

@mcp.tool()
def kubectl(command: str):
    """
    Execute a kubectl command.
    Example:
      get pods -n kube-system
      describe pod nginx -n default
      delete pod nginx -n default
    """
    full_cmd = ["kubectl"] + command.split()
    return run(full_cmd)

if __name__ == "__main__":
    mcp.run()
