import asyncio
import os
import sys
from typing import Any, Dict

from mcp import ClientSession, ServerSession
from mcp.client.stdio import stdio_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolRequest, CallToolResult, Tool, TextContent, ErrorData

from agentshield.shield import AgentShield


class MCPSecurityGateway:
    def __init__(self, target_command: str, target_args: list[str]):
        """
        Initializes the MCP Security Gateway proxy.
        :param target_command: The command to start the downstream MCP server.
        :param target_args: The arguments for the downstream MCP server command.
        """
        self.target_command = target_command
        self.target_args = target_args
        self.server = Server("mcp-security-gateway")
        self.shield = AgentShield(api_key=os.environ.get("AGENT_SHIELD_API_KEY", "default"))
        self.downstream_session: ClientSession | None = None
        self.downstream_tools: Dict[str, Tool] = {}

        # Setup standard server handlers
        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            if not self.downstream_session:
                return []
            response = await self.downstream_session.list_tools()
            self.downstream_tools = {tool.name: tool for tool in response.tools}
            return response.tools

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
            if not self.downstream_session:
                raise ValueError("Not connected to downstream server")
            
            args = arguments or {}
            
            # 1. Intercept and Evaluate via AgentShield
            decision = self.shield.check_action(tool_name=name, args=args)
            
            # 2. Block if policy violated
            if not decision.allowed:
                return [
                    TextContent(
                        type="text",
                        text=f"AgentShield Policy Violation: {decision.reason}"
                    )
                ]
                
            # 3. Forward to downstream
            try:
                response = await self.downstream_session.call_tool(name, args)
                # mcp client returns CallToolResult. mcp server expects list of contents
                return response.content
            except Exception as e:
                return [TextContent(type="text", text=f"Downstream Error: {str(e)}")]

    async def run(self):
        """Runs the proxy server using stdio for both downstream client and upstream server."""
        
        from mcp.client.stdio import StdioServerParameters
        server_params = StdioServerParameters(
            command=self.target_command,
            args=self.target_args,
        )

        # 1. Connect to Downstream Server
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                self.downstream_session = session
                
                # 2. Start Upstream Server (Gateway)
                async with stdio_server() as (server_read, server_write):
                    await self.server.run(
                        server_read,
                        server_write,
                        self.server.create_initialization_options()
                    )

def main():
    if len(sys.argv) < 2:
        print("Usage: mcp-gateway <downstream_command> [args...]", file=sys.stderr)
        sys.exit(1)
        
    command = sys.argv[1]
    args = sys.argv[2:]
    
    gateway = MCPSecurityGateway(target_command=command, target_args=args)
    asyncio.run(gateway.run())

if __name__ == "__main__":
    main()
