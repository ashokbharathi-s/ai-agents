from google.adk.agents import Agent
from datetime import datetime
import os
from google.adk.agents.llm_agent import LlmAgent  # (optional upgrade path)
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool import StdioConnectionParams
from mcp import StdioServerParameters

def say_hello(name: str = "there"):
    """Greeting function with default parameter"""
    if name:
        return f"Hello, {name}!"
    else:
        return "Hello there!"

def say_time():
    return f"The current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

def say_thanks():
    return "You're welcome! Happy to help!"

say_time_agent = Agent(
    name="time_agent",
    model="gemini-2.0-flash",
    description="An agent that tells the current time.",
    instruction="You are a time agent. When asked about time, use the 'say_time' tool to provide the current time.",
    tools=[say_time]  
)

say_thanks_agent = Agent(
    name="thanks_agent",
    model="gemini-2.0-flash",
    description="An agent that responds to thank you messages with polite acknowledgments.",
    instruction="You are a polite thanks agent. When the user says 'thank you', 'thanks', or shows gratitude, use the 'say_thanks' tool to respond courteously.",
    tools=[say_thanks]  
)
# Securely load GitHub token (ensure it's exported in your environment before running)
github_pat = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")

github_mcp_toolset = None
if github_pat:
    # Use Stdio (podman) GitHub MCP server so we don't rely on an external HTTP endpoint.
    github_mcp_toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command='podman',
                args=[
                    'run', '-i', '--rm',
                    '-e', 'GITHUB_PERSONAL_ACCESS_TOKEN',
                    '-e', 'GITHUB_HOST',
                    'ghcr.io/github/github-mcp-server'
                ],
                env={'GITHUB_PERSONAL_ACCESS_TOKEN': github_pat,
                     'GITHUB_HOST': 'https://github.com'}
            ),
            timeout=15
        ),
        # Allow full discovery first; we can tighten with a filter once actual tool names confirmed.
        tool_filter=None
    )
else:
    # Token missing; root agent will operate without GitHub MCP capabilities and instruct user to set it.
    pass

tools_list = [say_hello, say_time, say_thanks]
if github_mcp_toolset:
    tools_list.append(github_mcp_toolset)

root_agent = Agent(
    name="hello_agent",
    model="gemini-2.0-flash",
    description="Coordinator agent: greetings, time, gratitude, and (if configured) GitHub PR insights via MCP GitHub toolset.",
    instruction=(
        "You are the coordinator agent. Responsibilities:\n"
        "1. Greet users by name using 'say_hello'.\n"
        "2. Provide current time (delegate to 'time_agent' or call 'say_time').\n"
        "3. Respond politely to gratitude (delegate to 'thanks_agent' or call 'say_thanks').\n"
        "4. If GitHub MCP tools are available and the user asks about Pull Requests (e.g. 'list PRs for ford-ecom360/repo', 'show PR 42'), enumerate tools first if not cached, then call the appropriate one.\n"
        "   a. Ask for repo full name if missing (org/repo).\n"
        "   b. For listing: use the PR listing tool.\n"
        "   c. For single PR details: use the PR detail tool.\n"
        "   d. For changed files: use the PR files tool.\n"
        "   e. For diffs: use the PR diff tool (only if exposed).\n"
        "Never fabricate PR data; if tools unavailable (no token), inform the user to export GITHUB_PERSONAL_ACCESS_TOKEN.\n"
        "Operate read-only; do NOT attempt merges, comments, or mutations."
    ),
    tools=tools_list,
    sub_agents=[say_time_agent, say_thanks_agent]
)
