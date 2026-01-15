
# mcp_client.py
import asyncio
from openai import OpenAI
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

SYSTEM_PROMPT = """
You are an intent router for a Kubernetes agent.

You MUST respond with ONE JSON object only.

Allowed actions:
- list_nodes
- list_pods
- list_services
- describe
- get_logs

Response format:
{
  "action": "<action_name>",
  "args": { ... }
}

Do NOT explain.
Do NOT add text.
"""

async def main():
    llm = OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )

    params = StdioServerParameters(
        command="python3",
        args=["mcp_server.py"]
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("\nKubernetes MCP Agent (type 'exit')")

            while True:
                user = input("\n> ")
                if user.lower() == "exit":
                    break

                decision = llm.chat.completions.create(
                    model="llama3.1:8b",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user}
                    ],
                )

                data = decision.choices[0].message.content
                try:
                    intent = eval(data)
                except Exception:
                    print("❌ LLM returned invalid format")
                    continue

                action = intent["action"]
                args = intent.get("args", {})

                result = await session.call_tool(action, args)

                print("\n--- Kubernetes Output ---")
                for item in result.content:
                    print(item.text)

if __name__ == "__main__":
    asyncio.run(main())
