"""FastAPI server exposing timeline and query APIs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..config import Config
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
                raise HTTPException(status_code=500, detail=f"semantic search failed: {exc}")
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
                if (ch == "\n" or 32 <= ord(ch) <= 126 or (ord(ch) >= 160 and ord(ch) not in (0xFFFF, 0xFFFE)))
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
            answer = None
            if hasattr(response, 'output') and response.output:
                for output_item in response.output:
                    if hasattr(output_item, 'content'):
                        # content is a list of content items, iterate through them
                        if isinstance(output_item.content, list):
                            for content_item in output_item.content:
                                if hasattr(content_item, 'text'):
                                    answer = content_item.text
                                    break
                        else:
                            # Fallback if content is a string directly
                            answer = str(output_item.content)
                        if answer:
                            break
            if not answer:
                # Fallback to string representation if structure is different
                answer = str(response.output) if hasattr(response, 'output') else None
            if not answer or not answer.strip():
                # condensed retry
                condensed = []
                for r in results[:10]:
                    ts = datetime.fromtimestamp(r["timestamp"]) if r.get("timestamp") else None
                    t = _sanitize(" ".join((r.get("text") or "").split()))[:200]
                    condensed.append(
                        f"[{ts.strftime('%Y-%m-%d %H:%M:%S') if ts else 'Unknown'}] {r.get('app_name','Unknown')} • {r.get('window_title','')}\n{t}"
                    )
                condensed_ctx = "\n\n".join(condensed)
                response2 = client.responses.create(
                    model=model,
                    input=[
                        {"role": "developer", "content": "Answer succinctly using provided short OCR snippets."},
                        {"role": "user", "content": f"Question: {query}\n\nEvidence:\n{condensed_ctx}"},
                    ],
                    text={"verbosity": "low"},
                )
                # Extract text from retry response
                answer = None
                if hasattr(response2, 'output') and response2.output:
                    for output_item in response2.output:
                        if hasattr(output_item, 'content'):
                            # content is a list of content items, iterate through them
                            if isinstance(output_item.content, list):
                                for content_item in output_item.content:
                                    if hasattr(content_item, 'text'):
                                        answer = content_item.text
                                        break
                            else:
                                # Fallback if content is a string directly
                                answer = str(output_item.content)
                            if answer:
                                break
                if not answer:
                    answer = str(response2.output) if hasattr(response2, 'output') else None
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"AI answer failed: {exc}")

        return {"answer": answer, "results": results}

    # Serve built React UI if present
    # server.py lives at src/second_brain/api/server.py → repo root is parents[3]
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
