"""Embedding service for semantic search over visual memory."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger()


class EmbeddingService:
    """
    Semantic search service using sentence transformers and Chroma.

    NOTE: This is currently a stub implementation. Full semantic search
    with Chroma vector store is planned for future release.
    """

    def __init__(self, config: Optional[Any] = None):
        """
        Initialize embedding service.

        Args:
            config: Configuration instance (optional)
        """
        self.config = config
        logger.warning(
            "embedding_service_stub",
            message="EmbeddingService is currently a stub. Semantic search not yet implemented."
        )

    def search(
        self,
        query: str,
        limit: int = 10,
        app_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search over embeddings.

        Args:
            query: Search query string
            limit: Maximum number of results
            app_filter: Optional app bundle ID filter

        Returns:
            List of search results with frame_id, block_id, and distance

        NOTE: This is a stub implementation that returns empty results.
        """
        logger.warning(
            "semantic_search_not_implemented",
            query=query,
            message="Semantic search is not yet implemented. Use FTS5 search instead."
        )
        return []

    def index_text_block(self, frame_id: str, block_id: str, text: str) -> None:
        """
        Index a text block for semantic search.

        Args:
            frame_id: Frame identifier
            block_id: Text block identifier
            text: Text content to index

        NOTE: This is a stub implementation that does nothing.
        """
        pass

    def index_batch(self, text_blocks: List[Dict[str, Any]]) -> int:
        """
        Index a batch of text blocks.

        Args:
            text_blocks: List of text block dicts with frame_id, block_id, text

        Returns:
            Number of blocks indexed

        NOTE: This is a stub implementation that returns 0.
        """
        return 0
