"""Streamlit UI for Second Brain - Daily summaries and visual timeline."""

import streamlit as st
from datetime import datetime, time, timedelta
from pathlib import Path
import sqlite3
from typing import List, Dict, Any, Optional

# Import config system
from second_brain.config import get_config

# Page config
st.set_page_config(
    page_title="Second Brain - Daily Review",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with modern animations and improved styling
st.markdown("""
<style>
    /* Global improvements */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }

    @keyframes shimmer {
        0% { background-position: -1000px 0; }
        100% { background-position: 1000px 0; }
    }

    /* Main header with gradient text */
    .main-header {
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: fadeIn 0.6s ease-out;
    }

    /* Enhanced summary card with glassmorphism effect */
    .summary-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2.5rem;
        border-radius: 1.5rem;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
        animation: fadeIn 0.8s ease-out;
        transition: all 0.3s ease;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .summary-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 48px rgba(102, 126, 234, 0.4);
    }

    /* Modern stat boxes with hover effects - dark mode compatible */
    .stat-box {
        background: rgba(255, 255, 255, 0.05);
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        text-align: center;
        transition: all 0.3s ease;
        animation: fadeIn 0.6s ease-out;
        border: 2px solid rgba(102, 126, 234, 0.3);
    }

    .stat-box:hover {
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
        border-color: #667eea;
        background: rgba(102, 126, 234, 0.1);
    }

    /* Timeline frame cards with smooth transitions - dark mode compatible */
    .timeline-frame {
        border: 2px solid rgba(255, 255, 255, 0.1);
        border-radius: 0.75rem;
        padding: 0.75rem;
        margin: 0.5rem;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        background: rgba(255, 255, 255, 0.03);
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }

    .timeline-frame:hover {
        border-color: #667eea;
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 8px 16px rgba(102, 126, 234, 0.4);
        background: rgba(102, 126, 234, 0.1);
    }

    .timeline-frame.selected {
        border-color: #667eea;
        box-shadow: 0 6px 12px rgba(102, 126, 234, 0.5);
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
    }

    /* Enhanced button styling */
    .stButton > button {
        border-radius: 0.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }

    /* Image hover effects */
    img {
        transition: all 0.3s ease;
        border-radius: 0.5rem;
    }

    img:hover {
        transform: scale(1.03);
        box-shadow: 0 8px 16px rgba(0,0,0,0.15);
    }

    /* Progress bar styling */
    .stProgress > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border-radius: 1rem;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        border-radius: 0.5rem;
        transition: all 0.3s ease;
        font-weight: 600;
    }

    .streamlit-expanderHeader:hover {
        background-color: rgba(102, 126, 234, 0.05);
    }

    /* Loading spinner animation */
    .stSpinner > div {
        border-color: #667eea !important;
    }

    /* Smooth fade for all containers */
    .element-container {
        animation: fadeIn 0.5s ease-out;
    }

    /* Info/success/warning boxes */
    .stAlert {
        border-radius: 0.75rem;
        border-left: 4px solid #667eea;
        animation: fadeIn 0.5s ease-out;
    }

    /* Sidebar improvements - dark mode */
    .css-1d391kg {
        background: linear-gradient(180deg, #0e1117 0%, #262730 100%);
    }

    /* Metric styling */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
</style>
""", unsafe_allow_html=True)


class SecondBrainUI:
    """Streamlit UI for Second Brain."""
    
    def __init__(self):

        self.db_path = Path.home() / "Library/Application Support/second-brain/database/memory.db"
        self.frames_dir = Path.home() / "Library/Application Support/second-brain/frames"
        self.conn = None
        
    def connect_db(self):

        if not self.db_path.exists():
            st.error("Database not found. Please start Second Brain first.")
            st.stop()
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
    
    @st.cache_data(ttl=60)
    def get_daily_stats(_self, date: datetime) -> Dict[str, Any]:

        start_ts = int(date.replace(hour=0, minute=0, second=0).timestamp())
        end_ts = int(date.replace(hour=23, minute=59, second=59).timestamp())

        cursor = _self.conn.cursor()
        
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
    
    @st.cache_data(ttl=60)
    def get_frames_for_day(_self, date: datetime, app_filter: Optional[str] = None, start_time=None, end_time=None, preview_per_hour: int = 10) -> Dict[int, List[Dict[str, Any]]]:
        """Get frames for a specific day with filtering and lazy loading.

        Args:
            date: Date to query
            app_filter: Optional app name to filter by
            start_time: Start time (datetime.time object)
            end_time: End time (datetime.time object)
            preview_per_hour: Number of frames to load per hour as preview

        Returns:
            Dict mapping hour -> list of frames (limited to preview_per_hour)
        """
        # Ensure we have time objects, not datetime
        if start_time is None:
            start_time = time(0, 0)
        elif isinstance(start_time, datetime):
            start_time = start_time.time()

        if end_time is None:
            end_time = time(23, 59, 59)
        elif isinstance(end_time, datetime):
            end_time = end_time.time()

        # Get date object from datetime
        if isinstance(date, datetime):
            date_obj = date.date()
        else:
            date_obj = date

        start_dt = datetime.combine(date_obj, start_time)
        end_dt = datetime.combine(date_obj, end_time)
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        cursor = _self.conn.cursor()

        # Build query with optional app filter
        query = """
            SELECT * FROM frames
            WHERE timestamp BETWEEN ? AND ?
        """
        params = [start_ts, end_ts]

        if app_filter:
            query += " AND app_bundle_id = ?"
            params.append(app_filter)

        query += " ORDER BY timestamp ASC"

        cursor.execute(query, params)
        all_frames = [dict(row) for row in cursor.fetchall()]

        # Group by hour and limit to preview
        frames_by_hour = {}
        for frame in all_frames:
            hour = datetime.fromtimestamp(frame['timestamp']).hour
            if hour not in frames_by_hour:
                frames_by_hour[hour] = {'frames': [], 'total': 0}

            frames_by_hour[hour]['total'] += 1
            if len(frames_by_hour[hour]['frames']) < preview_per_hour:
                frames_by_hour[hour]['frames'].append(frame)

        return frames_by_hour

    @st.cache_data(ttl=60)
    def get_apps_for_day(_self, date: datetime) -> Dict[str, str]:

        start_ts = int(date.replace(hour=0, minute=0, second=0).timestamp())
        end_ts = int(date.replace(hour=23, minute=59, second=59).timestamp())

        cursor = _self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT app_name, app_bundle_id FROM frames
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY app_name
        """, (start_ts, end_ts))

        return {row[0]: row[1] for row in cursor.fetchall()}
    
    @st.cache_data(ttl=60)
    def get_text_for_frame(_self, frame_id: str) -> List[Dict[str, Any]]:

        cursor = _self.conn.cursor()
        cursor.execute("""
            SELECT * FROM text_blocks
            WHERE frame_id = ?
        """, (frame_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def render_settings_panel(self):

        config = get_config()
        
        # Initialize session state for settings
        if 'settings_changed' not in st.session_state:
            st.session_state['settings_changed'] = False
        
        st.subheader("⚙️ Settings")
        
        # Create tabs for different settings categories
        tab1, tab2, tab3 = st.tabs(["Capture", "Search", "Storage"])
        
        with tab1:
            st.markdown("#### Capture Settings")
            
            # Smart capture toggles
            st.markdown("**Smart Capture:**")
            
            # Enable frame deduplication
            enable_frame_diff = config.get("capture.enable_frame_diff", True)
            new_frame_diff = st.checkbox(
                "Skip duplicate frames",
                value=enable_frame_diff,
                help="Automatically skip frames that haven't changed"
            )
            if new_frame_diff != enable_frame_diff:
                config.set("capture.enable_frame_diff", new_frame_diff)
                config.save()
                st.success(f"Frame deduplication {'enabled' if new_frame_diff else 'disabled'}")
            
            # Frame similarity threshold
            if new_frame_diff:
                similarity_threshold = config.get("capture.similarity_threshold", 0.95)
                new_threshold = st.slider(
                    "Similarity threshold",
                    min_value=0.80,
                    max_value=0.99,
                    value=float(similarity_threshold),
                    step=0.01,
                    help="How similar frames need to be to be considered duplicates (higher = more strict)"
                )
                if new_threshold != similarity_threshold:
                    config.set("capture.similarity_threshold", new_threshold)
                    config.save()
                    st.success(f"Threshold updated to {new_threshold}")
            
            st.markdown("---")
            st.markdown("**Adaptive FPS:**")
            
            # Enable adaptive FPS
            enable_adaptive_fps = config.get("capture.enable_adaptive_fps", True)
            new_adaptive_fps = st.checkbox(
                "Auto-adjust FPS based on activity",
                value=enable_adaptive_fps,
                help="Automatically reduce FPS when idle (smart power saving)"
            )
            if new_adaptive_fps != enable_adaptive_fps:
                config.set("capture.enable_adaptive_fps", new_adaptive_fps)
                config.save()
                st.success(f"Adaptive FPS {'enabled' if new_adaptive_fps else 'disabled'}")
            
            # Idle threshold
            if new_adaptive_fps:
                idle_threshold = config.get("capture.idle_threshold_seconds", 30.0)
                new_idle = st.slider(
                    "Idle detection threshold (seconds)",
                    min_value=10.0,
                    max_value=120.0,
                    value=float(idle_threshold),
                    step=5.0,
                    help="Seconds of inactivity before considered idle"
                )
                if new_idle != idle_threshold:
                    config.set("capture.idle_threshold_seconds", new_idle)
                    config.save()
                    st.success(f"Idle threshold updated to {new_idle}s")
            
            st.markdown("---")
            st.markdown("**Image Settings:**")
            
            # Format setting
            current_format = config.get("capture.format", "png")
            new_format = st.selectbox(
                "Image format",
                options=["png", "webp", "jpg"],
                index=["png", "webp", "jpg"].index(current_format),
                help="PNG: lossless, larger; WebP: balanced; JPG: smaller, lossy"
            )
            if new_format != current_format:
                config.set("capture.format", new_format)
                config.save()
                st.success(f"Format updated to {new_format}")
            
            # BEGIN_DEEPSEEK_OCR
            # OCR Engine selection (currently Apple Vision only, DeepSeek commented for future)
            # FUTURE: Uncomment when DeepSeek OCR is production-ready
            # current_ocr_engine = config.get("ocr.engine", "apple")
            # new_ocr_engine = st.selectbox(
            #     "OCR Engine",
            #     options=["apple", "deepseek"],
            #     index=["apple", "deepseek"].index(current_ocr_engine),
            #     help="Apple Vision: fast, free, local (default)\nDeepSeek: cutting-edge, local, requires MLX (experimental)"
            # )
            # if new_ocr_engine != current_ocr_engine:
            #     config.set("ocr.engine", new_ocr_engine)
            #     config.save()
            #     st.success(f"OCR engine updated to {new_ocr_engine}")
            # END_DEEPSEEK_OCR
            
            # Quality setting
            current_quality = config.get("capture.quality", 85)
            new_quality = st.slider(
                "Image quality (for WebP/JPG)",
                min_value=50,
                max_value=100,
                value=int(current_quality),
                step=5,
                help="Higher quality = larger files but better image preservation"
            )
            if new_quality != current_quality:
                config.set("capture.quality", new_quality)
                config.save()
                st.success(f"Quality updated to {new_quality}")
            
            # Max disk usage
            current_max_disk = config.get("capture.max_disk_usage_gb", 100)
            new_max_disk = st.number_input(
                "Max disk usage (GB)",
                min_value=10,
                max_value=1000,
                value=int(current_max_disk),
                step=10,
                help="Maximum disk space to use for captured frames"
            )
            if new_max_disk != current_max_disk:
                config.set("capture.max_disk_usage_gb", new_max_disk)
                config.save()
                st.success(f"Max disk usage updated to {new_max_disk} GB")
        
        with tab2:
            st.markdown("#### Search Settings")
            
            # Embeddings enabled
            embeddings_enabled = config.get("embeddings.enabled", True)
            new_embeddings_enabled = st.checkbox(
                "Enable semantic search (embeddings)",
                value=embeddings_enabled,
                help="Enable vector embeddings for semantic search"
            )
            if new_embeddings_enabled != embeddings_enabled:
                config.set("embeddings.enabled", new_embeddings_enabled)
                config.save()
                status = "enabled" if new_embeddings_enabled else "disabled"
                st.success(f"Semantic search {status}")
            
            # Reranker setting
            reranker_enabled = config.get("embeddings.reranker_enabled", False)
            new_reranker_enabled = st.checkbox(
                "Enable search result reranking",
                value=reranker_enabled,
                help="Use AI-powered reranking to improve search result relevance (requires BAAI/bge-reranker-large model - 2.24 GB download on first use)"
            )
            if new_reranker_enabled != reranker_enabled:
                config.set("embeddings.reranker_enabled", new_reranker_enabled)
                config.save()
                if new_reranker_enabled:
                    st.info("ℹ️ Reranker model (2.24 GB) will download on first search. This improves relevance significantly.")
                    st.success("Reranking enabled")
                else:
                    st.success("Reranking disabled")
            
            # Embedding model info
            if embeddings_enabled:
                embedding_model = config.get("embeddings.model", "sentence-transformers/all-MiniLM-L6-v2")
                st.caption(f"Embedding model: {embedding_model}")
        
        with tab3:
            st.markdown("#### Storage Settings")
            
            # Retention days
            current_retention = config.get("storage.retention_days", 90)
            new_retention = st.number_input(
                "Data retention (days)",
                min_value=7,
                max_value=365,
                value=int(current_retention),
                step=7,
                help="How long to keep captured data before automatic deletion"
            )
            if new_retention != current_retention:
                config.set("storage.retention_days", new_retention)
                config.save()
                st.success(f"Retention updated to {new_retention} days")
            
            # Compression
            compression_enabled = config.get("storage.compression", True)
            new_compression = st.checkbox(
                "Enable compression",
                value=compression_enabled,
                help="Compress text blocks and metadata for faster I/O"
            )
            if new_compression != compression_enabled:
                config.set("storage.compression", new_compression)
                config.save()
                st.success(f"Compression {'enabled' if new_compression else 'disabled'}")
        
        st.markdown("---")
        
        # Reset options
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save All Settings", use_container_width=True):
                config.save()
                st.success("✅ All settings saved")
        
        with col2:
            if st.button("🔄 Reset to Defaults", use_container_width=True, type="secondary"):
                config.reset_all()
                st.success("✅ Settings reset to defaults")
                st.rerun()
    
    @st.cache_data(ttl=60)
    def get_summaries_for_day(_self, date: datetime) -> List[Dict[str, Any]]:
        """Get AI-generated summaries for a specific day.

        Args:
            date: Date to get summaries for

        Returns:
            List of summary dictionaries
        """
        start_ts = int(date.replace(hour=0, minute=0, second=0).timestamp())
        end_ts = int(date.replace(hour=23, minute=59, second=59).timestamp())

        cursor = _self.conn.cursor()
        cursor.execute("""
            SELECT * FROM summaries
            WHERE start_timestamp >= ? AND end_timestamp <= ?
            ORDER BY start_timestamp ASC
        """, (start_ts, end_ts))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def run(self):

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
            
            # Render settings panel with full config management (collapsible)
            with st.expander("⚙️ Settings", expanded=False):
                self.render_settings_panel()
            
            st.markdown("---")
            st.caption("💡 Changes are saved immediately")
        
        # Get stats for selected day with loading indicator
        with st.spinner("Loading daily statistics..."):
            stats = self.get_daily_stats(selected_datetime)

        # Show empty state if no frames captured
        if stats['frame_count'] == 0:
            st.markdown("""
            <div style="padding: 4rem 2rem; text-align: center; background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%); border-radius: 1.5rem; margin: 3rem 0;">
                <h1 style="color: #667eea; margin-bottom: 1rem;">📭 No Activity Recorded</h1>
                <p style="font-size: 1.2rem; color: #aaa; margin-bottom: 2rem;">
                    No frames were captured on this day.
                </p>
                <div style="background: rgba(255, 255, 255, 0.05); padding: 2rem; border-radius: 1rem; max-width: 600px; margin: 0 auto; box-shadow: 0 8px 16px rgba(0,0,0,0.5); border: 1px solid rgba(102, 126, 234, 0.3);">
                    <h3 style="color: #fafafa; margin-bottom: 1rem;">🚀 Getting Started</h3>
                    <p style="color: #ccc; line-height: 1.8; margin: 0;">
                        Make sure Second Brain is running in the background to start capturing your screen activity.
                        Try selecting a different date or start Second Brain to begin recording!
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.stop()

        # UI-only settings (not persisted to config)
        show_summary = st.sidebar.checkbox("Show AI Summary", value=True, help="Display AI-generated summaries if available")
        frames_per_row = st.sidebar.slider("Frames per row", 2, 6, 4, help="How many frames to display per row in timeline")

        # Filters
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filters")

        # App filter - get app_name -> app_bundle_id mapping
        app_mapping = self.get_apps_for_day(selected_datetime)
        available_apps = list(app_mapping.keys())
        app_filter_name = st.sidebar.selectbox(
            "Filter by App",
            options=["All"] + available_apps,
            index=0,
            help="Filter frames by application"
        )
        # Convert app_name to app_bundle_id for database queries
        app_filter = app_mapping.get(app_filter_name) if app_filter_name != "All" else None

        # Time range filter with proper time picker
        st.sidebar.subheader("Time Range")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_time = st.time_input("Start Time", value=time(0, 0))
        with col2:
            end_time = st.time_input("End Time", value=time(23, 59, 59))

        # Preview limit control - up to 1000 frames per hour
        _preview_limit = st.sidebar.number_input(  # noqa: F841
            "Frames per hour (max)",
            min_value=5,
            max_value=1000,
            value=10,
            step=5,
            help="Number of frames to display per hour. Set to 1000 to see all frames."
        )

        # ===== CHATBOT / QUERY INTERFACE =====
        st.markdown("---")
        st.markdown("### 💬 Ask Your Second Brain")

        query_text = st.text_input(
            "Search your captured memory",
            placeholder="What was I working on yesterday? What did I read about...?",
            help="Ask questions about your captured screen activity"
        )

        # Query options in expander
        with st.expander("🔧 Search Options", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                use_semantic = st.checkbox(
                    "Use Semantic Search",
                    value=True,
                    help="Vector-based semantic search for meaning, not just keywords"
                )
                result_limit = st.slider(
                    "Max Results",
                    min_value=5,
                    max_value=50,
                    value=10,
                    help="Maximum number of results to return"
                )
            with col2:
                use_reranker = st.checkbox(
                    "Enable AI Reranking",
                    value=False,
                    disabled=not use_semantic,
                    help="Use AI-powered reranking for better relevance (requires model download)"
                )
                query_app_filter_name = st.selectbox(
                    "Filter by App",
                    options=["All"] + available_apps,
                    key="query_app_filter",
                    help="Only search within specific app"
                )
                # Convert app_name to app_bundle_id for search queries
                query_app_filter = app_mapping.get(query_app_filter_name) if query_app_filter_name != "All" else None

            # Date Range Selection
            st.markdown("##### 📅 Date Range")
            date_preset = st.radio(
                "Select time range",
                options=["Last 7 Days", "Last 30 Days", "All Time", "Custom Range"],
                index=0,  # Default to "Last 7 Days"
                horizontal=True,
                help="Choose the time period to search within"
            )

            # Calculate timestamps based on preset
            query_start_timestamp = None
            query_end_timestamp = None

            if date_preset == "Last 7 Days":
                query_start_timestamp = int((datetime.now() - timedelta(days=7)).timestamp())
                query_end_timestamp = int(datetime.now().timestamp())
            elif date_preset == "Last 30 Days":
                query_start_timestamp = int((datetime.now() - timedelta(days=30)).timestamp())
                query_end_timestamp = int(datetime.now().timestamp())
            elif date_preset == "All Time":
                query_start_timestamp = None
                query_end_timestamp = None
            elif date_preset == "Custom Range":
                col_start, col_end = st.columns(2)
                with col_start:
                    custom_start_date = st.date_input(
                        "Start Date",
                        value=(datetime.now() - timedelta(days=7)).date(),
                        max_value=datetime.now().date(),
                        key="query_custom_start"
                    )
                with col_end:
                    custom_end_date = st.date_input(
                        "End Date",
                        value=datetime.now().date(),
                        max_value=datetime.now().date(),
                        key="query_custom_end"
                    )
                # Convert dates to timestamps (start of day to end of day)
                query_start_timestamp = int(datetime.combine(custom_start_date, datetime.min.time()).timestamp())
                query_end_timestamp = int(datetime.combine(custom_end_date, datetime.max.time()).timestamp())

        # Execute search
        if query_text:
            with st.spinner("🔍 Searching your memory..."):
                try:
                    from second_brain.database import Database

                    db = Database()
                    search_results = []
                    debug_info = []

                    if use_semantic:
                        # Use semantic vector search
                        try:
                            from second_brain.embeddings import EmbeddingService
                            embedding_service = EmbeddingService()

                            debug_info.append(f"Using semantic search with limit={result_limit}")
                            debug_info.append(f"App filter name: {query_app_filter_name}")
                            debug_info.append(f"App filter bundle ID: {query_app_filter}")
                            debug_info.append(f"Reranker: {use_reranker}")

                            matches = embedding_service.search(
                                query=query_text,
                                limit=result_limit,
                                app_filter=query_app_filter,
                                rerank=use_reranker,
                                start_timestamp=query_start_timestamp,
                                end_timestamp=query_end_timestamp,
                            )

                            debug_info.append(f"Got {len(matches)} matches from embedding service")

                            for match in matches:
                                frame = db.get_frame(match["frame_id"])
                                if not frame:
                                    debug_info.append(f"Frame {match['frame_id']} not found")
                                    continue
                                block = db.get_text_block(match["block_id"])
                                if not block:
                                    debug_info.append(f"Block {match['block_id']} not found")
                                    continue
                                search_results.append({
                                    "window_title": frame.get("window_title") or "Untitled",
                                    "app_name": frame.get("app_name") or "Unknown",
                                    "timestamp": frame.get("timestamp"),
                                    "text": block.get("text", ""),
                                    "score": 1 - match.get("distance", 0.0) if match.get("distance") is not None else None,
                                    "method": "semantic",
                                    "frame_id": frame.get("frame_id"),
                                })
                        except Exception as e:
                            st.warning(f"⚠️ Semantic search failed: {str(e)}. Falling back to full-text search.")
                            debug_info.append(f"Semantic search error: {str(e)}")
                            use_semantic = False  # Fall back to FTS

                    if not use_semantic:
                        # Use full-text search
                        debug_info.append("Using full-text search")
                        results = db.search_text(
                            query=query_text,
                            app_filter=query_app_filter,
                            start_timestamp=query_start_timestamp,
                            end_timestamp=query_end_timestamp,
                            limit=result_limit,
                        )
                        debug_info.append(f"Got {len(results)} results from FTS")

                        for result in results:
                            search_results.append({
                                "window_title": result.get("window_title") or "Untitled",
                                "app_name": result.get("app_name") or "Unknown",
                                "timestamp": result.get("timestamp"),
                                "text": result.get("text", ""),
                                "score": result.get("score"),
                                "method": "fts",
                                "frame_id": result.get("frame_id"),
                            })

                    db.close()

                    # Generate AI answer from search results (for BOTH semantic and full-text search)
                    ai_answer = None
                    debug_info.append(f"Search results count: {len(search_results)}")
                    if search_results and len(search_results) > 0:
                        debug_info.append("Attempting to generate AI answer...")
                        try:
                            import os
                            from openai import OpenAI
                            
                            api_key = os.getenv("OPENAI_API_KEY")
                            if not api_key:
                                st.error("❌ OPENAI_API_KEY not found in environment!")
                                debug_info.append("No OpenAI API key found")
                                raise ValueError("Missing OPENAI_API_KEY")
                            
                            openai_client = OpenAI(api_key=api_key)
                            debug_info.append(f"OpenAI client initialized (key length: {len(api_key)})")
                            
                            # Prepare ENHANCED context from search results
                            context_items = []
                            apps_seen = set()
                            
                            # Group results by relevance and provide rich context
                            # Sanitize function to avoid problematic control chars for LLMs
                            def _sanitize_text(s: str) -> str:

                                return "".join(
                                    ch if (
                                        ch == "\n" or 32 <= ord(ch) <= 126 or (ord(ch) >= 160 and ord(ch) not in (0xFFFF, 0xFFFE))
                                    ) else " "
                                    for ch in s
                                )

                            for i, result in enumerate(search_results[:40]):  # limit context size for reliability
                                ts = datetime.fromtimestamp(result["timestamp"])
                                app = result.get("app_name", "Unknown")
                                window = result.get("window_title", "")
                                text = result.get("text", "").strip()
                                # score is calculated when rendering; no need to store here
                                
                                if not text:  # Skip empty text
                                    continue
                                
                                apps_seen.add(app)
                                
                                # Format based on relevance
                                relevance = "HIGH" if i < 5 else "MEDIUM" if i < 15 else "LOW"
                                
                                # Clean up and sanitize text; keep token budget controlled
                                text = _sanitize_text(" ".join(text.split()))[:300]
                                
                                context_entry = f"""[RELEVANCE: {relevance}]
Time: {ts.strftime('%Y-%m-%d %H:%M:%S')}
Application: {app}
Window: {window}
Content:
{text}"""
                                
                                context_items.append(context_entry)
                            
                            # Create structured context
                            context_text = ("\n\n" + "=" * 50 + "\n\n").join(context_items)
                            
                            # Add summary of what apps were involved
                            apps_summary = f"Applications involved: {', '.join(sorted(apps_seen))}"
                            
                            debug_info.append(f"Context prepared: {len(context_items)} text blocks, {len(apps_seen)} apps, {len(context_text)} chars")
                            
                            # Generate answer using GPT-5 (Responses API)
                            model = "gpt-5"
                            response = openai_client.responses.create(
                                model=model,
                                instructions=(
                                    "You are an expert assistant helping a user recall their computer activities. "
                                    "You have access to OCR-extracted text from their screen captures, organized by relevance to their query.\n\n"
                                    "IMPORTANT CONTEXT:\n"
                                    "- This is REAL TEXT that was visible on their screen, captured via OCR\n"
                                    "- Text may contain typical OCR artifacts (minor typos, merged words, etc.)\n"
                                    "- Higher relevance entries are more likely to contain the answer\n"
                                    "- The text preserves actual content: code, commands, documents, web pages, etc.\n\n"
                                    "Your task: Provide intelligent, contextual answers by analyzing patterns across multiple captures and understanding what the user was actually doing."
                                ),
                                input=(
                                    f"Based on my screen activity, please answer: {query_text}\n\n"
                                    f"{apps_summary}\n\n"
                                    f"OCR Text from my screen (organized by relevance):\n{context_text}\n\n"
                                    "INSTRUCTIONS FOR YOUR RESPONSE:\n"
                                    "1. DIRECTLY answer the question first - be specific and actionable\n"
                                    "2. Reference specific evidence from the text (quote relevant parts)\n"
                                    "3. If you see patterns across multiple captures, identify the workflow\n"
                                    "4. Include concrete details: file names, commands, code snippets, timestamps\n"
                                    "5. If the text shows a progression of activity, describe what was being accomplished\n"
                                    "6. Be conversational but precise - this is the user's actual work history\n\n"
                                    "Remember: You're looking at the actual text from their screen. If they ask \"what did I do\", tell them specifically what the text shows they were doing. If they ask \"what did I change\", look for diffs, edits, or modifications in the text."
                                ),
                                max_output_tokens=2000,
                            )
                            
                            ai_answer = getattr(response, "output_text", None)
                            finish_reason = getattr(response, "status", None)
                            debug_info.append(f"Generated AI answer using {model} (len={len(ai_answer) if ai_answer else 0}, finish_reason={finish_reason})")
                            
                            # Debug: Show what we got
                            if not ai_answer or len(ai_answer.strip()) == 0:
                                # Retry once with a shorter context to avoid truncation/garbage
                                debug_info.append("Empty answer; retrying with condensed context (top 10, 200 chars each)")
                                condensed_items = []
                                for j, result in enumerate(search_results[:10]):
                                    ts2 = datetime.fromtimestamp(result["timestamp"])
                                    app2 = result.get("app_name", "Unknown")
                                    window2 = result.get("window_title", "")
                                    text2 = result.get("text", "").strip()
                                    if not text2:
                                        continue
                                    text2 = _sanitize_text(" ".join(text2.split()))[:200]
                                    condensed_items.append(
                                        f"[{ts2.strftime('%Y-%m-%d %H:%M:%S')}] {app2} • {window2}\n{text2}"
                                    )
                                condensed_context = "\n\n".join(condensed_items)
                                response2 = openai_client.responses.create(
                                    model=model,
                                    instructions=(
                                        "You are a helpful assistant that answers questions using short evidence snippets from OCR of the user's screen."
                                    ),
                                    input=(
                                        f"Question: {query_text}\n\nEvidence:\n{condensed_context}\n\nAnswer succinctly and cite snippets."
                                    ),
                                    max_output_tokens=600,
                                )
                                ai_answer = getattr(response2, "output_text", None)
                                finish_reason2 = getattr(response2, "status", None)
                                debug_info.append(f"Retry finish_reason={finish_reason2}, len={len(ai_answer) if ai_answer else 0}")
                                if not ai_answer or len(ai_answer.strip()) == 0:
                                    st.warning(f"⚠️ {model} returned an empty answer")
                                    debug_info.append(f"Empty answer received from {model} after retry")
                                    ai_answer = None  # Clear it so we don't show empty box
                            else:
                                debug_info.append(f"AI answer generated successfully ({len(ai_answer)} chars)")
                            
                        except Exception as e:
                            debug_info.append(f"Failed to generate AI answer: {str(e)}")
                            st.error(f"❌ Could not generate AI answer: {str(e)}")
                            # Check for common issues
                            if "api_key" in str(e).lower():
                                st.error("🔑 Please set OPENAI_API_KEY environment variable")
                            elif "model" in str(e).lower():
                                st.error("🤖 Model issue - the configured model may not be available")
                            ai_answer = None

                    # Display results
                    if not search_results:
                        st.warning("🤷 No results found. Try different keywords or try full-text search!")
                        with st.expander("🐛 Debug Info"):
                            for info in debug_info:
                                st.text(info)
                    else:
                        # Display AI answer prominently at the top
                        if ai_answer:
                            import html
                            safe_answer = html.escape(ai_answer).replace('\n', '<br>')
                            st.markdown(f"""
                            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);\n                                        padding: 2.5rem; border-radius: 1.5rem; color: white; margin-bottom: 2rem;
                                        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);">
                                <h2 style="color: white; margin: 0 0 1rem 0;">🤖 AI Answer</h2>
                                <div style="font-size: 1.1rem; line-height: 1.8; color: white;">
                                    {safe_answer}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # Show debug info if requested
                        if st.checkbox("🐛 Show Debug Info", value=False, key="show_debug"):
                            with st.expander("Debug Information", expanded=True):
                                for info in debug_info:
                                    st.text(info)
                        
                        # Show search results in expander
                        with st.expander(f"📋 View {len(search_results)} Source Frames", expanded=False):
                            for i, result in enumerate(search_results):
                                timestamp = datetime.fromtimestamp(result["timestamp"])

                                # Calculate display score
                                score_text = ""
                                if result.get("score") is not None:
                                    if result["method"] == "semantic":
                                        score_label = "Similarity"
                                        score_val = result["score"]
                                    else:
                                        score_label = "Relevance"
                                        score_val = 1 / (1 + result["score"]) if result["score"] >= 0 else result["score"]
                                    score_text = f"**{score_label}:** {score_val:.1%}"

                                # Result card
                                with st.container():
                                    st.markdown(f"""
                                    <div style="background: rgba(102, 126, 234, 0.1); padding: 1.5rem; border-radius: 0.75rem; margin-bottom: 1rem; border-left: 4px solid #667eea;">
                                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.75rem;">
                                            <h4 style="color: #667eea; margin: 0;">{result['window_title']}</h4>
                                            <span style="color: #aaa; font-size: 0.85rem;">{timestamp.strftime('%Y-%m-%d %H:%M:%S')}</span>
                                        </div>
                                        <div style="margin-bottom: 0.75rem;">
                                            <span style="color: #aaa; font-size: 0.9rem;">{result['app_name']}</span>
                                            {f'<span style="color: #888; margin-left: 1rem; font-size: 0.85rem;">{score_text}</span>' if score_text else ''}
                                        </div>
                                        <div style="color: #e0e0e0; line-height: 1.6;">
                                            {result['text'][:300]}{'...' if len(result['text']) > 300 else ''}
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                                    # View Frame button
                                    if st.button("👁️ View Frame", key=f"view_result_{i}"):
                                        st.session_state['selected_frame'] = result['frame_id']
                                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Search error: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())

        st.markdown("---")

        # Stats row - AT THE TOP
        st.markdown("### 📊 Daily Overview")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="stat-box">
                <h3 style="color: #667eea; margin: 0;">📸 {stats['frame_count']}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #aaa;">Frames Captured</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="stat-box">
                <h3 style="color: #667eea; margin: 0;">📝 {stats['text_count']}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #aaa;">Text Blocks</p>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="stat-box">
                <h3 style="color: #667eea; margin: 0;">💬 {stats['total_chars']:,}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #aaa;">Characters</p>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="stat-box">
                <h3 style="color: #667eea; margin: 0;">🎯 {len(stats['top_apps'])}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #aaa;">Apps Used</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Top apps section - WITH READABLE TEXT
        if stats['top_apps']:
            st.markdown("### 📱 Top Applications")
            for app in stats['top_apps']:
                # Custom styled progress bar with readable text
                progress_value = app['count'] / stats['frame_count']
                st.markdown(f"""
                <div style="margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                        <span style="color: #fafafa; font-weight: 600;">{app['app_name']}</span>
                        <span style="color: #aaa;">{app['count']} frames</span>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.1); border-radius: 0.5rem; height: 0.75rem; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                                    width: {progress_value * 100}%; height: 100%; border-radius: 0.5rem;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # Summary cards with embedded timelines
        if show_summary and stats['frame_count'] > 0:
            with st.spinner("Loading AI summaries..."):
                summaries = self.get_summaries_for_day(selected_datetime)

            if summaries:
                for summary in summaries:
                    start_time = datetime.fromtimestamp(summary['start_timestamp'])
                    end_time = datetime.fromtimestamp(summary['end_timestamp'])

                    # Display summary card
                    st.markdown(f"""
                    <div class="summary-card">
                        <h2>🤖 AI Summary - {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}</h2>
                        <p style="font-size: 1.1rem; line-height: 1.6;">{summary['summary_text']}</p>
                        <p style="font-size: 0.9rem; opacity: 0.8; margin-top: 1rem;">
                            📊 {summary['frame_count']} frames analyzed
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Embedded timeline for this hour
                    frames_by_hour = self.get_frames_for_day(
                        selected_datetime,
                        app_filter=app_filter,
                        start_time=start_time.time(),
                        end_time=end_time.time(),
                        preview_per_hour=10
                    )

                    if frames_by_hour:
                        for hour in sorted(frames_by_hour.keys()):
                            hour_data = frames_by_hour[hour]
                            hour_frames = hour_data['frames']
                            total_frames = hour_data['total']

                            with st.expander(f"⏰ {hour:02d}:00 - {hour:02d}:59 ({total_frames} frames, showing {len(hour_frames)})", expanded=False):
                                cols = st.columns(frames_per_row)
                                for idx, frame in enumerate(hour_frames):
                                    col_idx = idx % frames_per_row

                                    with cols[col_idx]:
                                        frame_path = self.frames_dir / frame['file_path']
                                        if frame_path.exists():
                                            st.image(
                                                str(frame_path),
                                                caption=f"{datetime.fromtimestamp(frame['timestamp']).strftime('%H:%M:%S')}",
                                                use_container_width=True
                                            )
                                            if st.button("View Details", key=f"btn_{summary['start_timestamp']}_{hour}_{frame['frame_id']}"):
                                                st.session_state['selected_frame'] = frame['frame_id']
                                                st.rerun()
            else:
                st.markdown("""
                <div style="padding: 3rem; text-align: center; background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%); border-radius: 1rem; margin: 2rem 0;">
                    <h2 style="color: #667eea; margin-bottom: 1rem;">🤖 No AI Summaries Yet</h2>
                    <p style="font-size: 1.1rem; color: #aaa; margin-bottom: 1.5rem;">
                        AI summaries are generated automatically every hour when Second Brain is running.
                    </p>
                    <div style="background: rgba(255, 255, 255, 0.05); padding: 1.5rem; border-radius: 0.75rem; max-width: 500px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.5); border: 1px solid rgba(102, 126, 234, 0.3);">
                        <p style="color: #fafafa; margin: 0;"><strong>💡 Pro Tip:</strong> Keep Second Brain running to build up your timeline and get insights!</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Selected frame details - enhanced modal-style view
        if 'selected_frame' in st.session_state:
            # Add scroll target and visual indicator
            st.markdown("""
            <div id="frame-details-section" style="scroll-margin-top: 100px;"></div>
            <script>
                // Auto-scroll to frame details
                setTimeout(function() {
                    document.getElementById('frame-details-section').scrollIntoView({behavior: 'smooth', block: 'start'});
                }, 100);
            </script>
            """, unsafe_allow_html=True)

            st.success("📍 **Frame details loaded below!** Scroll down to see full information.")
            st.markdown("---")

            # Header with close button
            col_header, col_close = st.columns([6, 1])
            with col_header:
                st.markdown("""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            padding: 1.5rem; border-radius: 1rem; margin-bottom: 1.5rem;">
                    <h2 style="color: white; margin: 0;">🔍 Frame Details</h2>
                </div>
                """, unsafe_allow_html=True)
            with col_close:
                if st.button("✕ Close", key="close_frame", help="Close frame details"):
                    del st.session_state['selected_frame']
                    st.rerun()

            frame_id = st.session_state['selected_frame']

            # Get frame data with loading indicator
            with st.spinner("Loading frame details..."):
                cursor = self.conn.cursor()
                cursor.execute("SELECT * FROM frames WHERE frame_id = ?", (frame_id,))
                frame = dict(cursor.fetchone())
                text_blocks = self.get_text_for_frame(frame_id)

            # Calculate confidence
            avg_confidence = None
            if text_blocks:
                confidences = [block['confidence'] for block in text_blocks if block.get('confidence')]
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)

            # Enhanced two-column layout
            col1, col2 = st.columns([3, 2])

            with col1:
                # Display full image in a styled container - dark mode
                st.markdown("""
                <div style="background: rgba(255, 255, 255, 0.05); padding: 1rem; border-radius: 1rem;
                            box-shadow: 0 8px 16px rgba(0,0,0,0.5); margin-bottom: 1rem;
                            border: 1px solid rgba(102, 126, 234, 0.2);">
                """, unsafe_allow_html=True)
                frame_path = self.frames_dir / frame['file_path']
                if frame_path.exists():
                    st.image(str(frame_path), use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with col2:
                # Metadata cards with better styling - dark mode
                st.markdown("""
                <div style="background: rgba(255, 255, 255, 0.05); padding: 1.5rem; border-radius: 1rem;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.5); margin-bottom: 1rem;
                            border: 1px solid rgba(102, 126, 234, 0.2);">
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div style="margin-bottom: 1rem;">
                    <p style="color: #888; font-size: 0.85rem; margin: 0;">TIME</p>
                    <p style="color: #fafafa; font-size: 1.1rem; font-weight: 600; margin: 0.25rem 0 0 0;">
                        {datetime.fromtimestamp(frame['timestamp']).strftime('%H:%M:%S')}
                    </p>
                </div>

                <div style="margin-bottom: 1rem;">
                    <p style="color: #888; font-size: 0.85rem; margin: 0;">APPLICATION</p>
                    <p style="color: #fafafa; font-size: 1.1rem; font-weight: 600; margin: 0.25rem 0 0 0;">
                        {frame['app_name']}
                    </p>
                </div>

                <div style="margin-bottom: 1rem;">
                    <p style="color: #888; font-size: 0.85rem; margin: 0;">WINDOW</p>
                    <p style="color: #fafafa; font-size: 0.95rem; margin: 0.25rem 0 0 0;">
                        {frame['window_title']}
                    </p>
                </div>

                <div style="margin-bottom: 1rem;">
                    <p style="color: #888; font-size: 0.85rem; margin: 0;">RESOLUTION</p>
                    <p style="color: #fafafa; font-size: 0.95rem; margin: 0.25rem 0 0 0;">
                        {frame['screen_resolution']}
                    </p>
                </div>
                """, unsafe_allow_html=True)

                if avg_confidence is not None:
                    confidence_color = "#4ade80" if avg_confidence > 0.8 else "#fbbf24" if avg_confidence > 0.5 else "#f87171"
                    st.markdown(f"""
                    <div style="margin-bottom: 1rem;">
                        <p style="color: #888; font-size: 0.85rem; margin: 0;">OCR CONFIDENCE</p>
                        <p style="color: {confidence_color}; font-size: 1.3rem; font-weight: 700; margin: 0.25rem 0 0 0;">
                            {avg_confidence:.1%}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

            # Display OCR text in full width
            st.markdown("### 📝 Extracted Text")
            if text_blocks:
                for block in text_blocks:
                    with st.expander(f"Text Block ({block['block_type']})", expanded=True):
                        st.markdown(f"""
                        <div style="background: rgba(255, 255, 255, 0.05); padding: 1rem; border-radius: 0.5rem;
                                    font-family: monospace; white-space: pre-wrap; line-height: 1.6; color: #e0e0e0;
                                    border: 1px solid rgba(102, 126, 234, 0.2);">
                        {block['text']}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="padding: 2rem; text-align: center; background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%); border-radius: 0.75rem;">
                    <p style="color: #888; margin: 0;">📄 No text content detected in this frame</p>
                </div>
                """, unsafe_allow_html=True)


def main():

    ui = SecondBrainUI()
    ui.run()


if __name__ == "__main__":
    main()
