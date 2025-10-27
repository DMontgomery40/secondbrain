"""Context7 MCP client for fetching library documentation."""

import httpx
from typing import Dict, List, Optional
import structlog

logger = structlog.get_logger()


class Context7Client:
    """Client for Context7 documentation API."""
    
    BASE_URL = "https://api.context7.com/v1"
    
    def __init__(self, api_key: str):
        """Initialize Context7 client.
        
        Args:
            api_key: Context7 API key
        """
        self.api_key = api_key
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    
    def resolve_library(self, library_name: str) -> Optional[Dict]:
        """Resolve a library name to a Context7 library ID.
        
        Args:
            library_name: Name of the library to search for
            
        Returns:
            Dictionary with library info or None if not found
        """
        try:
            response = self.client.post(
                "/libraries/resolve",
                json={"libraryName": library_name}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("libraries") and len(data["libraries"]) > 0:
                # Return the best match (first result)
                best_match = data["libraries"][0]
                logger.info(
                    "resolved_library",
                    name=library_name,
                    library_id=best_match.get("id"),
                    trust_score=best_match.get("trustScore")
                )
                return best_match
            
            logger.warning("no_library_found", name=library_name)
            return None
            
        except httpx.HTTPError as e:
            logger.error("library_resolution_failed", name=library_name, error=str(e))
            return None
    
    def get_docs(
        self,
        library_id: str,
        topic: Optional[str] = None,
        max_tokens: int = 5000
    ) -> Optional[str]:
        """Fetch documentation for a library.
        
        Args:
            library_id: Context7 library ID (e.g., '/mongodb/docs')
            topic: Optional topic to focus on
            max_tokens: Maximum tokens to retrieve (default: 5000)
            
        Returns:
            Documentation text or None if failed
        """
        try:
            payload = {
                "context7CompatibleLibraryID": library_id,
                "tokens": max_tokens,
            }
            
            if topic:
                payload["topic"] = topic
            
            response = self.client.post(
                "/libraries/docs",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            docs = data.get("documentation", "")
            logger.info(
                "fetched_docs",
                library_id=library_id,
                topic=topic,
                doc_length=len(docs)
            )
            
            return docs
            
        except httpx.HTTPError as e:
            logger.error("docs_fetch_failed", library_id=library_id, error=str(e))
            return None
    
    def search_and_get_docs(
        self,
        library_name: str,
        topic: Optional[str] = None,
        max_tokens: int = 5000
    ) -> Optional[Dict]:
        """Search for a library and fetch its documentation.
        
        Args:
            library_name: Name of the library
            topic: Optional topic to focus on
            max_tokens: Maximum tokens to retrieve
            
        Returns:
            Dictionary with library info and docs, or None if failed
        """
        # First resolve the library
        library = self.resolve_library(library_name)
        if not library:
            return None
        
        library_id = library.get("id")
        if not library_id:
            return None
        
        # Fetch docs
        docs = self.get_docs(library_id, topic, max_tokens)
        if not docs:
            return None
        
        return {
            "library": library,
            "documentation": docs,
        }
    
    def get_multiple_docs(
        self,
        libraries: List[Dict[str, str]],
        max_tokens: int = 5000
    ) -> List[Dict]:
        """Fetch documentation for multiple libraries.
        
        Args:
            libraries: List of dicts with 'name' and optional 'topic' keys
            max_tokens: Maximum tokens per library
            
        Returns:
            List of result dictionaries
        """
        results = []
        
        for lib in libraries:
            name = lib.get("name")
            topic = lib.get("topic")
            
            if not name:
                continue
            
            result = self.search_and_get_docs(name, topic, max_tokens)
            if result:
                results.append(result)
        
        return results
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

