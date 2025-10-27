"""Embedding service for semantic search using Chroma and sentence-transformers."""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional

import chromadb
from chromadb.config import Settings
import structlog
from sentence_transformers import SentenceTransformer

from ..config import Config

logger = structlog.get_logger()


class EmbeddingService:
    """Service for creating and searching embeddings."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize embedding service.
        
        Args:
            config: Configuration instance. If None, uses global config.
        """
        self.config = config or Config()
        
        if not self.config.get("embeddings.enabled", True):
            logger.info("embeddings_disabled")
            self.enabled = False
            return
        
        self.enabled = True
        
        # Get model configuration
        model_name = self.config.get(
            "embeddings.model",
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Initialize embedding model
        logger.info("loading_embedding_model", model=model_name)
        self.model = SentenceTransformer(model_name)
        
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
        
        logger.info(
            "embedding_service_initialized",
            model=model_name,
            collection_count=self.collection.count()
        )
    
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
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False
            ).tolist()
            
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
    ) -> List[Dict[str, Any]]:
        """Search for similar text blocks.
        
        Args:
            query: Search query
            limit: Maximum number of results
            app_filter: Optional app bundle ID to filter by
            
        Returns:
            List of matching results with metadata
        """
        if not self.enabled:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.model.encode(
                [query],
                convert_to_numpy=True,
                show_progress_bar=False
            )[0].tolist()
            
            # Build where filter if app_filter provided
            where = None
            if app_filter:
                where = {"app_bundle_id": app_filter}
            
            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            matches = []
            if results and results["ids"] and len(results["ids"]) > 0:
                for i, block_id in enumerate(results["ids"][0]):
                    matches.append({
                        "block_id": int(block_id),
                        "frame_id": results["metadatas"][0][i]["frame_id"],
                        "text": results["documents"][0][i],
                        "distance": results["distances"][0][i],
                        "metadata": results["metadatas"][0][i],
                    })
            
            logger.debug("semantic_search_completed", query=query, results=len(matches))
            
            return matches
            
        except Exception as e:
            logger.error("search_failed", query=query, error=str(e))
            return []
    
    def delete_frame_blocks(self, frame_id: int) -> None:
        """Delete all text blocks for a frame.
        
        Args:
            frame_id: Frame ID to delete blocks for
        """
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
        """Get embedding service statistics.
        
        Returns:
            Dictionary with statistics
        """
        if not self.enabled:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "total_embeddings": self.collection.count(),
            "model": self.config.get("embeddings.model"),
        }

