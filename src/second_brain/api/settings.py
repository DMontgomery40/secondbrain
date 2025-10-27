"""Settings API: expose and update all configuration via HTTP."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import psutil
import httpx
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..config import Config
from ..database import Database


router = APIRouter(prefix="/api/settings", tags=["settings"])
config = Config()


def _pid_file() -> Path:
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "second-brain"
        / "second-brain.pid"
    )


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _restart_capture_service() -> None:
    pidf = _pid_file()
    if pidf.exists():
        try:
            pid = int(pidf.read_text().strip())
        except Exception:
            pid = None  # type: ignore
        if pid and _is_running(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            deadline = time.time() + 10
            while time.time() < deadline:
                if not _is_running(pid):
                    break
                time.sleep(0.2)

    # Relaunch using current venv executable
    exe = Path(sys.executable).with_name("second-brain")
    try:
        subprocess.Popen([str(exe), "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        subprocess.Popen(["second-brain", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _flatten_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten_dict(v, key))
        else:
            out[key] = v
    return out


@router.get("/all")
async def get_all_settings() -> Dict[str, Any]:
    """Return all settings as nested JSON with sensible defaults."""
    db_path = str(config.get_database_dir() / "memory.db")
    frames_dir = str(config.get_frames_dir())
    return {
        "capture": {
            "fps": config.get("capture.fps", 1),
            "max_disk_usage_gb": config.get("capture.max_disk_usage_gb", 100),
            "min_free_space_gb": config.get("capture.min_free_space_gb", 10),
            "buffer_enabled": config.get("capture.buffer_enabled", False),
            "buffer_duration": config.get("capture.buffer_duration", 30),
        },
        "ocr": {
            "engine": config.get("ocr.engine", "openai"),
            "model": config.get("ocr.model", "gpt-5"),
            "rate_limit_rpm": config.get("ocr.rate_limit_rpm", 50),
            "deepseek_docker": config.get("ocr.deepseek_docker", True),
            "deepseek_docker_url": config.get("ocr.deepseek_docker_url", "http://localhost:8001"),
            "deepseek_mode": config.get("ocr.deepseek_mode", "optimal"),
            "batch_size": config.get("ocr.batch_size", 5),
        },
        "embeddings": {
            "enabled": config.get("embeddings.enabled", True),
            "model": config.get("embeddings.model", "sentence-transformers/all-MiniLM-L6-v2"),
        },
        "storage": {
            "database_path": db_path,
            "screenshots_dir": frames_dir,
            "max_screenshots": config.get("storage.max_screenshots", 100000),
            "retention_days": config.get("storage.retention_days", 90),
        },
        "api": {
            "host": config.get("api.host", "127.0.0.1"),
            "port": config.get("api.port", 8000),
            "cors_enabled": config.get("api.cors_enabled", True),
        },
        "logging": {
            "level": config.get("logging.level", "INFO"),
            "file": config.get("logging.file", "capture.log"),
            "max_size_mb": config.get("logging.max_size_mb", 100),
        },
        "mcp": {
            "enabled": config.get("mcp.enabled", False),
            "port": config.get("mcp.port", 3000),
            "transport": config.get("mcp.transport", "streamable_http"),
        },
    }


@router.post("/update")
async def update_settings(settings: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Update any settings, persist, and restart services where needed."""
    if not isinstance(settings, dict):
        raise HTTPException(status_code=400, detail="Invalid settings payload")

    for category, values in settings.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            config.set(f"{category}.{key}", value)
    config.save()

    flat = _flatten_dict(settings)
    if "ocr.engine" in flat or "ocr.model" in flat:
        _restart_capture_service()
    if "capture.fps" in flat:
        _restart_capture_service()
    return {"status": "updated"}


@router.post("/reset")
async def reset_settings(payload: Dict[str, Any] = Body(None)) -> Dict[str, Any]:
    category = (payload or {}).get("category") if isinstance(payload, dict) else None
    if category:
        try:
            config.reset_category(category)
        except KeyError:
            raise HTTPException(status_code=400, detail="Unknown category")
    else:
        config.reset_all()
    return {"status": "reset"}


def _dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except Exception:
                pass
    return total


def _today_start_ts() -> int:
    now = datetime.now()
    start = datetime(year=now.year, month=now.month, day=now.day)
    return int(start.timestamp())


def _check_deepseek_health() -> bool:
    url = config.get("ocr.deepseek_docker_url", "http://localhost:8001")
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{url}/health")
            return r.status_code == 200
    except Exception:
        return False


@router.get("/stats")
async def get_system_stats() -> Dict[str, Any]:
    db = Database(config=config)
    stats = db.get_database_stats()
    db.close()

    frames_dir = config.get_frames_dir()
    screenshots = 0
    for root, _, files in os.walk(frames_dir):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                screenshots += 1

    frames_today = 0
    try:
        with Database(config=config) as db2:
            start = _today_start_ts()
            frames_today = len(db2.get_frames_by_timerange(start, int(time.time()), limit=100000))
    except Exception:
        frames_today = 0

    disk = psutil.disk_usage(str(frames_dir))
    return {
        "disk_usage_gb": round((disk.total - disk.free) / (1024 ** 3), 2),
        "database_size_mb": round((stats.get("database_size_bytes") or 0) / (1024 ** 2), 2),
        "screenshot_count": screenshots,
        "gpu_available": False,  # GPU detection optional; skip heavy deps
        "memory_usage_percent": psutil.virtual_memory().percent,
        "deepseek_docker_running": _check_deepseek_health(),
        "frames_processed_today": frames_today,
    }


@router.post("/maintenance/compact-db")
async def compact_database() -> Dict[str, Any]:
    with Database(config=config) as db:
        db.vacuum()
    return {"status": "ok"}


@router.post("/maintenance/clear-screenshots")
async def clear_screenshots(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    retention_days = int((payload or {}).get("retention_days", config.get("storage.retention_days", 90)))
    cutoff = int(time.time()) - retention_days * 86400
    # Delete DB records
    with Database(config=config) as db:
        db.cleanup_old_frames(retention_days)
    # Best-effort file cleanup by date folders
    frames_dir = config.get_frames_dir()
    removed = 0
    for year_dir in frames_dir.glob("*/"):
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.glob("*/"):
            if not month_dir.is_dir():
                continue
            for day_dir in month_dir.glob("*/"):
                if not day_dir.is_dir():
                    continue
                try:
                    ts = int(time.mktime(time.strptime(f"{year_dir.name}-{month_dir.name}-{day_dir.name}", "%Y-%m-%d")))
                except Exception:
                    ts = 0
                if ts and ts < cutoff:
                    for p in day_dir.glob("**/*"):
                        if p.is_file():
                            try:
                                p.unlink()
                                removed += 1
                            except Exception:
                                pass
    return {"status": "ok", "removed_files": removed}


@router.get("/logs")
async def get_logs(file: str = Query("capture.log")):
    logs_dir = config.get_logs_dir()
    path = logs_dir / file
    if not path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    try:
        content = path.read_text(errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return PlainTextResponse(content)

