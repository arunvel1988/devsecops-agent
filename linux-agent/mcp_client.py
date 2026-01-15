import asyncio
from openai import OpenAI
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def main():
    # Local LLM (Ollama) — TEXT ONLY
    llm = OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )

    params = StdioServerParameters(
        command="python3",
        args=["k8s_mcp_server.py"]
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # 1️⃣ Ask LLM what to do
            user_question = "What nodes are in my Kubernetes cluster?"

            decision = llm.chat.completions.create(
                model="llama3.1:8b",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Kubernetes assistant. "
                                   "If the user asks about nodes, respond ONLY with: LIST_NODES"
                    },
                    {
                        "role": "user",
                        "content": user_question
                    }
                ]
            )

            intent = decision.choices[0].message.content.strip()
            print("LLM INTENT:", intent)

            # 2️⃣ Map intent → MCP tool
            if intent == "LIST_NODES":
                result = await session.call_tool("list_nodes", {})
                print("\nKUBERNETES NODES:")
                for item in result.content:
                    print("-", item.text)
            else:
                print("Unknown intent")

if __name__ == "__main__":
    asyncio.run(main())
