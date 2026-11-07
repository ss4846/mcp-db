import asyncio
from pathlib import Path

from dotenv import load_dotenv

from agents import Agent, Runner
from agents.mcp import MCPServerStdio


load_dotenv(Path(__file__).with_name(".env"))


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
            model="gpt-6.1-sol",
            mcp_servers=[server],
        )
        result = await Runner.run(
            agent,
            "List details of any three customers.",
        )
        print(result.final_output)
        print("\n--- steps taken ---")
        for item in result.new_items:
            print(type(item).__name__)


asyncio.run(main())


