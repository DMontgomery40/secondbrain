"""FastAPI server exposing timeline and query APIs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..config import Config
from ..database import Database
from .settings import router as settings_router

config = Config()


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Second Brain API",
        description="Local API for timeline visualization and search",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Settings API
    app.include_router(settings_router)

    frames_dir = config.get_frames_dir()
    frames_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/frames", StaticFiles(directory=str(frames_dir)), name="frames")

    def get_db() -> Generator[Database, None, None]:
        db = Database(config=config)
        try:
            yield db
        finally:
            db.close()

    @app.get("/api/frames")
    def list_frames(
        limit: int = Query(200, ge=1, le=1000),
        app_bundle_id: Optional[str] = Query(None),
        start: Optional[int] = Query(None, description="Start timestamp (unix seconds)"),
        end: Optional[int] = Query(None, description="End timestamp (unix seconds)"),
        db: Database = Depends(get_db),
    ):
        frames = db.get_frames(
            limit=limit,
            app_bundle_id=app_bundle_id,
            start_timestamp=start,
            end_timestamp=end,
        )
        response = []
        for frame in frames:
            response.append(
                {
                    **frame,
                    "iso_timestamp": datetime.fromtimestamp(frame["timestamp"]).isoformat(),
                    "screenshot_url": f"/frames/{frame['file_path']}",
                }
            )
        return {"frames": response}

    @app.get("/api/frames/{frame_id}")
    def get_frame(frame_id: str, db: Database = Depends(get_db)):
        frame = db.get_frame(frame_id)
        if not frame:
            raise HTTPException(status_code=404, detail="Frame not found")
        frame["iso_timestamp"] = datetime.fromtimestamp(frame["timestamp"]).isoformat()
        frame["screenshot_url"] = f"/frames/{frame['file_path']}"
        return frame

    @app.get("/api/frames/{frame_id}/text")
    def get_frame_text(frame_id: str, db: Database = Depends(get_db)):
        frame = db.get_frame(frame_id)
        if not frame:
            raise HTTPException(status_code=404, detail="Frame not found")
        blocks = db.get_text_blocks_by_frame(frame_id)
        return {"frame_id": frame_id, "blocks": blocks}

    @app.get("/api/apps")
    def list_apps(limit: int = Query(50, ge=1, le=200), db: Database = Depends(get_db)):
        stats = db.get_app_usage_stats(limit=limit)
        return {"apps": stats}

    def _get_pid_file() -> Path:
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "second-brain"
            / "second-brain.pid"
        )

    def _is_process_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _restart_capture_service() -> None:
        pid_file = _get_pid_file()
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
            except Exception:
                pid = None  # type: ignore
            if pid and _is_process_running(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
                # Wait up to 10 seconds for shutdown
                deadline = time.time() + 10
                while time.time() < deadline:
                    if not _is_process_running(pid):
                        break
                    time.sleep(0.2)

        # Start the service again in background using the same venv
        exe = Path(sys.executable).with_name("second-brain")
        try:
            subprocess.Popen([str(exe), "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            # As fallback, try system PATH
            subprocess.Popen(["second-brain", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @app.get("/api/settings/ocr-engine")
    def get_ocr_engine():
        return {"engine": config.get("ocr.engine", "openai")}

    @app.post("/api/settings/ocr-engine")
    def set_ocr_engine(payload: dict = Body(...)):
        engine = payload.get("engine") if isinstance(payload, dict) else None
        if engine not in ("openai", "deepseek"):
            raise HTTPException(status_code=400, detail="Invalid engine")
        # Update config
        config.set("ocr.engine", engine)
        config.save()
        # Restart capture service if running
        _restart_capture_service()
        return {"status": "ok", "engine": engine}

    ui_dist = (
        Path(__file__).resolve().parents[2] / "web" / "timeline" / "dist"
    )
    if ui_dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(ui_dist), html=True),
            name="timeline_ui",
        )

    return app


app = create_app()
