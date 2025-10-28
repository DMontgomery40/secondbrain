"""Real-time activity summarization using GPT-5.

This service automatically summarizes OCR data in real-time and stores
summaries in the database for quick retrieval.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import structlog

from openai import AsyncOpenAI, OpenAIError

from ..config import Config
from ..database import Database

logger = structlog.get_logger()


class SummarizationService:
    """Service for generating AI summaries of captured activity."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize summarization service.
        
        Args:
            config: Configuration instance
        """
        self.config = config or Config()
        
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        # Initialize OpenAI client
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-5"  # Using available model
        
        # Configuration
        self.hourly_summary_enabled = self.config.get("summarization.hourly_enabled", True)
        self.daily_summary_enabled = self.config.get("summarization.daily_enabled", True)
        self.min_frames_for_summary = self.config.get("summarization.min_frames", 10)
        
        # State
        self.running = False
        self.last_hourly_summary = None
        self.summaries_generated = 0
        
        logger.info(
            "summarization_service_initialized",
            model=self.model,
            hourly=self.hourly_summary_enabled,
            daily=self.daily_summary_enabled,
        )
    
    async def generate_summary(
        self,
        text_blocks: List[Dict[str, Any]],
        frames: List[Dict[str, Any]],
        summary_type: str = "hourly"
    ) -> str:
        """Generate a summary using GPT-5.
        
        Args:
            text_blocks: List of text blocks to summarize
            frames: List of frames for context
            summary_type: Type of summary (hourly, daily, session)
            
        Returns:
            Generated summary text
        """
        if not text_blocks:
            return "No activity recorded."
        
        # Prepare context
        context_items = []
        for i, (block, frame) in enumerate(zip(text_blocks[:50], frames[:50])):  # Limit to 50 for token management
            ts = datetime.fromtimestamp(frame['timestamp'])
            app = frame.get('app_name', 'Unknown')
            text = block.get('text', '')[:300]  # Limit text length
            context_items.append(f"[{ts.strftime('%H:%M')}] {app}: {text}")
        
        context_text = "\n".join(context_items)
        
        # Create prompt based on summary type
        if summary_type == "hourly":
            prompt = f"""Summarize this hour of screen activity. Be concise but insightful. 
Focus on:
- Main tasks/activities
- Applications used
- Key accomplishments or patterns

Activity log:
{context_text}

Provide a 2-3 sentence summary."""
        elif summary_type == "daily":
            prompt = f"""Summarize this day's screen activity. Provide an insightful overview.
Focus on:
- Major tasks and projects worked on
- Time allocation across different activities
- Key accomplishments
- Productivity patterns

Activity log:
{context_text}

Provide a comprehensive 4-5 sentence summary."""
        else:
            prompt = f"""Summarize this work session.

Activity log:
{context_text}

Provide a brief 2-3 sentence summary."""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that summarizes screen activity. Be concise, insightful, and focus on meaningful patterns and accomplishments."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_completion_tokens=300,
                # GPT-5 only supports temperature=1 (default), so we omit it
            )
            
            summary = response.choices[0].message.content
            logger.info(
                "summary_generated",
                type=summary_type,
                length=len(summary),
                blocks_processed=len(text_blocks),
            )
            
            return summary
            
        except OpenAIError as e:
            logger.error("summary_generation_failed", error=str(e))
            return f"Failed to generate summary: {str(e)}"
    
    async def generate_hourly_summary(self, database: Database) -> Optional[str]:
        """Generate summary for the last hour.
        
        Args:
            database: Database instance
            
        Returns:
            Summary ID if successful
        """
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        start_ts = int(hour_ago.timestamp())
        end_ts = int(now.timestamp())
        
        # Get frames and text blocks for the hour
        cursor = database.conn.cursor()
        cursor.execute("""
            SELECT f.*, tb.text, tb.block_type
            FROM frames f
            LEFT JOIN text_blocks tb ON f.frame_id = tb.frame_id
            WHERE f.timestamp BETWEEN ? AND ?
            ORDER BY f.timestamp ASC
        """, (start_ts, end_ts))
        
        rows = cursor.fetchall()
        
        if len(rows) < self.min_frames_for_summary:
            logger.debug("not_enough_frames_for_summary", frames=len(rows))
            return None
        
        # Separate frames and text blocks
        frames = []
        text_blocks = []
        app_names = set()
        
        for row in rows:
            frame = dict(row)
            frames.append(frame)
            app_names.add(frame.get('app_name', 'Unknown'))
            
            if frame.get('text'):
                text_blocks.append({
                    'text': frame['text'],
                    'block_type': frame.get('block_type'),
                })
        
        # Generate summary
        summary_text = await self.generate_summary(text_blocks, frames, "hourly")
        
        # Store in database
        summary_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO summaries (
                summary_id, start_timestamp, end_timestamp,
                summary_type, summary_text, frame_count, app_names
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            summary_id,
            start_ts,
            end_ts,
            "hourly",
            summary_text,
            len(frames),
            json.dumps(list(app_names)),
        ))
        database.conn.commit()
        
        self.summaries_generated += 1
        self.last_hourly_summary = now
        
        logger.info(
            "hourly_summary_stored",
            summary_id=summary_id,
            frames=len(frames),
            apps=len(app_names),
        )
        
        return summary_id
    
    async def summarization_loop(self, database: Database):
        """Main loop that generates summaries periodically."""
        logger.info("summarization_loop_started")
        self.running = True
        
        while self.running:
            try:
                # Generate hourly summary every hour
                if self.hourly_summary_enabled:
                    now = datetime.now()
                    
                    # Check if we should generate a summary
                    # (at the top of each hour, or if we haven't generated one yet)
                    should_generate = (
                        self.last_hourly_summary is None or
                        (now - self.last_hourly_summary).total_seconds() >= 3600
                    )
                    
                    if should_generate:
                        await self.generate_hourly_summary(database)
                
                # Sleep for 5 minutes before checking again
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error("summarization_loop_error", error=str(e))
                await asyncio.sleep(60)  # Wait a minute on error
        
        logger.info("summarization_loop_stopped", summaries_generated=self.summaries_generated)
    
    def stop(self):
        """Stop the summarization loop."""
        logger.info("stopping_summarization_service")
        self.running = False
    
    async def close(self):
        """Close the OpenAI client."""
        await self.client.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get summarization statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "running": self.running,
            "summaries_generated": self.summaries_generated,
            "last_hourly_summary": self.last_hourly_summary.isoformat() if self.last_hourly_summary else None,
            "model": self.model,
        }
