"""Embedding and reranking service using Chroma, SentenceTransformers or OpenAI, and BAAI bge reranker."""

import os
from typing import Dict, List, Any, Optional

import chromadb
from chromadb.config import Settings
import structlog
from sentence_transformers import SentenceTransformer

try:
    # Optional: BAAI reranker
    from FlagEmbedding import FlagReranker  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    FlagReranker = None  # type: ignore

try:
    # Optional OpenAI provider
    from openai import OpenAI as OpenAIClient  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAIClient = None  # type: ignore

from ..config import Config

logger = structlog.get_logger()


class EmbeddingService:
    """Service for creating and searching embeddings."""
    
    def __init__(self, config: Optional[Config] = None):

        self.config = config or Config()
        
        if not self.config.get("embeddings.enabled", True):
            logger.info("embeddings_disabled")
            self.enabled = False
            return
        
        self.enabled = True
        
        # Provider selection
        self.provider = self.config.get("embeddings.provider", "sbert")

        # Embedding backends
        self._sbert_model: Optional[SentenceTransformer] = None
        self._openai_client = None
        self._openai_model = None

        # Initialize embedding backend lazily
        if self.provider == "sbert":
            model_name = self.config.get(
                "embeddings.model", "sentence-transformers/all-MiniLM-L6-v2"
            )
            logger.info("loading_embedding_model", provider="sbert", model=model_name)
            self._sbert_model = SentenceTransformer(model_name)
        elif self.provider == "openai":
            if OpenAIClient is None:
                raise RuntimeError("openai client library not available; install openai")
            api_key = os.getenv(self.config.get("ocr.api_key_env", "OPENAI_API_KEY"))
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not configured for embeddings provider 'openai'")
            self._openai_client = OpenAIClient(api_key=api_key)
            self._openai_model = self.config.get(
                "embeddings.openai_model", "text-embedding-3-small"
            )
            logger.info(
                "loading_embedding_model", provider="openai", model=self._openai_model
            )
        else:
            raise ValueError(f"Unknown embeddings.provider: {self.provider}")
        
        # Initialize Chroma client
        chroma_dir = self.config.get_embeddings_dir()
        chroma_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False,
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="text_blocks",
            metadata={"hnsw:space": "cosine"}
        )

        # Optional reranker (lazy-init when actually used)
        self.reranker_enabled = bool(self.config.get("embeddings.reranker_enabled", False))
        self.reranker_model_name = self.config.get(
            "embeddings.reranker_model", "BAAI/bge-reranker-large"
        )
        self._reranker = None

        logger.info(
            "embedding_service_initialized",
            provider=self.provider,
            collection_count=self.collection.count(),
            reranker=self.reranker_enabled,
        )

    def _ensure_reranker_loaded(self) -> None:

        if not self.reranker_enabled or self._reranker is not None:
            return
        try:
            # Re-import here to avoid import-time hard dependency
            try:
                from FlagEmbedding import FlagReranker as _FlagReranker  # type: ignore
            except Exception as _imp_err:  # pragma: no cover
                logger.warning("flagembedding_not_installed_reranker_disabled", error=str(_imp_err))
                self.reranker_enabled = False
                return
            self._reranker = _FlagReranker(self.reranker_model_name, use_fp16=True)
            logger.info("reranker_loaded", model=self.reranker_model_name)
        except Exception as rerank_err:  # pragma: no cover
            logger.warning("reranker_init_failed", error=str(rerank_err))
            self.reranker_enabled = False

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:

        if self.provider == "sbert":
            assert self._sbert_model is not None
            return self._sbert_model.encode(
                texts, convert_to_numpy=True, show_progress_bar=False
            ).tolist()
        elif self.provider == "openai":
            assert self._openai_client is not None and self._openai_model is not None
            # OpenAI embeddings API expects list of inputs; returns data[].embedding
            resp = self._openai_client.embeddings.create(
                input=texts, model=self._openai_model
            )
            return [d.embedding for d in resp.data]
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def index_text_blocks(
        self,
        frame_metadata: Dict[str, Any],
        text_blocks: List[Dict[str, Any]]
    ) -> None:
        """Index text blocks for semantic search.
        
        Args:
            frame_metadata: Frame metadata dictionary
            text_blocks: List of text block dictionaries
        """
        if not self.enabled:
            return
        
        if not text_blocks:
            return
        
        try:
            # Prepare data for indexing
            ids = []
            texts = []
            metadatas = []
            
            for block in text_blocks:
                block_id = str(block["block_id"])
                text = block["text"]
                
                if not text or len(text.strip()) == 0:
                    continue
                
                ids.append(block_id)
                texts.append(text)
                
                # Include frame metadata with block
                metadatas.append({
                    "frame_id": frame_metadata["frame_id"],
                    "block_id": block["block_id"],
                    "app_name": frame_metadata.get("app_name", ""),
                    "app_bundle_id": frame_metadata.get("app_bundle_id", ""),
                    "window_title": frame_metadata.get("window_title", ""),
                    "timestamp": frame_metadata["timestamp"],
                    "x": block.get("x", 0),
                    "y": block.get("y", 0),
                    "width": block.get("width", 0),
                    "height": block.get("height", 0),
                })
            
            if not ids:
                return
            
            # Generate embeddings
            embeddings = self._embed_texts(texts)
            
            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )
            
            logger.debug(
                "text_blocks_indexed",
                frame_id=frame_metadata["frame_id"],
                count=len(ids)
            )
            
        except Exception as e:
            logger.error(
                "indexing_failed",
                frame_id=frame_metadata.get("frame_id"),
                error=str(e)
            )
            raise
    
    def search(
        self,
        query: str,
        limit: int = 10,
        app_filter: Optional[str] = None,
        rerank: bool = False,
        start_timestamp: Optional[int] = None,
        end_timestamp: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar text blocks.

        Args:
            query: Search query
            limit: Maximum number of results
            app_filter: Optional app bundle ID to filter by
            rerank: Whether to rerank results using cross-encoder
            start_timestamp: Optional start timestamp (unix seconds) to filter by
            end_timestamp: Optional end timestamp (unix seconds) to filter by

        Returns:
            List of matching results with metadata
        """
        if not self.enabled:
            return []

        try:
            # Generate query embedding
            query_embedding = self._embed_texts([query])[0]

            # Build where filter for app, start, and end timestamps
            where = None
            where_conditions = []

            if app_filter:
                where_conditions.append({"app_bundle_id": app_filter})

            if start_timestamp is not None:
                where_conditions.append({"timestamp": {"$gte": start_timestamp}})

            if end_timestamp is not None:
                where_conditions.append({"timestamp": {"$lte": end_timestamp}})

            # Combine conditions with $and if multiple filters
            if len(where_conditions) == 1:
                where = where_conditions[0]
            elif len(where_conditions) > 1:
                where = {"$and": where_conditions}
            
            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            matches: List[Dict[str, Any]] = []
            if results and results.get("ids") and len(results["ids"]) > 0:
                for i, block_id in enumerate(results["ids"][0]):
                    matches.append({
                        "block_id": block_id,  # keep as string id
                        "frame_id": results["metadatas"][0][i]["frame_id"],
                        "text": results["documents"][0][i],
                        "distance": results["distances"][0][i],
                        "metadata": results["metadatas"][0][i],
                    })

            # Optional rerank using cross-encoder
            if rerank:
                self._ensure_reranker_loaded()
            if rerank and self.reranker_enabled and self._reranker and matches:
                pairs = [[query, m["text"]] for m in matches]
                try:
                    scores = self._reranker.compute_score(pairs, normalize=True)
                    for m, s in zip(matches, scores):
                        m["rerank_score"] = float(s)
                    matches.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
                except Exception as rerank_err:
                    logger.warning("rerank_failed", error=str(rerank_err))
            
            logger.debug("semantic_search_completed", query=query, results=len(matches))
            
            return matches
            
        except Exception as e:
            logger.error("search_failed", query=query, error=str(e))
            return []
    
    def delete_frame_blocks(self, frame_id: int) -> None:

        if not self.enabled:
            return
        
        try:
            # Query for blocks belonging to this frame
            results = self.collection.get(
                where={"frame_id": frame_id},
                include=[]
            )
            
            if results and results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.debug("frame_blocks_deleted", frame_id=frame_id, count=len(results["ids"]))
                
        except Exception as e:
            logger.error("delete_failed", frame_id=frame_id, error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:

        if not self.enabled:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "total_embeddings": self.collection.count(),
            "provider": self.provider,
            "model": self.config.get("embeddings.model") if self.provider == "sbert" else self._openai_model,
            "reranker": self.reranker_enabled,
            "reranker_model": self.reranker_model_name if self.reranker_enabled else None,
        }

    def rerank(self, query: str, texts: List[str]) -> List[float]:

        if not (self.reranker_enabled and self._reranker):
            logger.warning("rerank_called_but_disabled")
            return [0.0 for _ in texts]
        pairs = [[query, t] for t in texts]
        try:
            scores = self._reranker.compute_score(pairs, normalize=True)
            return [float(s) for s in scores]
        except Exception as e:
            logger.warning("rerank_compute_failed", error=str(e))
            return [0.0 for _ in texts]
