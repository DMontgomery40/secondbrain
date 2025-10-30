"""Command-line interface for Second Brain."""

import asyncio
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import psutil
import structlog
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import Config
from .database import Database
# Lazy imports for heavy dependencies
# from .pipeline import ProcessingPipeline
# from .embeddings import EmbeddingService

# Load environment variables
load_dotenv()

# Configure structlog with log level filtering


def filter_by_level(logger, method_name, event_dict):

    if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
        return event_dict
    
    # Filter out debug and info level logs by default
    level = event_dict.get("level")
    if level in ("debug", "info"):
        raise structlog.DropEvent
    
    return event_dict


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        filter_by_level,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

console = Console()
logger = structlog.get_logger()


def get_pid_file() -> Path:

    return Path.home() / "Library" / "Application Support" / "second-brain" / "second-brain.pid"


def _read_pid_file(pid_file: Path) -> tuple[int, Optional[float]]:

    pid_raw = pid_file.read_text().strip()
    expected_create_time: Optional[float] = None

    if ":" in pid_raw:
        pid_part, create_time_part = pid_raw.split(":", 1)
        pid = int(pid_part)
        try:
            expected_create_time = float(create_time_part)
        except ValueError:
            expected_create_time = None
    else:
        pid = int(pid_raw)

    return pid, expected_create_time


def is_running() -> bool:

    pid_file = get_pid_file()
    if not pid_file.exists():
        return False

    try:
        pid, expected_create_time = _read_pid_file(pid_file)
        process = psutil.Process(pid)
        if expected_create_time is not None:
            # Allow slight drift in floating point representation
            if abs(process.create_time() - expected_create_time) > 0.5:
                raise psutil.NoSuchProcess(pid)

        return True
    except (ValueError, psutil.Error, OSError):
        # Process doesn't exist or PID file is invalid
        pid_file.unlink(missing_ok=True)
        return False


def save_pid():

    pid_file = get_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    process = psutil.Process(os.getpid())
    payload = f"{process.pid}:{process.create_time()}"
    with open(pid_file, "w") as f:
        f.write(payload)


def remove_pid():

    pid_file = get_pid_file()
    pid_file.unlink(missing_ok=True)


@click.group()
@click.version_option(version="0.1.0")
def main():

    pass


@main.command()
@click.option("--fps", type=float, help="Frames per second to capture")
def start(fps: Optional[float]):

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
    
    # Lazy import heavy dependencies only when needed
    from .pipeline import ProcessingPipeline
    
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
            console.print("[green]✓[/green] Press Ctrl+C to stop")
            
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

    if not is_running():
        console.print("[yellow]Service is not running[/yellow]")
        return

    pid_file = get_pid_file()
    try:
        pid, _ = _read_pid_file(pid_file)
    except (OSError, ValueError):
        console.print("[red]PID file is corrupted or missing[/red]")
        remove_pid()
        return
    
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
@click.option("--reranker", is_flag=True, help="Use AI reranking for better relevance (requires FlagEmbedding)")
def query(query: str, app: Optional[str], from_date: Optional[str], to_date: Optional[str], limit: int, semantic: bool, reranker: bool):

    console.print(f"[cyan]Searching for:[/cyan] {query}")
    
    # Parse dates
    start_timestamp = None
    end_timestamp = None
    
    if from_date:
        try:
            dt = datetime.strptime(from_date, "%Y-%m-%d")
            start_timestamp = int(dt.timestamp())
        except ValueError:
            console.print("[red]Invalid from date format. Use YYYY-MM-DD[/red]")
            return
    
    if to_date:
        try:
            dt = datetime.strptime(to_date, "%Y-%m-%d")
            end_timestamp = int(dt.timestamp())
        except ValueError:
            console.print("[red]Invalid to date format. Use YYYY-MM-DD[/red]")
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
                # Lazy import heavy dependencies only when needed
                from .embeddings import EmbeddingService
                
                embedding_service = EmbeddingService()
                matches = embedding_service.search(
                    query=query,
                    limit=limit,
                    app_filter=app,
                    rerank=reranker,  # Enable reranking if flag is set
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
        
        # Generate AI answer from search results if semantic search
        if semantic and display_results:
            try:
                import os
                from openai import OpenAI
                
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                
                # Prepare enhanced context from search results
                context_items = []
                apps_seen = set()
                
                # Sanitize function to avoid problematic control chars for LLMs
                def _sanitize_text(s: str) -> str:

                    return "".join(
                        ch if (
                            ch == "\n" or 32 <= ord(ch) <= 126 or (ord(ch) >= 160 and ord(ch) not in (0xFFFF, 0xFFFE))
                        ) else " "
                        for ch in s
                    )
                
                for i, result in enumerate(display_results[:40]):  # limit context size for reliability
                    ts = datetime.fromtimestamp(result["timestamp"])
                    app = result.get("app_name", "Unknown")
                    window = result.get("window_title", "")
                    text = result.get("text", "").strip()
                    
                    if not text:
                        continue
                    
                    apps_seen.add(app)
                    relevance = "HIGH" if i < 5 else "MEDIUM" if i < 15 else "LOW"
                    text = _sanitize_text(" ".join(text.split()))[:300]  # Clean and limit
                    
                    context_items.append(f"""[RELEVANCE: {relevance}]
Time: {ts.strftime('%Y-%m-%d %H:%M:%S')}
Application: {app}
Window: {window}
Content:
{text}""")
                
                context_text = ("\n\n" + "=" * 50 + "\n\n").join(context_items)
                apps_summary = f"Applications involved: {', '.join(sorted([a for a in apps_seen if isinstance(a, str) and a]))}"
                
                # Generate answer using Responses API (preferred)
                response = client.responses.create(
                    model="gpt-5",
                    instructions=(
                        "You are an expert assistant analyzing computer activity through OCR text. "
                        "You see the ACTUAL content from the user's screen - code, commands, documents, web pages, etc. "
                        "Provide specific, actionable answers based on this evidence."
                    ),
                    input=(
                        f"Based on my screen activity, please answer: {query}\n\n"
                        f"{apps_summary}\n\n"
                        f"OCR Text from my screen (organized by relevance):\n{context_text}\n\n"
                        "Provide a specific, detailed answer. Reference the actual text you see. "
                        "If you notice patterns or workflows, describe them. Include file names, commands, or code changes when relevant."
                    ),
                    max_output_tokens=2000,
                )
                
                answer = getattr(response, "output_text", None)
                finish_reason = getattr(response, "status", None)
                
                # Display AI answer prominently
                console.print("\n[bold cyan]🤖 AI Answer:[/bold cyan]")
                answer_panel = Panel(
                    answer or "",
                    style="cyan",
                    border_style="cyan",
                    padding=(1, 2),
                )
                console.print(answer_panel)
                if not answer or len(answer.strip()) == 0:
                    console.print(f"[yellow]Empty answer (finish_reason={finish_reason}). Retrying with condensed context...[/yellow]")
                    condensed_items = []
                    for j, result in enumerate(display_results[:10]):
                        ts2 = datetime.fromtimestamp(result["timestamp"])
                        app2 = result.get("app_name", "Unknown")
                        window2 = result.get("window_title", "")
                        text2 = result.get("text", "").strip()
                        if not text2:
                            continue
                        text2 = _sanitize_text(" ".join(text2.split()))[:200]
                        condensed_items.append(f"[{ts2.strftime('%Y-%m-%d %H:%M:%S')}] {app2} • {window2}\n{text2}")
                    condensed_context = "\n\n".join(condensed_items)
                    try:
                        response2 = client.responses.create(
                            model="gpt-5",
                            instructions=(
                                "Answer succinctly using the following short OCR snippets from the user's screen."
                            ),
                            input=f"Question: {query}\n\nEvidence:\n{condensed_context}",
                            max_output_tokens=600,
                        )
                        answer2 = getattr(response2, "output_text", None)
                        finish_reason2 = getattr(response2, "status", None)
                        console.print(Panel(answer2 or "", style="cyan", border_style="cyan", padding=(1, 2)))
                        if not answer2 or len(answer2.strip()) == 0:
                            console.print(f"[yellow]Still empty after retry (finish_reason={finish_reason2}).[/yellow]")
                    except Exception as retry_err:
                        console.print(f"[yellow]Retry failed: {retry_err}[/yellow]")
                console.print("")  # Space before results
                
            except Exception as e:
                console.print(f"[yellow]Could not generate AI answer: {e}[/yellow]\n")
        
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
@click.option("--date", help="Date to convert (YYYY-MM-DD). If not provided, converts yesterday.")
@click.option("--keep-frames", is_flag=True, help="Keep original frames after conversion")
def convert_to_video(date: Optional[str], keep_frames: bool):

    from datetime import datetime, timedelta
    from .video.simple_video_capture import VideoConverter
    
    # Parse date or use yesterday
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
            return
    else:
        target_date = datetime.now() - timedelta(days=1)
    
    console.print(f"[cyan]Converting frames from {target_date.strftime('%Y-%m-%d')} to H.264 video...[/cyan]")
    
    # Create converter
    config = Config()
    if keep_frames:
        config.set("video.delete_frames_after_conversion", False)
    else:
        config.set("video.delete_frames_after_conversion", True)
    
    converter = VideoConverter(config)
    
    # Check ffmpeg
    if not converter._check_ffmpeg_available():
        console.print("[red]ffmpeg is not installed. Install with: brew install ffmpeg[/red]")
        return
    
    # Convert
    async def do_conversion():

        result = await converter.convert_day_to_video(target_date)
        if result:
            console.print(f"[green]✓ Video created: {result}[/green]")
            if not keep_frames:
                console.print("[yellow]Original frames deleted to save space[/yellow]")
        else:
            console.print("[red]✗ Conversion failed[/red]")
    
    try:
        asyncio.run(do_conversion())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@main.command()
def health():

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
    try:
        import psutil
        config = Config()
        frames_dir = config.get_frames_dir()
        # Create directory if it doesn't exist
        frames_dir.mkdir(parents=True, exist_ok=True)
        disk = psutil.disk_usage(str(frames_dir))
        free_gb = disk.free / (1024 ** 3)
        
        if free_gb > config.get("capture.min_free_space_gb", 10):
            checks.append(("Disk Space", f"✓ {free_gb:.1f} GB free", "green"))
        else:
            checks.append(("Disk Space", f"✗ Only {free_gb:.1f} GB free", "red"))
    except Exception as e:
        checks.append(("Disk Space", f"✗ Error: {e}", "red"))
    
    # Display results
    table = Table(title="Health Check")
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    
    for component, status, color in checks:
        table.add_row(component, f"[{color}]{status}[/{color}]")
    
    console.print(table)


@main.command()
@click.option("--port", default=8501, show_default=True, type=int)
def ui(port: int):

    import subprocess
    import sys
    
    # Get path to streamlit app
    app_path = Path(__file__).parent / "ui" / "streamlit_app.py"
    
    if not app_path.exists():
        console.print(f"[red]Streamlit app not found at {app_path}[/red]")
        return
    
    console.print(f"[green]Launching Second Brain UI on port {port}...[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    
    try:
        # Launch streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(app_path),
            "--server.port", str(port),
            "--server.headless", "false",
        ])
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down UI...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error launching UI: {e}[/red]")
        console.print("[yellow]Make sure streamlit is installed: pip install streamlit[/yellow]")


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--no-open", is_flag=True, help="Do not open the browser automatically")
def timeline(host: str, port: int, no_open: bool):

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
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def reset(yes: bool):

    import shutil
    
    console.print("[yellow]Second Brain Reset[/yellow]\n")
    console.print("This will delete ALL captured data including:")
    console.print("  • Screenshots and frames")
    console.print("  • SQLite database")
    console.print("  • Video files")
    console.print("  • Embeddings")
    console.print("  • Logs")
    console.print("\n[red]WARNING: This action cannot be undone![/red]\n")
    
    # Prompt for confirmation unless --yes flag is used
    if not yes:
        confirmation = click.prompt(
            "Type 'yes' to confirm reset",
            type=str,
            default="no"
        )
        if confirmation.lower() != "yes":
            console.print("[yellow]Reset cancelled.[/yellow]")
            return
    
    console.print("\n[yellow]Checking if service is running...[/yellow]")
    
    # Stop service if running
    if is_running():
        console.print("[yellow]Stopping Second Brain service...[/yellow]")
        pid_file = get_pid_file()
        try:
            pid, _ = _read_pid_file(pid_file)
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to stop
            import time
            for _ in range(10):
                if not is_running():
                    break
                time.sleep(0.5)
            
            if is_running():
                console.print("[red]Warning: Service may still be running[/red]")
            else:
                console.print("[green]✓[/green] Service stopped")
        except Exception as e:
            console.print(f"[yellow]Warning: {e}[/yellow]")
            remove_pid()
    else:
        console.print("[green]✓[/green] Service not running")
    
    console.print()
    
    # Get data directory
    config = Config()
    data_dir = config.get_data_dir()
    
    if not data_dir.exists():
        console.print("[yellow]Data directory does not exist, nothing to remove[/yellow]")
        console.print("[green]✓ Reset complete![/green]")
        return
    
    console.print(f"[yellow]Removing data directory: {data_dir}[/yellow]")
    
    # Remove specific subdirectories
    dirs_to_remove = [
        ("frames", config.get_frames_dir()),
        ("videos", data_dir / "videos"),
        ("database", config.get_database_dir()),
        ("embeddings", config.get_embeddings_dir()),
        ("logs", config.get_logs_dir()),
    ]
    
    for name, dir_path in dirs_to_remove:
        if dir_path.exists():
            console.print(f"  • Removing {name}...")
            try:
                shutil.rmtree(dir_path)
            except Exception as e:
                console.print(f"[red]    Error removing {name}: {e}[/red]")
    
    # Remove PID file
    pid_file = get_pid_file()
    if pid_file.exists():
        console.print("  • Removing PID file...")
        pid_file.unlink()
    
    console.print("\n[green]✓ Reset complete![/green]")
    console.print("\nYou can now start fresh with: [cyan]second-brain start[/cyan]")


if __name__ == "__main__":
    main()
