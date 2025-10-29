"""FastAPI server exposing timeline and query APIs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Body
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
        start: Optional[int] = Query(
            None, description="Start timestamp (unix seconds)"
        ),
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
                    "iso_timestamp": datetime.fromtimestamp(
                        frame["timestamp"]
                    ).isoformat(),
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
            (
                "capture.max_disk_usage_gb",
                settings.get("capture", {}).get("max_disk_usage_gb"),
            ),
            (
                "capture.min_free_space_gb",
                settings.get("capture", {}).get("min_free_space_gb"),
            ),
            ("ocr.batch_size", ocr.get("batch_size")),
            ("ocr.max_retries", ocr.get("max_retries")),
            ("ocr.timeout_seconds", ocr.get("timeout_seconds")),
            ("ocr.buffer_duration", ocr.get("buffer_duration")),
            ("ocr.mlx_max_tokens", ocr.get("mlx_max_tokens")),
            ("ocr.mlx_temperature", ocr.get("mlx_temperature")),
            ("ocr.mlx_repetition_penalty", ocr.get("mlx_repetition_penalty")),
            (
                "storage.retention_days",
                settings.get("storage", {}).get("retention_days"),
            ),
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

        return {
            "status": "ok",
            "message": "Settings updated. Some changes may require service restart.",
        }

    @app.post("/api/settings/reset")
    def reset_settings(category: str = None):
        """Reset settings to defaults.

        Args:
            category: Category to reset (e.g., 'capture'), or None to reset all
        """
        if category:
            config.reset_category(category)
            return {
                "status": "ok",
                "message": f"Category '{category}' reset to defaults",
            }
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
                    if item.suffix in [".png", ".jpg", ".jpeg"]:
                        screenshot_count += 1

        # Check DeepSeek MLX availability (importable)
        try:
            importlib.import_module("mlx_vlm")
            deepseek_mlx_available = True
        except Exception:
            deepseek_mlx_available = False

        return {
            "database_size_mb": round(
                db_stats.get("database_size_bytes", 0) / (1024 * 1024), 2
            ),
            "screenshots_size_gb": round(total_size / (1024 * 1024 * 1024), 2),
            "screenshot_count": screenshot_count,
            "frames_in_db": db_stats.get("frame_count", 0),
            "text_blocks": db_stats.get("text_block_count", 0),
            "memory_usage_percent": round(psutil.virtual_memory().percent, 1),
            "disk_free_gb": round(
                psutil.disk_usage(str(config.get_data_dir())).free
                / (1024 * 1024 * 1024),
                2,
            ),
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
        if engine not in ["apple", "deepseek"]:
            raise HTTPException(
                status_code=400, detail="Invalid engine. Must be 'apple' or 'deepseek'"
            )

        # Update config and save it
        config.set("ocr.engine", engine)
        config.save()

        return {
            "status": "ok",
            "engine": engine,
            "message": f"OCR engine switched to {engine}. Restart the capture service for changes to take effect.",
        }

    @app.get("/api/summaries")
    def get_summaries(
        date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
        summary_type: Optional[str] = Query(
            None, description="Type of summary: hourly, daily, or session"
        ),
        db: Database = Depends(get_db),
    ):
        """Get AI-generated summaries for a date or type."""
        if date:
            from datetime import datetime as dt

            try:
                date_obj = dt.strptime(date, "%Y-%m-%d")
                summaries = db.get_summaries_for_day(date_obj)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
                )
        elif summary_type:
            latest = db.get_latest_summary(summary_type)
            summaries = [latest] if latest else []
        else:
            # Get all recent summaries (last 7 days)
            from datetime import datetime as dt, timedelta

            end_date = dt.now()
            start_date = end_date - timedelta(days=7)

            # Query summaries in date range
            cursor = db.conn.execute(
                """
                SELECT summary_id, start_timestamp, end_timestamp, summary_type,
                       summary_text, frame_count, app_names, created_at
                FROM summaries
                WHERE start_timestamp >= ? AND start_timestamp <= ?
                ORDER BY start_timestamp DESC
            """,
                (int(start_date.timestamp()), int(end_date.timestamp())),
            )

            summaries = []
            for row in cursor.fetchall():
                import json

                summaries.append(
                    {
                        "summary_id": row[0],
                        "start_timestamp": row[1],
                        "end_timestamp": row[2],
                        "summary_type": row[3],
                        "summary_text": row[4],
                        "frame_count": row[5],
                        "app_names": json.loads(row[6]) if row[6] else [],
                        "created_at": row[7],
                    }
                )

        return {"summaries": summaries}

    @app.get("/api/stats/daily")
    def get_daily_stats(
        date: str = Query(..., description="Date in YYYY-MM-DD format"),
        db: Database = Depends(get_db),
    ):
        """Get daily statistics for frames, text blocks, and apps."""
        from datetime import datetime as dt

        try:
            date_obj = dt.strptime(date, "%Y-%m-%d")
            start_ts = int(date_obj.replace(hour=0, minute=0, second=0).timestamp())
            end_ts = int(date_obj.replace(hour=23, minute=59, second=59).timestamp())
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
            )

        # Get frame count
        cursor = db.conn.execute(
            """
            SELECT COUNT(*) FROM frames
            WHERE timestamp >= ? AND timestamp <= ?
        """,
            (start_ts, end_ts),
        )
        frame_count = cursor.fetchone()[0]

        # Get text block count and total characters
        cursor = db.conn.execute(
            """
            SELECT COUNT(*), SUM(LENGTH(text))
            FROM text_blocks tb
            JOIN frames f ON tb.frame_id = f.frame_id
            WHERE f.timestamp >= ? AND f.timestamp <= ?
        """,
            (start_ts, end_ts),
        )
        row = cursor.fetchone()
        text_block_count = row[0]
        total_characters = row[1] or 0

        # Get unique app count
        cursor = db.conn.execute(
            """
            SELECT COUNT(DISTINCT app_bundle_id) FROM frames
            WHERE timestamp >= ? AND timestamp <= ?
        """,
            (start_ts, end_ts),
        )
        app_count = cursor.fetchone()[0]

        return {
            "date": date,
            "frame_count": frame_count,
            "text_block_count": text_block_count,
            "total_characters": total_characters,
            "app_count": app_count,
        }

    @app.post("/api/search")
    def search(
        payload: dict = Body(...),
        db: Database = Depends(get_db),
    ):
        """Search text blocks (FTS) or semantic embeddings.
        payload keys: query (str), limit (int), app_bundle_id (str|None), semantic (bool), reranker (bool),
                      start (int|None), end (int|None)
        """
        query: str = payload.get("query", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        limit: int = int(payload.get("limit", 10))
        app_bundle_id = payload.get("app_bundle_id")
        semantic = bool(payload.get("semantic", False))
        reranker = bool(payload.get("reranker", False))
        start_timestamp = payload.get("start")
        end_timestamp = payload.get("end")

        results = []
        if semantic:
            try:
                from ..embeddings import EmbeddingService  # lazy import heavy deps

                embedding_service = EmbeddingService()
                matches = embedding_service.search(
                    query=query,
                    limit=limit,
                    app_filter=app_bundle_id,
                    rerank=reranker,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                )
                for match in matches:
                    frame = db.get_frame(match["frame_id"]) or {}
                    block = db.get_text_block(match["block_id"]) or {}
                    if not block:
                        continue
                    results.append(
                        {
                            "frame_id": match["frame_id"],
                            "block_id": match["block_id"],
                            "timestamp": frame.get("timestamp"),
                            "window_title": frame.get("window_title") or "Untitled",
                            "app_name": frame.get("app_name") or "Unknown",
                            "text": block.get("text", ""),
                            "score": 1 - match.get("distance", 0.0)
                            if match.get("distance") is not None
                            else None,
                            "method": "semantic",
                        }
                    )
            except Exception as exc:
                raise HTTPException(
                    status_code=500, detail=f"semantic search failed: {exc}"
                )
        else:
            rows = db.search_text(
                query=query,
                app_filter=app_bundle_id,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                limit=limit,
            )
            for row in rows:
                results.append(
                    {
                        "frame_id": row.get("frame_id"),
                        "block_id": row.get("block_id"),
                        "timestamp": row.get("timestamp"),
                        "window_title": row.get("window_title") or "Untitled",
                        "app_name": row.get("app_name") or "Unknown",
                        "text": row.get("text", ""),
                        "score": row.get("score"),
                        "method": "fts",
                    }
                )

        return {"results": results}

    @app.post("/api/ask")
    def ask(
        payload: dict = Body(...),
        db: Database = Depends(get_db),
    ):
        """Generate an AI answer from search results.
        payload keys: query (str), limit (int), app_bundle_id (str|None), semantic (bool), reranker (bool),
                      start (int|None), end (int|None)
        """
        query: str = payload.get("query", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        limit: int = int(payload.get("limit", 10))
        app_bundle_id = payload.get("app_bundle_id")
        semantic = bool(payload.get("semantic", True))
        reranker = bool(payload.get("reranker", False))
        start_timestamp = payload.get("start")
        end_timestamp = payload.get("end")

        # Reuse search endpoint logic
        search_response = search(
            {
                "query": query,
                "limit": limit,
                "app_bundle_id": app_bundle_id,
                "semantic": semantic,
                "reranker": reranker,
                "start": start_timestamp,
                "end": end_timestamp,
            },
            db,
        )
        results = search_response["results"]
        if not results:
            return {"answer": None, "results": []}

        # Prepare context with sanitization
        def _sanitize(s: str) -> str:
            return "".join(
                ch
                if (
                    ch == "\n"
                    or 32 <= ord(ch) <= 126
                    or (ord(ch) >= 160 and ord(ch) not in (0xFFFF, 0xFFFE))
                )
                else " "
                for ch in s
            )

        context_items = []
        apps_seen = set()
        for i, r in enumerate(results[:40]):
            ts = datetime.fromtimestamp(r["timestamp"]) if r.get("timestamp") else None
            apps_seen.add(r.get("app_name", "Unknown"))
            text = _sanitize(" ".join((r.get("text") or "").split()))[:300]
            context_items.append(
                f"[RELEVANCE: {'HIGH' if i < 5 else 'MEDIUM' if i < 15 else 'LOW'}]\n"
                f"Time: {ts.strftime('%Y-%m-%d %H:%M:%S') if ts else 'Unknown'}\n"
                f"Application: {r.get('app_name','Unknown')}\n"
                f"Window: {r.get('window_title','')}\n"
                f"Content:\n{text}"
            )

        context_text = ("\n\n" + "=" * 50 + "\n\n").join(context_items)
        apps_summary = f"Applications involved: {', '.join(sorted([a for a in apps_seen if isinstance(a, str) and a]))}"

        # Call OpenAI server-side so the browser never needs the API key
        try:
            import os
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured on server")
            client = OpenAI(api_key=api_key)

            model = "gpt-5"
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "developer",
                        "content": "You are an expert assistant analyzing OCR from screen captures. Be specific and cite evidence.",
                    },
                    {
                        "role": "user",
                        "content": f"Based on my screen activity, please answer: {query}\n\n{apps_summary}\n\nOCR Text (by relevance):\n{context_text}\n\nAnswer directly and cite snippets.",
                    },
                ],
                text={"verbosity": "medium"},
            )
            # Extract text from response.output
            import logging

            logger = logging.getLogger(__name__)

            answer = None
            if hasattr(response, "output") and response.output:
                for output_item in response.output:
                    if hasattr(output_item, "content"):
                        # content is a list of content items, iterate through them
                        if isinstance(output_item.content, list):
                            for content_item in output_item.content:
                                if hasattr(content_item, "text"):
                                    answer = content_item.text
                                    break
                        else:
                            # Fallback if content is a string directly
                            answer = str(output_item.content)
                        if answer:
                            break
            if not answer:
                # Log the response structure for debugging
                logger.warning(
                    f"Failed to extract answer from response. Response structure: {response}"
                )
                logger.warning(
                    f"Response output: {response.output if hasattr(response, 'output') else 'No output attr'}"
                )
                # Fallback to string representation if structure is different
                if hasattr(response, "output") and response.output is not None:
                    answer = str(response.output)
                else:
                    answer = "Unable to extract answer from AI response. Please check server logs."
            if not answer or not answer.strip():
                # condensed retry
                condensed = []
                for r in results[:10]:
                    ts = (
                        datetime.fromtimestamp(r["timestamp"])
                        if r.get("timestamp")
                        else None
                    )
                    t = _sanitize(" ".join((r.get("text") or "").split()))[:200]
                    condensed.append(
                        f"[{ts.strftime('%Y-%m-%d %H:%M:%S') if ts else 'Unknown'}] {r.get('app_name','Unknown')} • {r.get('window_title','')}\n{t}"
                    )
                condensed_ctx = "\n\n".join(condensed)
                response2 = client.responses.create(
                    model=model,
                    input=[
                        {
                            "role": "developer",
                            "content": "Answer succinctly using provided short OCR snippets.",
                        },
                        {
                            "role": "user",
                            "content": f"Question: {query}\n\nEvidence:\n{condensed_ctx}",
                        },
                    ],
                    text={"verbosity": "low"},
                )
                # Extract text from retry response
                answer = None
                if hasattr(response2, "output") and response2.output:
                    for output_item in response2.output:
                        if hasattr(output_item, "content"):
                            # content is a list of content items, iterate through them
                            if isinstance(output_item.content, list):
                                for content_item in output_item.content:
                                    if hasattr(content_item, "text"):
                                        answer = content_item.text
                                        break
                            else:
                                # Fallback if content is a string directly
                                answer = str(output_item.content)
                            if answer:
                                break
                if not answer:
                    logger.warning(
                        f"Failed to extract answer from retry response. Response structure: {response2}"
                    )
                    logger.warning(
                        f"Response2 output: {response2.output if hasattr(response2, 'output') else 'No output attr'}"
                    )
                    if hasattr(response2, "output") and response2.output is not None:
                        answer = str(response2.output)
                    else:
                        answer = "Unable to extract answer from AI response after retry. Please check server logs."
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"AI answer failed: {exc}")

        return {"answer": answer, "results": results}

    # Serve built React UI if present
    # server.py lives at src/second_brain/api/server.py → repo root is parents[3]
    ui_dist = Path(__file__).resolve().parents[3] / "web" / "timeline" / "dist"
    if ui_dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(ui_dist), html=True),
            name="timeline_ui",
        )

    return app


app = create_app()
