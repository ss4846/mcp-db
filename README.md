# mcp-db

Read-only database assistant MCP server (SQLite / Chinook sample data).

## Setup
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    curl -L -o chinook.db https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite

## Run
    npx @modelcontextprotocol/inspector python server.py
