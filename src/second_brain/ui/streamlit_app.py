"""Streamlit UI for Second Brain - Daily summaries and visual timeline."""

import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import List, Dict, Any
import os

# Page config
st.set_page_config(
    page_title="Second Brain - Daily Review",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .summary-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 1rem;
        color: white;
        margin-bottom: 2rem;
    }
    .stat-box {
        background: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .timeline-frame {
        border: 2px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 0.5rem;
        margin: 0.5rem;
        cursor: pointer;
        transition: all 0.3s;
    }
    .timeline-frame:hover {
        border-color: #667eea;
        transform: scale(1.05);
    }
    .timeline-frame.selected {
        border-color: #667eea;
        box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
    }
</style>
""", unsafe_allow_html=True)


class SecondBrainUI:
    """Streamlit UI for Second Brain."""
    
    def __init__(self):
        """Initialize UI."""
        self.db_path = Path.home() / "Library/Application Support/second-brain/database/memory.db"
        self.frames_dir = Path.home() / "Library/Application Support/second-brain/frames"
        self.conn = None
        
    def connect_db(self):
        """Connect to database."""
        if not self.db_path.exists():
            st.error("Database not found. Please start Second Brain first.")
            st.stop()
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
    
    def get_daily_stats(self, date: datetime) -> Dict[str, Any]:
        """Get statistics for a specific day."""
        start_ts = int(date.replace(hour=0, minute=0, second=0).timestamp())
        end_ts = int(date.replace(hour=23, minute=59, second=59).timestamp())
        
        cursor = self.conn.cursor()
        
        # Get frame count
        cursor.execute("""
            SELECT COUNT(*) as count FROM frames
            WHERE timestamp BETWEEN ? AND ?
        """, (start_ts, end_ts))
        frame_count = cursor.fetchone()['count']
        
        # Get text block count
        cursor.execute("""
            SELECT COUNT(*) as count FROM text_blocks tb
            JOIN frames f ON tb.frame_id = f.frame_id
            WHERE f.timestamp BETWEEN ? AND ?
        """, (start_ts, end_ts))
        text_count = cursor.fetchone()['count']
        
        # Get app usage
        cursor.execute("""
            SELECT app_name, COUNT(*) as count
            FROM frames
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY app_name
            ORDER BY count DESC
            LIMIT 5
        """, (start_ts, end_ts))
        top_apps = [dict(row) for row in cursor.fetchall()]
        
        # Get total text length
        cursor.execute("""
            SELECT SUM(LENGTH(text)) as total_chars
            FROM text_blocks tb
            JOIN frames f ON tb.frame_id = f.frame_id
            WHERE f.timestamp BETWEEN ? AND ?
        """, (start_ts, end_ts))
        total_chars = cursor.fetchone()['total_chars'] or 0
        
        return {
            'frame_count': frame_count,
            'text_count': text_count,
            'top_apps': top_apps,
            'total_chars': total_chars,
        }
    
    def get_frames_for_day(self, date: datetime, limit: int = 100) -> List[Dict[str, Any]]:
        """Get frames for a specific day."""
        start_ts = int(date.replace(hour=0, minute=0, second=0).timestamp())
        end_ts = int(date.replace(hour=23, minute=59, second=59).timestamp())
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM frames
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (start_ts, end_ts, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_text_for_frame(self, frame_id: str) -> List[Dict[str, Any]]:
        """Get text blocks for a frame."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM text_blocks
            WHERE frame_id = ?
        """, (frame_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_summaries_for_day(self, date: datetime) -> List[Dict[str, Any]]:
        """Get AI-generated summaries for a specific day.
        
        Args:
            date: Date to get summaries for
            
        Returns:
            List of summary dictionaries
        """
        start_ts = int(date.replace(hour=0, minute=0, second=0).timestamp())
        end_ts = int(date.replace(hour=23, minute=59, second=59).timestamp())
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM summaries
            WHERE start_timestamp >= ? AND end_timestamp <= ?
            ORDER BY start_timestamp ASC
        """, (start_ts, end_ts))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def run(self):
        """Run the Streamlit app."""
        self.connect_db()
        
        # Header
        st.markdown('<div class="main-header">🧠 Second Brain</div>', unsafe_allow_html=True)
        st.markdown("### Your Visual Memory Timeline")
        
        # Sidebar - Date selection
        with st.sidebar:
            st.header("📅 Select Date")
            selected_date = st.date_input(
                "Date",
                value=datetime.now().date(),
                max_value=datetime.now().date()
            )
            selected_datetime = datetime.combine(selected_date, datetime.min.time())
            
            st.markdown("---")
            st.header("⚙️ Options")
            show_summary = st.checkbox("Show AI Summary", value=True)
            frames_per_row = st.slider("Frames per row", 2, 6, 4)
            
        # Get stats for selected day
        stats = self.get_daily_stats(selected_datetime)
        
        # Summary cards - show AI-generated summaries from database
        if show_summary and stats['frame_count'] > 0:
            summaries = self.get_summaries_for_day(selected_datetime)
            
            if summaries:
                for summary in summaries:
                    start_time = datetime.fromtimestamp(summary['start_timestamp'])
                    end_time = datetime.fromtimestamp(summary['end_timestamp'])
                    
                    st.markdown(f"""
                    <div class="summary-card">
                        <h2>🤖 AI Summary - {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}</h2>
                        <p style="font-size: 1.1rem; line-height: 1.6;">{summary['summary_text']}</p>
                        <p style="font-size: 0.9rem; opacity: 0.8; margin-top: 1rem;">
                            📊 {summary['frame_count']} frames analyzed
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("💡 AI summaries will appear here once generated (hourly). Keep Second Brain running to generate summaries automatically.")
        
        # Stats row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="stat-box">
                <h3 style="color: #667eea; margin: 0;">📸 {stats['frame_count']}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #666;">Frames Captured</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="stat-box">
                <h3 style="color: #667eea; margin: 0;">📝 {stats['text_count']}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #666;">Text Blocks</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="stat-box">
                <h3 style="color: #667eea; margin: 0;">💬 {stats['total_chars']:,}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #666;">Characters</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="stat-box">
                <h3 style="color: #667eea; margin: 0;">🎯 {len(stats['top_apps'])}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #666;">Apps Used</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Top apps
        if stats['top_apps']:
            st.subheader("📊 Top Applications")
            for app in stats['top_apps']:
                st.progress(
                    app['count'] / stats['frame_count'],
                    text=f"{app['app_name']}: {app['count']} frames"
                )
        
        st.markdown("---")
        
        # Timeline
        st.subheader("🎬 Visual Timeline")
        
        frames = self.get_frames_for_day(selected_datetime, limit=200)
        
        if not frames:
            st.info(f"No frames captured on {selected_date.strftime('%B %d, %Y')}")
            return
        
        # Group frames by hour
        frames_by_hour = {}
        for frame in frames:
            hour = datetime.fromtimestamp(frame['timestamp']).hour
            if hour not in frames_by_hour:
                frames_by_hour[hour] = []
            frames_by_hour[hour].append(frame)
        
        # Display timeline by hour
        for hour in sorted(frames_by_hour.keys()):
            with st.expander(f"⏰ {hour:02d}:00 - {hour:02d}:59 ({len(frames_by_hour[hour])} frames)", expanded=(hour == datetime.now().hour)):
                hour_frames = frames_by_hour[hour]
                
                # Display frames in grid
                cols = st.columns(frames_per_row)
                for idx, frame in enumerate(hour_frames):
                    col_idx = idx % frames_per_row
                    
                    with cols[col_idx]:
                        # Get frame image path
                        frame_path = self.frames_dir / frame['file_path']
                        
                        if frame_path.exists():
                            # Display thumbnail
                            st.image(
                                str(frame_path),
                                caption=f"{datetime.fromtimestamp(frame['timestamp']).strftime('%H:%M:%S')}",
                                use_container_width=True
                            )
                            
                            # Show details on click
                            if st.button(f"View Details", key=f"btn_{frame['frame_id']}"):
                                st.session_state['selected_frame'] = frame['frame_id']
        
        # Selected frame details
        if 'selected_frame' in st.session_state:
            st.markdown("---")
            st.subheader("🔍 Frame Details")
            
            frame_id = st.session_state['selected_frame']
            
            # Get frame data
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM frames WHERE frame_id = ?", (frame_id,))
            frame = dict(cursor.fetchone())
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Display full image
                frame_path = self.frames_dir / frame['file_path']
                if frame_path.exists():
                    st.image(str(frame_path), use_container_width=True)
            
            with col2:
                # Display metadata
                st.markdown(f"**Time**: {datetime.fromtimestamp(frame['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
                st.markdown(f"**Application**: {frame['app_name']}")
                st.markdown(f"**Window**: {frame['window_title']}")
                st.markdown(f"**Resolution**: {frame['screen_resolution']}")
                
                # Display OCR text
                text_blocks = self.get_text_for_frame(frame_id)
                if text_blocks:
                    st.markdown("**Extracted Text:**")
                    for block in text_blocks:
                        with st.expander(f"Text Block ({block['block_type']})", expanded=True):
                            st.text(block['text'])
                            st.caption(f"Confidence: {block['confidence']:.2%}")
                else:
                    st.info("No text extracted for this frame")


def main():
    """Main entry point."""
    ui = SecondBrainUI()
    ui.run()


if __name__ == "__main__":
    main()
