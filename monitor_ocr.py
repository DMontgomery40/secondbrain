import os
import sqlite3
from datetime import datetime, timedelta

from src.second_brain.config import Config


def main() -> None:
    cfg = Config()
    db_path = cfg.get_database_dir() / "memory.db"
    # Expand user and environment vars
    db = sqlite3.connect(str(db_path))

    since = int((datetime.now() - timedelta(days=1)).timestamp())
    cursor = db.execute(
        """
        SELECT 
            COALESCE(ocr_engine, 'openai') as engine,
            COUNT(*) as blocks,
            AVG(LENGTH(text)) as avg_text_len,
            AVG(confidence) as avg_confidence,
            AVG(compression_ratio) as avg_compression
        FROM text_blocks tb
        JOIN frames f ON tb.frame_id = f.frame_id
        WHERE f.timestamp > ?
        GROUP BY engine
        ORDER BY blocks DESC
        """,
        (since,),
    )

    print("OCR Performance (Last 24h)")
    print("-" * 50)
    rows = cursor.fetchall()
    if not rows:
        print("No OCR data found in the last 24 hours.")
        return
    for row in rows:
        engine, blocks, avg_len, avg_conf, avg_comp = row
        print(f"{engine}:")
        print(f"  Blocks: {blocks}")
        print(f"  Avg Text: {avg_len or 0:.0f} chars")
        if avg_conf is not None:
            print(f"  Confidence: {avg_conf:.2f}")
        else:
            print("  Confidence: N/A")
        if avg_comp is not None:
            print(f"  Compression: {avg_comp:.1f}x")
        else:
            print("  Compression: N/A")


if __name__ == "__main__":
    main()

