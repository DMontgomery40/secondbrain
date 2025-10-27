"""Command-line interface for Second Brain."""

import asyncio
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import structlog
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import Config
from .database import Database
from .pipeline import ProcessingPipeline
from .embeddings import EmbeddingService

# Load environment variables
load_dotenv()

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging_level=20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

console = Console()
logger = structlog.get_logger()


def get_pid_file() -> Path:
    """Get path to PID file."""
    return Path.home() / "Library" / "Application Support" / "second-brain" / "second-brain.pid"


def is_running() -> bool:
    """Check if service is running."""
    pid_file = get_pid_file()
    if not pid_file.exists():
        return False
    
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        # Process doesn't exist or PID file is invalid
        pid_file.unlink(missing_ok=True)
        return False


def save_pid():
    """Save current process PID."""
    pid_file = get_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))


def remove_pid():
    """Remove PID file."""
    pid_file = get_pid_file()
    pid_file.unlink(missing_ok=True)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Second Brain - Local-first visual memory capture and search."""
    pass


@main.command()
@click.option("--fps", type=float, help="Frames per second to capture")
def start(fps: Optional[float]):
    """Start the capture service."""
    if is_running():
        console.print("[yellow]Service is already running[/yellow]")
        return
    
    console.print("[green]Starting Second Brain capture service...[/green]")
    
    # Load config
    config = Config()
    
    # Override FPS if provided
    if fps:
        config.set("capture.fps", fps)
    
    # Save PID
    save_pid()
    
    # Create pipeline
    pipeline = ProcessingPipeline(config)
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        console.print("\n[yellow]Stopping service...[/yellow]")
        asyncio.create_task(pipeline.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start pipeline
    async def run():
        try:
            await pipeline.start()
            
            console.print(f"[green]✓[/green] Service started (PID: {os.getpid()})")
            console.print(f"[green]✓[/green] Capturing at {config.get('capture.fps')} FPS")
            console.print(f"[green]✓[/green] Press Ctrl+C to stop")
            
            # Keep running
            while pipeline.running:
                await asyncio.sleep(1)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping service...[/yellow]")
        finally:
            await pipeline.stop()
            remove_pid()
            console.print("[green]Service stopped[/green]")
    
    try:
        asyncio.run(run())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        remove_pid()
        sys.exit(1)


@main.command()
def stop():
    """Stop the capture service."""
    if not is_running():
        console.print("[yellow]Service is not running[/yellow]")
        return
    
    pid_file = get_pid_file()
    with open(pid_file, "r") as f:
        pid = int(f.read().strip())
    
    try:
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]✓[/green] Sent stop signal to process {pid}")
        
        # Wait for process to stop
        import time
        for _ in range(10):
            if not is_running():
                console.print("[green]Service stopped[/green]")
                return
            time.sleep(0.5)
        
        console.print("[yellow]Service may still be stopping...[/yellow]")
        
    except OSError as e:
        console.print(f"[red]Error stopping service: {e}[/red]")
        remove_pid()


@main.command()
def status():
    """Show service status."""
    if not is_running():
        console.print("[yellow]Service is not running[/yellow]")
        return
    
    console.print("[green]Service is running[/green]")
    
    # Get stats from database
    try:
        db = Database()
        stats = db.get_database_stats()
        
        table = Table(title="Second Brain Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Status", "Running")
        table.add_row("Total Frames", str(stats["frame_count"]))
        table.add_row("Text Blocks", str(stats["text_block_count"]))
        table.add_row("Apps Tracked", str(stats["window_count"]))
        
        if stats["database_size_bytes"]:
            size_mb = stats["database_size_bytes"] / (1024 * 1024)
            table.add_row("Database Size", f"{size_mb:.2f} MB")
        
        if stats["oldest_frame_timestamp"]:
            oldest = datetime.fromtimestamp(stats["oldest_frame_timestamp"])
            table.add_row("Oldest Frame", oldest.strftime("%Y-%m-%d %H:%M:%S"))
        
        if stats["newest_frame_timestamp"]:
            newest = datetime.fromtimestamp(stats["newest_frame_timestamp"])
            table.add_row("Newest Frame", newest.strftime("%Y-%m-%d %H:%M:%S"))
        
        console.print(table)
        
        db.close()
        
    except Exception as e:
        console.print(f"[red]Error getting stats: {e}[/red]")


@main.command()
@click.argument("query")
@click.option("--app", help="Filter by application bundle ID")
@click.option("--from", "from_date", help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", help="End date (YYYY-MM-DD)")
@click.option("--limit", default=10, help="Maximum number of results")
@click.option("--semantic", is_flag=True, help="Use semantic vector search")
def query(query: str, app: Optional[str], from_date: Optional[str], to_date: Optional[str], limit: int, semantic: bool):
    """Search captured memory."""
    console.print(f"[cyan]Searching for:[/cyan] {query}")
    
    # Parse dates
    start_timestamp = None
    end_timestamp = None
    
    if from_date:
        try:
            dt = datetime.strptime(from_date, "%Y-%m-%d")
            start_timestamp = int(dt.timestamp())
        except ValueError:
            console.print(f"[red]Invalid from date format. Use YYYY-MM-DD[/red]")
            return
    
    if to_date:
        try:
            dt = datetime.strptime(to_date, "%Y-%m-%d")
            end_timestamp = int(dt.timestamp())
        except ValueError:
            console.print(f"[red]Invalid to date format. Use YYYY-MM-DD[/red]")
            return
    
    # Search database
    try:
        db = Database()
        
        display_results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Searching...", total=None)

            if semantic:
                embedding_service = EmbeddingService()
                matches = embedding_service.search(
                    query=query,
                    limit=limit,
                    app_filter=app,
                )

                for match in matches:
                    frame = db.get_frame(match["frame_id"])
                    if not frame:
                        continue
                    block = db.get_text_block(match["block_id"])
                    if not block:
                        continue
                    display_results.append(
                        {
                            "window_title": frame.get("window_title") or "Untitled",
                            "app_name": frame.get("app_name") or "Unknown",
                            "timestamp": frame.get("timestamp"),
                            "text": block.get("text", ""),
                            "score": 1 - match.get("distance", 0.0) if match.get("distance") is not None else None,
                            "method": "semantic",
                        }
                    )
            else:
                results = db.search_text(
                    query=query,
                    app_filter=app,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                    limit=limit,
                )
                for result in results:
                    display_results.append(
                        {
                            "window_title": result.get("window_title") or "Untitled",
                            "app_name": result.get("app_name") or "Unknown",
                            "timestamp": result.get("timestamp"),
                            "text": result.get("text", ""),
                            "score": result.get("score"),
                            "method": "fts",
                        }
                    )

        if not display_results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        console.print(f"\n[green]Found {len(display_results)} results:[/green]\n")
        
        for i, result in enumerate(display_results, 1):
            timestamp = datetime.fromtimestamp(result["timestamp"])
            score_line = ""
            raw_score = result.get("score")
            if raw_score is not None:
                if result["method"] == "semantic":
                    score_label = "Similarity"
                    display_score = raw_score
                else:
                    score_label = "Relevance"
                    display_score = 1 / (1 + raw_score) if raw_score >= 0 else raw_score
                score_line = f"\n[dim]{score_label}: {display_score:.3f}[/dim]"
            
            panel = Panel(
                f"[bold]{result['window_title']}[/bold]\n"
                f"[dim]{result['app_name']} • {timestamp.strftime('%Y-%m-%d %H:%M:%S')}[/dim]{score_line}\n\n"
                f"{result['text'][:200]}{'...' if len(result['text']) > 200 else ''}",
                title=f"Result {i}",
                border_style="cyan",
            )
            console.print(panel)
        
        db.close()
        
    except Exception as e:
        console.print(f"[red]Error searching: {e}[/red]")
        import traceback
        traceback.print_exc()


@main.command()
def health():
    """Check system health."""
    console.print("[cyan]Checking system health...[/cyan]\n")
    
    checks = []
    
    # Check if service is running
    if is_running():
        checks.append(("Service Status", "✓ Running", "green"))
    else:
        checks.append(("Service Status", "✗ Not running", "yellow"))
    
    # Check OpenAI API key
    if os.getenv("OPENAI_API_KEY"):
        checks.append(("OpenAI API Key", "✓ Configured", "green"))
    else:
        checks.append(("OpenAI API Key", "✗ Not found", "red"))
    
    # Check database
    try:
        db = Database()
        db.close()
        checks.append(("Database", "✓ Accessible", "green"))
    except Exception as e:
        checks.append(("Database", f"✗ Error: {e}", "red"))
    
    # Check disk space
    import psutil
    config = Config()
    frames_dir = config.get_frames_dir()
    disk = psutil.disk_usage(str(frames_dir))
    free_gb = disk.free / (1024 ** 3)
    
    if free_gb > config.get("capture.min_free_space_gb", 10):
        checks.append(("Disk Space", f"✓ {free_gb:.1f} GB free", "green"))
    else:
        checks.append(("Disk Space", f"✗ Only {free_gb:.1f} GB free", "red"))
    
    # Display results
    table = Table(title="Health Check")
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    
    for component, status, color in checks:
        table.add_row(component, f"[{color}]{status}[/{color}]")
    
    console.print(table)


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--no-open", is_flag=True, help="Do not open the browser automatically")
def timeline(host: str, port: int, no_open: bool):
    """Launch the timeline visualization server."""
    try:
        from uvicorn import Config as UvicornConfig, Server as UvicornServer
    except ImportError as exc:
        console.print("[red]uvicorn is not installed. Please install with `pip install uvicorn`.[/red]")
        raise click.ClickException(str(exc))

    from .api.server import create_app

    app = create_app()
    config = UvicornConfig(app=app, host=host, port=port, log_level="info")
    server = UvicornServer(config)

    url = f"http://{host}:{port}"
    console.print(f"[green]Timeline server available at {url}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    if not no_open:
        import webbrowser

        try:
            webbrowser.open(url)
        except Exception:
            console.print("[yellow]Unable to open browser automatically[/yellow]")

    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down timeline server...[/yellow]")


@main.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", show_default=True, help="Transport protocol (stdio for Claude Desktop, sse for HTTP)")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host for SSE transport")
@click.option("--port", default=8100, show_default=True, type=int, help="Port for SSE transport")
def mcp(transport: str, host: str, port: int):
    """
    Start MCP (Model Context Protocol) server.

    This exposes Second Brain's visual memory as MCP tools that can be consumed
    by AI assistants like Claude Desktop or AGRO RAG engine.

    Use 'stdio' transport for Claude Desktop integration.
    Use 'sse' transport for HTTP-based clients like AGRO.
    """
    try:
        from .mcp.server import create_mcp_server
    except ImportError:
        console.print("[red]MCP SDK not installed. Install with: pip install mcp[cli][/red]")
        sys.exit(1)

    console.print(f"[green]Starting Second Brain MCP server ({transport} transport)...[/green]")

    config = Config()
    mcp_server = create_mcp_server(config=config)

    async def run_stdio():
        """Run with stdio transport for Claude Desktop."""
        from mcp.server.stdio import stdio_server

        console.print("[green]✓[/green] MCP server ready (stdio)")
        console.print("[dim]Connect from Claude Desktop or pipe to stdin/stdout[/dim]")

        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options()
            )

    async def run_sse():
        """Run with SSE transport for HTTP clients."""
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route

        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await mcp_server.run(
                    streams[0], streams[1], mcp_server.create_initialization_options()
                )

        async def handle_messages(request):
            await sse.handle_post_message(request.scope, request.receive, request._send)

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ]
        )

        url = f"http://{host}:{port}"
        console.print(f"[green]✓[/green] MCP server available at {url}")
        console.print(f"[dim]SSE endpoint: {url}/sse[/dim]")
        console.print(f"[dim]Messages endpoint: {url}/messages[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")

        import uvicorn
        await uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_level="info")
        ).serve()

    try:
        if transport == "stdio":
            asyncio.run(run_stdio())
        else:
            asyncio.run(run_sse())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down MCP server...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error running MCP server: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
