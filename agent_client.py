import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStdio


async def main():
    async with MCPServerStdio(
        name="db-assistant",
        params={
            "command": "/home/omar1340/mcp-db/.venv/bin/python",
            "args": ["/home/omar1340/mcp-db/server.py"],
        },
        cache_tools_list=True,
    ) as server:
        agent = Agent(
            name="DB analyst",
            instructions=(
                "You answer questions about a SQLite music-store database. "
                "Always inspect the schema with the tools before writing SQL."
            ),
            model="gpt-6.1-sol",  # use any model your key has access to
            mcp_servers=[server],
        )
        result = await Runner.run(
            agent,
            "Which 5 artists have the most tracks, and which country spends the most?",
        )
        print(result.final_output)
        print("\n--- steps taken ---")
        for item in result.new_items:
            print(type(item).__name__)


asyncio.run(main())