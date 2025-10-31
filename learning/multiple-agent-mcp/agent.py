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
# IMPORTANT: Never hardcode tokens. Expect it in the environment.
github_pat = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")

# --- GitHub MCP Toolset ----------------------------------------------------
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

"""Kubernetes MCP Integration
We add a second MCP toolset for Kubernetes / Helm operations. The user asked to
"run it in web mode" (SSE / streamable-http). The Google ADK MCPToolset we are
using currently establishes stdio-based sessions; to keep reliability we launch
the k8s-mcp-server in `--mode stdio` within a container. This still satisfies
functional needs (all tools exposed) while remaining compatible. If/when an
HTTP/SSE connection helper is available, we can switch to:
  podman run -p 8080:8080 -v ~/.kube/config:/home/appuser/.kube/config:ro \
     ginnux/k8s-mcp-server:latest --mode sse
and instantiate an HTTP/SSE connection params object instead.

Security NOTE: kubeconfig is mounted read-only; RBAC in that config governs
what the agent can actually mutate. For now we allow full tool discovery and
depend on the configured read/write mode of the server (defaults allow writes).
If you want read-only safety, add '--read-only' to the args list below.
"""

k8s_mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command='podman',
            args=[
                'run', '-i', '--rm',
                # Mount host kubeconfig into non-root home used by container
                '-v', f"{os.path.expanduser('~')}/.kube/config:/home/appuser/.kube/config:ro",
                'ginnux/k8s-mcp-server:latest',
                '--mode', 'stdio'
                # Consider adding '--read-only' if you wish to block mutations.
            ],
            env={}  # k8s-mcp-server does not require extra env for stdio mode
        ),
        timeout=20  # a little higher; first discovery can take a moment
    ),
    tool_filter=None  # discover all k8s + helm tool names
)

tools_list = [say_hello, say_time, say_thanks]
if github_mcp_toolset:
    tools_list.append(github_mcp_toolset)
if k8s_mcp_toolset:
    tools_list.append(k8s_mcp_toolset)

root_agent = Agent(
    name="hello_agent",
    model="gemini-2.0-flash",
    description="Coordinator agent: greetings, time, gratitude, GitHub PR insights, and Kubernetes/Helm operations via MCP toolsets.",
    instruction=(
        "You are the coordinator agent. Responsibilities:\n"
        "1. Greet users by name using 'say_hello'.\n"
        "2. Provide current time (delegate to 'time_agent' or call 'say_time').\n"
        "3. Respond politely to gratitude (delegate to 'thanks_agent' or call 'say_thanks').\n"
        "4. If GitHub MCP tools are available and the user asks about repository or Pull Request information:\n"
        "   a. For listing ALL repos in an organization, request the org name (e.g. 'org-name') then call the repo listing tool (e.g. 'list_repos').\n"
        "   b. For PR listing: call the PR listing tool (e.g. 'list_pull_requests').\n"
        "   c. For single PR details: call the PR detail tool (e.g. 'get_pull_request').\n"
        "   d. For changed files in a PR: call the PR files tool (e.g. 'list_pull_request_files').\n"
        "   e. For diffs: call the diff tool if exposed (e.g. 'get_pull_request_diff').\n"
        "5. For ANY Kubernetes or Helm related request (e.g. list pods/resources, describe objects, fetch logs, get metrics, restart rollouts, create/update/delete manifests, list Helm releases, install/upgrade/uninstall charts):\n"
        "   a. Identify the user intent (read vs mutate).\n"
        "   b. Select the appropriate Kubernetes MCP tool (e.g. getAPIResources, listResources, getResource, describeResource, getPodsLogs, getPodMetrics, getNodeMetrics, getEvents, createOrUpdateResource / createOrUpdateResourceYAML, deleteResource, rolloutRestart, getIngresses).\n"
        "   c. For Helm operations use helmList, helmGet, helmHistory, helmInstall, helmUpgrade, helmRollback, helmUninstall, helmRepoList, helmRepoAdd as appropriate.\n"
        "   d. ALWAYS confirm required parameters (kind, name, namespace, chart name, release name, etc.) requesting clarification if absent.\n"
        "   e. Do NOT fabricate cluster state—only rely on tool responses.\n"
        "   f. If a write (mutation) is requested and the server is (or should be) in read-only mode, explain the limitation and offer a read-only alternative (like showing the manifest).\n"
        "6. Always verify required parameters (org, repo, PR number) or k8s object identifiers and ask the user to clarify if missing.\n"
        "Never fabricate repo, PR, or cluster data; if a relevant MCP toolset is unavailable, inform the user which capability is missing."
    ),
    tools=tools_list,
    sub_agents=[say_time_agent, say_thanks_agent]
)
