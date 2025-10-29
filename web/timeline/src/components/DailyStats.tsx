import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import "./DailyStats.css";

type DailyStatsData = {
  date: string;
  frame_count: number;
  text_block_count: number;
  total_characters: number;
  app_count: number;
};

interface DailyStatsProps {
  date: string;  // YYYY-MM-DD format
}

export function DailyStats({ date }: DailyStatsProps) {
  const statsQuery = useQuery({
    queryKey: ["daily-stats", date],
    queryFn: async () => {
      if (!date) return null;
      try {
        const response = await axios.get(`/api/stats/daily?date=${date}`);
        return response.data as DailyStatsData;
      } catch (error: any) {
        console.error("Error fetching daily stats:", error);
        // Don't throw - return null to silently fail
        return null;
      }
    },
    enabled: !!date,
    retry: false,
  });

  if (!date || statsQuery.isLoading) {
    return null;
  }

  if (statsQuery.error || !statsQuery.data) {
    return null; // Silently fail
  }

  const stats = statsQuery.data;

  if (stats.frame_count === 0) {
    return null; // Don't show stats if no frames
  }

  return (
    <div className="daily-stats">
      <h2 className="stats-title">📈 Daily Overview</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">📸</div>
          <div className="stat-value">{stats.frame_count.toLocaleString()}</div>
          <div className="stat-label">Frames Captured</div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📝</div>
          <div className="stat-value">{stats.text_block_count.toLocaleString()}</div>
          <div className="stat-label">Text Blocks</div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🔤</div>
          <div className="stat-value">{stats.total_characters.toLocaleString()}</div>
          <div className="stat-label">Characters Extracted</div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">💼</div>
          <div className="stat-value">{stats.app_count}</div>
          <div className="stat-label">Apps Used</div>
        </div>
      </div>
    </div>
  );
}
