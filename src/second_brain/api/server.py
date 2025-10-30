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
    """
    Construct and configure the FastAPI application for Second Brain.

    ---agentspec
    what: |
      Builds a FastAPI app with CORS enabled, mounts the local frames directory
      as a static route, and registers all HTTP endpoints used by the UI:
      frame listing/detail, text retrieval, app stats, settings CRUD, system
      diagnostics, summaries, daily stats, full‑text/semantic search, and Q&A.
      Returns a fully configured FastAPI instance ready to be served.

    deps:
      calls:
        - second_brain.api.server.create_app.get_db()
        - fastapi.FastAPI
        - fastapi.middleware.cors.CORSMiddleware
        - fastapi.staticfiles.StaticFiles
        - second_brain.config.Config.get_frames_dir()
      called_by:
        - Module import (app = create_app())
      config_files: []
      environment: []

    why: |
      Centralizes API wiring in a single factory so tests and the CLI can
      instantiate the server consistently. Mounting the frames directory lets
      the UI fetch images without an additional file service.

    guardrails:
      - DO NOT remove CORS middleware; the local UI relies on cross‑origin
        access during development.
      - DO NOT mount frames outside of Config.get_frames_dir(); the UI builds
        URLs using this path.
      - DO NOT perform heavy work in this function; endpoint handlers should do
        IO to keep startup fast.

    changelog:
      - "2025-10-30: Added agentspec docstring describing server wiring"
    ---/agentspec
    """

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
        """
        FastAPI dependency that opens a Database connection and guarantees close.

        ---agentspec
        what: |
          Creates a Database using module‑level Config and yields it to request
          handlers. Ensures db.close() is called via finally to avoid leaks.

        deps:
          calls:
            - second_brain.database.Database
            - second_brain.database.Database.close
          called_by:
            - All endpoints using Depends(get_db)
          config_files: []
          environment: []

        why: |
          Keeps connection lifetime scoped to a single request, which is safest
          for SQLite and aligns with FastAPI dependency patterns.

        guardrails:
          - DO NOT cache the Database instance globally; SQLite connections are
            not process‑safe and can cause locking issues.
          - ALWAYS close the connection in finally.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
        """

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
        """
        List recent frames with optional filters and computed fields.

        ---agentspec
        what: |
          Queries frames from the database with optional filtering by
          app_bundle_id and timestamp range. Computes iso_timestamp (from unix
          seconds) and screenshot_url for each frame and returns a JSON object
          with a frames array.

        deps:
          calls:
            - Database.get_frames()
          called_by:
            - HTTP GET /api/frames
          config_files: []
          environment: []

        why: |
          The UI needs a lightweight list of frames enriched with derived
          fields. Computing these server‑side keeps client logic simple.

        guardrails:
          - DO NOT remove the limit constraint; returning unbounded results can
            exhaust memory.
          - ALWAYS return iso_timestamp and screenshot_url to keep the UI
            contract stable.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
        """
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
        """
        Get a single frame by id and enrich with derived fields.

        ---agentspec
        what: |
          Fetches one frame by frame_id, returning 404 if not found. Adds
          iso_timestamp and screenshot_url to the response object.

        deps:
          calls:
            - Database.get_frame()
          called_by:
            - HTTP GET /api/frames/{frame_id}

        why: |
          The UI needs per‑frame detail for overlays and preview panels.

        guardrails:
          - DO NOT change the 404 behavior; the UI distinguishes not‑found from
            empty content using the status code.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
        """

        frame = db.get_frame(frame_id)
        if not frame:
            raise HTTPException(status_code=404, detail="Frame not found")
        frame["iso_timestamp"] = datetime.fromtimestamp(frame["timestamp"]).isoformat()
        frame["screenshot_url"] = f"/frames/{frame['file_path']}"
        return frame

    @app.get("/api/frames/{frame_id}/text")
    def get_frame_text(frame_id: str, db: Database = Depends(get_db)):
        """
        Return OCR text blocks associated with a frame.

        ---agentspec
        what: |
          Retrieves frame metadata and its OCR text blocks. Returns 404 if the
          frame does not exist. On unexpected errors, logs a warning and returns
          an empty blocks list to avoid breaking the UI.

        deps:
          calls:
            - Database.get_frame()
            - Database.get_text_blocks_by_frame()
          called_by:
            - HTTP GET /api/frames/{frame_id}/text

        why: |
          The timeline and detail views require text for search highlighting and
          summaries. Failing open with empty results keeps the UI resilient.

        guardrails:
          - DO NOT convert unexpected failures to 500 if the database connection
            is transient; prefer empty response to keep UX responsive.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
        """

        try:
            frame = db.get_frame(frame_id)
            if not frame:
                raise HTTPException(status_code=404, detail="Frame not found")
            blocks = db.get_text_blocks_by_frame(frame_id)
            return {"frame_id": frame_id, "blocks": blocks}
        except HTTPException:
            # propagate 404s
            raise
        except Exception as e:  # Be resilient to transient DB issues
            import logging
            logging.getLogger(__name__).warning(
                f"get_frame_text_failed frame_id={frame_id} error={e}"
            )
            # Return empty list instead of 500 to avoid breaking UI
            return {"frame_id": frame_id, "blocks": []}

    @app.get("/api/apps")
    def list_apps(limit: int = Query(50, ge=1, le=200), db: Database = Depends(get_db)):

        stats = db.get_app_usage_stats(limit=limit)
        return {"apps": stats}

    @app.get("/api/settings/all")
    def get_all_settings():

        try:
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
        except Exception as e:
            import traceback
            error_detail = f"Error loading settings: {str(e)}\n{traceback.format_exc()}"
            raise HTTPException(status_code=500, detail=error_detail)

    @app.get("/api/settings/defaults")
    def get_default_settings():

        return DEFAULT_CONFIG

    @app.post("/api/settings/update")
    def update_settings(settings: dict):
        """
        Validate and persist user‑configurable settings.

        ---agentspec
        what: |
          Validates payload structure and known fields (OCR engine options,
          recognition level, numeric constraints). Accumulates field‑level
          validation errors and returns 422 on failure. On success, writes values
          to Config and saves to disk.

        deps:
          calls:
            - Config.set()
            - Config.save()
          called_by:
            - HTTP POST /api/settings/update

        why: |
          Centralizes settings validation and persistence to keep the UI thin
          and to guard against invalid combinations.

        guardrails:
          - DO NOT relax validation without updating the UI; clients rely on the
            422 structure for inline field errors.
          - ALWAYS persist using Config.save() after mutations.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
        """

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
        """
        Report database and host system metrics used by the settings UI.

        ---agentspec
        what: |
          Returns database size, screenshot storage usage, frame/text counts,
          memory utilization, disk free space and whether the DeepSeek MLX
          dependency is importable. Uses psutil for host metrics.

        deps:
          calls:
            - psutil.virtual_memory
            - psutil.disk_usage
            - Database.get_database_stats
          called_by:
            - HTTP GET /api/settings/stats

        why: |
          Gives users feedback on storage and performance to tune capture and
          retention settings.

        guardrails:
          - DO NOT import heavy ML packages here; only test importability.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
        """

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

        engine = config.get("ocr.engine", "apple")
        return {"engine": engine}

    @app.post("/api/settings/ocr-engine")
    def set_ocr_engine(engine: str):

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
        """
        Return AI‑generated summaries for a date, latest type, or recent window.

        ---agentspec
        what: |
          If a date (YYYY‑MM‑DD) is provided, returns that day’s summaries.
          If summary_type is provided, returns the latest summary of that type.
          Otherwise returns summaries from the past 7 days ordered by start time.

        deps:
          calls:
            - Database.get_summaries_for_day
            - Database.get_latest_summary
          called_by:
            - HTTP GET /api/summaries

        why: |
          The UI needs fast access to aggregated insights while browsing the
          timeline without running generation work on demand.

        guardrails:
          - DO NOT change the accepted date format; the UI sends YYYY‑MM‑DD.
          - DO NOT return 500 on bad dates; return 400 with helpful message.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
        """
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
        """
        Compute daily frame/text/app counts for the dashboard.

        ---agentspec
        what: |
          Calculates a day’s start/end unix timestamps and aggregates counts via
          SQL queries: frames captured, OCR text blocks, total characters, and
          distinct applications used.

        deps:
          calls:
            - sqlite3 connection (db.conn.execute)
          called_by:
            - HTTP GET /api/stats/daily

        why: |
          Provides a compact statistical summary used by the top of the page and
          empty‑state logic.

        guardrails:
          - DO NOT change returned keys (frame_count, text_block_count,
            total_characters, app_count) without updating UI rendering.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
        """
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
        """
        Search text blocks via FTS or semantic embeddings.

        ---agentspec
        what: |
          Validates input then executes either FTS search in SQLite or semantic
          vector search via EmbeddingService (optional reranking). Returns a
          normalized list of hits including frame metadata, text, and method.

        deps:
          calls:
            - Database.search_text
            - Database.get_frame
            - Database.get_text_block
            - second_brain.embeddings.EmbeddingService.search
          called_by:
            - HTTP POST /api/search

        why: |
          FTS is fast and local; semantic search is optional and used when
          higher‑level meaning is desired.

        guardrails:
          - DO NOT expose the embedding client globally; import lazily to keep
            API startup fast.
          - DO NOT return unbounded results; always honor limit.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
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
        """
        Generate an AI answer based on search results.

        ---agentspec
        what: |
          Executes the same search pipeline as /api/search and then calls the
          OpenAI Responses API server‑side to synthesize an answer from relevant
          OCR text. Sanitizes context and applies a retry with condensed text.

        deps:
          calls:
            - second_brain.api.server.search
            - openai.OpenAI.responses.create
          called_by:
            - HTTP POST /api/ask
          environment:
            - OPENAI_API_KEY: required (server‑side only)

        why: |
          Keeps credentials on the server and provides a single endpoint for the
          UI to request synthesized answers.

        guardrails:
          - DO NOT leak the API key to the client; calls must remain server‑side.
          - DO NOT block on very large contexts; cap the number and length of
            items to keep latency predictable.

        changelog:
          - "2025-10-30: Added agentspec docstring"
        ---/agentspec
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
            # Extract text from response - comprehensive extraction
            import logging

            logger = logging.getLogger(__name__)

            answer = None
            
            # Method 1: Try output_text attribute (simplest)
            if hasattr(response, "output_text") and response.output_text:
                answer = str(response.output_text).strip()
                logger.debug(f"Extracted answer from output_text: {answer[:100]}...")
            
            # Method 2: Extract from response.output structure
            if not answer and hasattr(response, "output") and response.output:
                logger.debug(f"Response has output attribute with {len(response.output)} items")
                for idx, output_item in enumerate(response.output):
                    logger.debug(f"Processing output_item[{idx}]: type={type(output_item)}, has content={hasattr(output_item, 'content')}")
                    
                    if hasattr(output_item, "content"):
                        content = output_item.content
                        logger.debug(f"  content type: {type(content)}, is list: {isinstance(content, list)}")
                        
                        if isinstance(content, list):
                            for content_idx, content_item in enumerate(content):
                                logger.debug(f"    content_item[{content_idx}]: type={type(content_item)}, has text={hasattr(content_item, 'text')}")
                                if hasattr(content_item, "text") and content_item.text:
                                    answer = str(content_item.text).strip()
                                    logger.debug(f"    Found text in content_item[{content_idx}]: {answer[:100]}...")
                                    break
                        elif hasattr(content, "text") and content.text:
                            answer = str(content.text).strip()
                            logger.debug(f"Found text in content: {answer[:100]}...")
                        elif isinstance(content, str):
                            answer = content.strip()
                            logger.debug(f"Content is string: {answer[:100]}...")
                        
                        if answer:
                            break
            
            # Method 3: Try to get text from response directly
            if not answer and hasattr(response, "text"):
                answer = str(response.text).strip()
                logger.debug(f"Extracted from response.text: {answer[:100]}...")
            
            # Method 4: Last resort - try to find any text attribute in the response
            if not answer:
                # Check all attributes of the response object
                for attr_name in dir(response):
                    if attr_name.startswith('_') or attr_name in ['output', 'output_text', 'text']:
                        continue
                    try:
                        attr_value = getattr(response, attr_name)
                        if isinstance(attr_value, str) and attr_value.strip() and len(attr_value.strip()) > 10:
                            answer = attr_value.strip()
                            logger.debug(f"Found text in response.{attr_name}: {answer[:100]}...")
                            break
                    except:
                        pass
            
            # Log what we found
            if answer:
                logger.info(f"Successfully extracted answer ({len(answer)} chars)")
            else:
                logger.error(
                    f"Failed to extract answer. Response structure: output_text={getattr(response, 'output_text', 'N/A')}, "
                    f"has output={hasattr(response, 'output')}, output type={type(getattr(response, 'output', None))}"
                )
                if hasattr(response, "output") and response.output:
                    logger.error(f"Output items: {[type(item).__name__ for item in response.output]}")
                    # Try to print the actual structure for debugging
                    try:
                        import json
                        logger.error(f"Response output (first 500 chars): {str(response.output)[:500]}")
                    except:
                        pass
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
                    instructions=(
                        "Answer succinctly using provided short OCR snippets."
                    ),
                    input=(
                        f"Question: {query}\n\nEvidence:\n{condensed_ctx}"
                    ),
                    max_output_tokens=1000,
                )
                # Extract text from retry response - comprehensive extraction
                answer = None
                
                # Method 1: Try output_text attribute
                if hasattr(response2, "output_text") and response2.output_text:
                    answer = str(response2.output_text).strip()
                    logger.debug(f"Retry: Extracted from output_text: {answer[:100]}...")
                
                # Method 2: Extract from response.output structure
                if not answer and hasattr(response2, "output") and response2.output:
                    for output_item in response2.output:
                        if hasattr(output_item, "content"):
                            content = output_item.content
                            if isinstance(content, list):
                                for content_item in content:
                                    if hasattr(content_item, "text") and content_item.text:
                                        answer = str(content_item.text).strip()
                                        break
                            elif hasattr(content, "text") and content.text:
                                answer = str(content.text).strip()
                            elif isinstance(content, str):
                                answer = content.strip()
                            if answer:
                                break
                
                # Method 3: Try response.text
                if not answer and hasattr(response2, "text"):
                    answer = str(response2.text).strip()
                
                # Method 4: Last resort - scan all attributes
                if not answer:
                    for attr_name in dir(response2):
                        if attr_name.startswith('_') or attr_name in ['output', 'output_text', 'text']:
                            continue
                        try:
                            attr_value = getattr(response2, attr_name)
                            if isinstance(attr_value, str) and attr_value.strip() and len(attr_value.strip()) > 10:
                                answer = attr_value.strip()
                                logger.debug(f"Retry: Found text in response2.{attr_name}")
                                break
                        except:
                            pass
                
                if not answer or not answer.strip():
                    logger.error(
                        f"Retry also failed. output_text={getattr(response2, 'output_text', 'N/A')}, "
                        f"has output={hasattr(response2, 'output')}"
                    )
                    if hasattr(response2, "output") and response2.output:
                        logger.error(f"Retry output items: {[type(item).__name__ for item in response2.output]}")
                        try:
                            logger.error(f"Retry response output (first 500 chars): {str(response2.output)[:500]}")
                        except:
                            pass
                    answer = None
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
