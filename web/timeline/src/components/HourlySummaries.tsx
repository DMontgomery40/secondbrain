import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import dayjs from "dayjs";
import { useState } from "react";
import "./HourlySummaries.css";

type Summary = {
  summary_id: string;
  start_timestamp: number;
  end_timestamp: number;
  summary_type: string;
  summary_text: string;
  frame_count: number;
  app_names: string[];
  created_at: number;
};

interface HourlySummariesProps {
  date: string;  // YYYY-MM-DD format
}

export function HourlySummaries({ date }: HourlySummariesProps) {
  const [expandedSummaries, setExpandedSummaries] = useState<Set<string>>(new Set());

  const summariesQuery = useQuery({
    queryKey: ["summaries", date],
    queryFn: async () => {
      const response = await axios.get(`/api/summaries?date=${date}`);
      return response.data.summaries as Summary[];
    },
    enabled: !!date,
  });

  if (!date) return null;

  if (summariesQuery.isLoading) {
    return (
      <div className="summaries-loading">
        <div className="loading-spinner"></div>
        <p>Generating hourly summaries...</p>
      </div>
    );
  }

  if (summariesQuery.error) {
    return null; // Silently fail if summaries aren't available
  }

  const summaries = summariesQuery.data || [];
  const hourlySummaries = summaries.filter(s => s.summary_type === "hourly");

  if (hourlySummaries.length === 0) {
    return null; // Don't show empty state
  }

  const toggleSummary = (summaryId: string) => {
    setExpandedSummaries(prev => {
      const newSet = new Set(prev);
      if (newSet.has(summaryId)) {
        newSet.delete(summaryId);
      } else {
        newSet.add(summaryId);
      }
      return newSet;
    });
  };

  return (
    <div className="hourly-summaries">
      <h2 className="summaries-title">📊 AI Hourly Summaries</h2>
      <div className="summaries-grid">
        {hourlySummaries.map((summary) => {
          const isExpanded = expandedSummaries.has(summary.summary_id);
          const startTime = dayjs.unix(summary.start_timestamp).format("HH:mm");
          const endTime = dayjs.unix(summary.end_timestamp).format("HH:mm");

          return (
            <div key={summary.summary_id} className="summary-card">
              <div className="summary-header">
                <div className="summary-time-badge">
                  🤖 AI Summary - {startTime} to {endTime}
                </div>
                <button
                  className="summary-toggle"
                  onClick={() => toggleSummary(summary.summary_id)}
                  aria-label={isExpanded ? "Collapse" : "Expand"}
                >
                  {isExpanded ? "▼" : "▶"}
                </button>
              </div>

              <div className={`summary-content ${isExpanded ? "expanded" : ""}`}>
                <p className="summary-text">{summary.summary_text}</p>

                <div className="summary-meta">
                  <span className="meta-item">
                    📸 {summary.frame_count} frames analyzed
                  </span>
                  {summary.app_names && summary.app_names.length > 0 && (
                    <span className="meta-item">
                      💼 Apps: {summary.app_names.join(", ")}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
