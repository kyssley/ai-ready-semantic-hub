"""Real MCP stdio handshake and calls through a real HTTP server."""

import importlib.util
import os
import socket
import sys
import tempfile
import threading
import time
import unittest


@unittest.skipUnless(importlib.util.find_spec("mcp"), "Install the mcp extra")
class McpIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_end_to_end(self):
        import uvicorn
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from semantic_hub.api import create_app
        from test_core import example

        with tempfile.TemporaryDirectory() as folder:
            token = "mcp-viewer-token-" + "x" * 32
            app = create_app(
                db_path=folder + "/mcp.db",
                demo=False,
                tokens={token: {"name": "agent", "role": "viewer"}},
            )
            app.state.store.save(example(), 1, "setup", "Synthetic data")
            app.state.store.publish(2, "setup")
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
            thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
            thread.start()
            try:
                for _ in range(100):
                    if server.started:
                        break
                    time.sleep(0.01)
                self.assertTrue(server.started)
                params = StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "semantic_hub.mcp_server"],
                    env={**os.environ, "HUB_URL": f"http://127.0.0.1:{port}", "HUB_TOKEN": token},
                )
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        listed = await session.list_tools()
                        self.assertEqual(
                            {t.name for t in listed.tools},
                            {"search_semantics", "get_semantic_context", "compile_metric_query"},
                        )
                        found = await session.call_tool("search_semantics", {"question": "成交额"})
                        self.assertFalse(found.isError, str(found.content))
                        self.assertIn("seller_gmv", found.content[0].text)
                        result = await session.call_tool(
                            "get_semantic_context", {"question": "GMV"}
                        )
                        self.assertIn("relationships", result.content[0].text)
                        compiled = await session.call_tool(
                            "compile_metric_query",
                            {"metrics": ["seller_gmv"], "dimensions": ["order_items.currency"]},
                        )
                        self.assertFalse(compiled.isError)
                        self.assertIn("SELECT", compiled.content[0].text)
                        denied = await session.call_tool(
                            "compile_metric_query",
                            {"metrics": ["refund_rate"], "dimensions": ["order_items.currency"]},
                        )
                        self.assertTrue(denied.isError)
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                sock.close()


if __name__ == "__main__":
    unittest.main()
