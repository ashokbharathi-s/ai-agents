# Multi-Agent MCP Assistant

## 1. Overview

This project defines a lightweight multi-agent assistant built with Google ADK. The root agent coordinates simple conversational utilities (greeting, time reporting, gratitude responses) and, when configured, adds read-only GitHub Pull Request (PR) introspection through a Model Context Protocol (MCP) GitHub server.

## 2. Features

- Greeting support ("hello", personalized when name provided)
- Current time responses
- Polite acknowledgements for user gratitude
- Optional GitHub PR insights (list PRs, show PR details, changed files, diffs) via MCP toolset (podman container)
- Sub-agent pattern for specialization (`time_agent`, `thanks_agent`)
- Token-aware: GitHub toolset only loads if `GITHUB_PERSONAL_ACCESS_TOKEN` is present

## 3. Architecture

```text
learning/multiple-agent-mcp/
  agent.py              # Defines tools, sub-agents, root agent (hello_agent or enterprise_assistant)
  .env                  # Place non-secret config; never commit tokens
  README.md             # This documentation
  .venv/                # Python virtual environment (local)
```

Core components:

- Tools: `say_hello`, `say_time`, `say_thanks`
- Sub-agents: `time_agent` (time queries), `thanks_agent` (gratitude responses)
- Root agent: `hello_agent` (delegates + optionally invokes GitHub MCP tools)
- MCP GitHub Toolset: Started locally via `podman run ghcr.io/github/github-mcp-server`

### Data Flow (GitHub PR request example)

1. User asks: "List open PRs in org-name/some-repo".
2. Root agent checks availability of GitHub MCP toolset.
3. If loaded, enumerates/uses PR-related tool (e.g., listing tool) through MCP session.
4. Returns structured, read-only information to user.

## 4. Requirements

- macOS (tested) / Linux
- Python 3.12+
- `podman` installed (for GitHub MCP server)
- Valid GitHub Enterprise Personal Access Token (PAT) with at least `repo` scope
- Network access to GitHub (public or your enterprise host if applicable)

## 5. Environment Setup

### Clone & Activate Virtual Environment

```zsh
git clone https://github.com/ashokbharathi-s/ai-agents.git
cd ai-agents/learning/multiple-agent-mcp
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install google-adk
```

(If MCP or additional dependencies are required, install them: `pip install mcp`)

### Set GitHub Token (DO NOT commit it)

```zsh
export GITHUB_PERSONAL_ACCESS_TOKEN=<your_pat_here>
```

Optional: store token outside repo (e.g., in shell profile) and source it.

## 6. Running the Agent (CLI)

```zsh
source .venv/bin/activate
adk run learning/multiple-agent-mcp
```

Sample interactions:

```text
hello
what is the time now
thanks
list prs for org-name/your-repo
show pr 42 in org-name/your-repo
files changed in pr 42 org-name/your-repo
```

If GitHub tools are not available the agent will instruct you to export the token.

## 7. Running Web UI

From parent agents directory:

```zsh
cd ai-agents
export GITHUB_PERSONAL_ACCESS_TOKEN=<your_pat_here>
adk web agents --port 8000
```

Visit: <http://127.0.0.1:8000>

(If static assets 404, upgrade ADK: `pip install --upgrade google-adk` then restart.)

## 8. GitHub MCP Toolset Details

Current configuration (in `agent.py`):

- Stdio connection using `podman` container
- Environment variables passed: `GITHUB_PERSONAL_ACCESS_TOKEN`, `GITHUB_HOST`
- Tool discovery initially unrestricted (`tool_filter=None`) to allow enumeration

### Hardening (After Discovery)

Once actual tool names are confirmed, replace `tool_filter=None` with a curated list, e.g.:

```python
tool_filter=[
  "list_pull_requests",
  "get_pull_request",
  "list_pull_request_files",
  "get_pull_request_diff",
  "get_repo"
]
```

## 9. Security & Compliance

| Aspect | Guidance |
|--------|----------|
| Secrets | Never commit tokens. Use environment variables. |
| Access | GitHub MCP is read-only by design here. Do not enable write operations. |
| Scope | Token should have minimal scopes (repo, read:org if needed). |
| Filesystem | No filesystem MCP is enabled (removed intentionally). |
| Logging | ADK may log interactions; avoid sending secrets as user input. |

## 10. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| 404 static assets in web UI | Outdated ADK build | `pip install --upgrade google-adk` |
| CancelledError during MCP init | Token missing or container failing | Verify token; test `podman run` manually |
| Tools not found | Mismatch between expected tool names and server export | Run with `tool_filter=None` and ask agent to list tools |
| No PR data returned | Wrong repo slug or insufficient token scope | Confirm `org/repo` spelling; check PAT scopes |
| Import errors for MCP modules | Old ADK version | Upgrade ADK package |

## 11. Extending the Agent

Add a new specialist:

1. Define tool function (e.g., `def say_date(): ...`)
2. Create sub-agent or append tool directly:

```python
date_agent = Agent(name="date_agent", model="gemini-2.0-flash", tools=[say_date], instruction="Return today's date.")
root_agent.sub_agents.append(date_agent)
```

3. Update root instructions to delegate date queries.

## 12. Cleaning Up

Stop CLI: `CTRL+C`
Stop web server: `CTRL+C` in terminal
Deactivate venv:

```zsh

```

## 13. Next Steps

- Discover actual GitHub MCP tool names and tighten the `tool_filter`.
- Add structured output formatting (tables) for PR summaries.
- Integrate caching layer for repeated PR queries.
- Add evaluation scripts for regression testing of agent responses.

## 14. License / Internal Use

Prototype / learning project. Review before any production deployment.

---

Questions or enhancement requests? Update `README.md` or open a task in your internal tracker.
