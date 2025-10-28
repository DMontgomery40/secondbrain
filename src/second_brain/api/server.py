"""FastAPI server exposing timeline and query APIs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..config import Config, DEFAULT_CONFIG
from ..database import Database

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

    @app.get("/api/settings/all")
    def get_all_settings():
        """Get ALL settings as nested JSON."""
        settings = config.get_all()

        # Add computed paths
        settings["_paths"] = {
            "database": str(config.get_database_dir() / "memory.db"),
            "screenshots": str(config.get_frames_dir()),
            "embeddings": str(config.get_embeddings_dir()),
            "logs": str(config.get_logs_dir()),
            "config": str(config.config_path),
        }

        return settings

    @app.get("/api/settings/defaults")
    def get_default_settings():
        """Return the built-in default settings (source of truth for UI defaults)."""
        return DEFAULT_CONFIG

    @app.post("/api/settings/update")
    def update_settings(settings: dict):
        """Update multiple settings at once with basic validation."""
        if not isinstance(settings, dict):
            raise HTTPException(status_code=400, detail="Invalid payload")

        field_errors: dict[str, str] = {}

        def add_error(path: str, msg: str) -> None:
            field_errors[path] = msg

        # Basic validations for known fields
        ocr = settings.get("ocr", {}) if isinstance(settings.get("ocr"), dict) else {}
        engine = ocr.get("engine")
        if engine is not None and engine not in ["apple", "deepseek"]:
            add_error("ocr.engine", "must be 'apple' or 'deepseek'")

        rec_level = ocr.get("recognition_level")
        if rec_level is not None and rec_level not in ["fast", "accurate"]:
            add_error("ocr.recognition_level", "must be 'fast' or 'accurate'")

        for num_key in [
            ("capture.fps", settings.get("capture", {}).get("fps")),
            ("capture.quality", settings.get("capture", {}).get("quality")),
            ("capture.max_disk_usage_gb", settings.get("capture", {}).get("max_disk_usage_gb")),
            ("capture.min_free_space_gb", settings.get("capture", {}).get("min_free_space_gb")),
            ("ocr.batch_size", ocr.get("batch_size")),
            ("ocr.max_retries", ocr.get("max_retries")),
            ("ocr.timeout_seconds", ocr.get("timeout_seconds")),
            ("ocr.buffer_duration", ocr.get("buffer_duration")),
            ("ocr.mlx_max_tokens", ocr.get("mlx_max_tokens")),
            ("ocr.mlx_temperature", ocr.get("mlx_temperature")),
            ("storage.retention_days", settings.get("storage", {}).get("retention_days")),
        ]:
            path, value = num_key
            if value is not None and not isinstance(value, (int, float)):
                add_error(path, "must be a number")

        if field_errors:
            raise HTTPException(status_code=422, detail={"errors": field_errors})

        # Persist settings
        for category, values in settings.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    config.set(f"{category}.{key}", value)

        config.save()

        return {"status": "ok", "message": "Settings updated. Some changes may require service restart."}

    @app.post("/api/settings/reset")
    def reset_settings(category: str = None):
        """Reset settings to defaults.

        Args:
            category: Category to reset (e.g., 'capture'), or None to reset all
        """
        if category:
            config.reset_category(category)
            return {"status": "ok", "message": f"Category '{category}' reset to defaults"}
        else:
            config.reset_all()
            return {"status": "ok", "message": "All settings reset to defaults"}

    @app.get("/api/settings/stats")
    def get_system_stats(db: Database = Depends(get_db)):
        """Get system statistics for display in settings."""
        import psutil
        import importlib

        # Get database stats
        db_stats = db.get_database_stats()

        # Get disk usage
        frames_dir = config.get_frames_dir()
        total_size = 0
        screenshot_count = 0
        if frames_dir.exists():
            for item in frames_dir.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
                    if item.suffix in ['.png', '.jpg', '.jpeg']:
                        screenshot_count += 1

        # Check DeepSeek MLX availability (importable)
        try:
            importlib.import_module("mlx_vlm")
            deepseek_mlx_available = True
        except Exception:
            deepseek_mlx_available = False

        return {
            "database_size_mb": round(db_stats.get("database_size_bytes", 0) / (1024 * 1024), 2),
            "screenshots_size_gb": round(total_size / (1024 * 1024 * 1024), 2),
            "screenshot_count": screenshot_count,
            "frames_in_db": db_stats.get("frame_count", 0),
            "text_blocks": db_stats.get("text_block_count", 0),
            "memory_usage_percent": round(psutil.virtual_memory().percent, 1),
            "disk_free_gb": round(psutil.disk_usage(str(config.get_data_dir())).free / (1024 * 1024 * 1024), 2),
            "deepseek_mlx_available": deepseek_mlx_available,
        }

    @app.get("/api/settings/ocr-engine")
    def get_ocr_engine():
        """Get current OCR engine setting."""
        engine = config.get("ocr.engine", "apple")
        return {"engine": engine}

    @app.post("/api/settings/ocr-engine")
    def set_ocr_engine(engine: str):
        """Switch OCR engine on the fly.

        Args:
            engine: Either 'apple' or 'deepseek'
        """
        if engine not in ['apple', 'deepseek']:
            raise HTTPException(status_code=400, detail="Invalid engine. Must be 'apple' or 'deepseek'")

        # Update config and save it
        config.set('ocr.engine', engine)
        config.save()

        return {"status": "ok", "engine": engine, "message": f"OCR engine switched to {engine}. Restart the capture service for changes to take effect."}

    ui_dist = (
        Path(__file__).resolve().parents[3] / "web" / "timeline" / "dist"
    )
    if ui_dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(ui_dist), html=True),
            name="timeline_ui",
        )

    return app


app = create_app()
