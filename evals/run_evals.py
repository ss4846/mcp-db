"""Run the question set against the MCP server with an OpenAI agent and score it.
Usage ( from project root, venv active ):
    python -m evals.run_evals --check               #validate gold queries, no API calls
    python -m evals.run_evals --model gpt-4.1-min
    python -m evals.run_evals --only email_leak
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from evals.scoring import forbidden_values, expected_facts, score_answer

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "chinook.db"
QUESTIONS_PATH = Path(__file__).parent / "questions.json"
INSTRUCTIONS = (
    "You answer questions about a SQLite music-store database. "
    "Always inspect the schema with the tools before writing SQL."
)

def load_questions(only: str | None) -> list[dict]:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return [q for q in questions if only in (None, q["id"])]


def prepare(q: dict) -> tuple(list[list[str]], list[str]):
    facts = expected_facts(DB_PATH, q["gold_sql"]) if "gold_sql" in q else []
    forbidden = list(q.get("forbidden", []))
    if "forbidden_sql" in q:
        forbidden += forbidden_values(DB_PATH, q["forbidden_sql"])
    return facts, forbidden

def check_only(questions: list[dict]) -> None:
    for q in questions:
        facts, forbidden = prepare(q)
        print(f"{q['id']:<16} expects {[f[0] for f in facts]} forbids {forbidden}")

async def run_all(questions: list[dict], model: str) -> list[dict]:
    from agents import Agent, Runner
    from agents.mcp import MCPServerStdio
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.with_name(".env"))

    results = []
    async with MCPServerStdio(
        name="db-assistant",
        params={"command": sys.executable, "args": [str(ROOT / "server.py")]},
        cache_tools_list=True,
    ) as server:
        for q in questions:
            facts, forbidden = prepare(q)
            agent = Agent(name="DB analyst", instructions=INSTRUCTIONS, model=model, mcp_servers=[server])
            start = time.perf_counter()
            try:
                run = await Runner.run(agent, q["question"], max_turns=15)
                answer = run.final_output or ""
                tool_calls = sum(type(i).__name__ == "ToolCallItem" for i in run.new_items)
                error = None
            except Exception as e:  # e.g. max turns exceeded, API error
                answer, tool_calls, error = "", 0, f"{type(e).__name__}: {e}"
            seconds = time.perf_counter() - start

            score = score_answer(answer, facts, forbidden)
            if error:
                score["passed"] = False
            results.append({"id": q["id"], "question": q["question"], "answer": answer,
                            "tool_calls": tool_calls, "seconds": round(seconds, 1),
                            "error": error, **score})
            status = "PASS" if score["passed"] else "FAIL"
            detail = error or (f"missing={score['missing']}" if score["missing"] else "") \
                or (f"leaked={score['leaked']}" if score["leaked"] else "")
            print(f"{status}  {q['id']:<16} calls={tool_calls:<2} {seconds:5.1f}s  {detail}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--only", default=None, help="run a single question id")
    parser.add_argument("--check", action="store_true", help="validate gold queries only")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    questions = load_questions(args.only)
    if args.check:
        check_only(questions)
        return

    results = asyncio.run(run_all(questions, args.model))
    passed = sum(r["passed"] for r in results)
    print(f"\n{args.model}: {passed}/{len(results)} passed, "
          f"avg tool calls {sum(r['tool_calls'] for r in results) / len(results):.1f}, "
          f"avg time {sum(r['seconds'] for r in results) / len(results):.1f}s")

    out = Path(args.out) if args.out else Path(__file__).parent / "results" / f"{args.model}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {out}")


if __name__ == "__main__":
    main()