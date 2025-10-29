import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import dayjs from "dayjs";
import { SettingsPanel } from "./components/SettingsPanel";
import { HourlySummaries } from "./components/HourlySummaries";
import { DailyStats } from "./components/DailyStats";
import { DopamineButton } from "./components/DopamineButton";
import { LoadingBar } from "./components/LoadingBar";
import { Tooltip } from "./components/Tooltip";
import tipsData from "./tips.json";

type Frame = {
  frame_id: string;
  timestamp: number;
  iso_timestamp: string;
  window_title: string;
  app_name: string;
  app_bundle_id: string;
  file_path: string;
  screenshot_url: string;
};

type TextBlock = {
  block_id: string;
  text: string;
  block_type: string;
};

type AppStat = {
  app_bundle_id: string;
  app_name: string;
  frame_count: number;
};

type OCREngine = "apple" | "deepseek";

const fetchFrames = async (params: {
  app_bundle_id?: string | null;
  start?: number | null;
  end?: number | null;
}) => {
  const response = await axios.get("/api/frames", {
    params: {
      limit: 500,
      app_bundle_id: params.app_bundle_id ?? undefined,
      start: params.start ?? undefined,
      end: params.end ?? undefined
    }
  });
  return response.data.frames as Frame[];
};

const fetchFrameText = async (frameId: string) => {
  const response = await axios.get(`/api/frames/${frameId}/text`);
  return response.data.blocks as TextBlock[];
};

const fetchApps = async () => {
  const response = await axios.get("/api/apps");
  return response.data.apps as AppStat[];
};

const fetchOCREngine = async (): Promise<OCREngine> => {
  const response = await axios.get("/api/settings/ocr-engine");
  return response.data.engine as OCREngine;
};

const setOCREngine = async (engine: OCREngine): Promise<void> => {
  await axios.post("/api/settings/ocr-engine", null, {
    params: { engine }
  });
};

const formatTime = (timestamp: number) =>
  dayjs.unix(timestamp).format("HH:mm:ss");

const formatDate = (timestamp: number) =>
  dayjs.unix(timestamp).format("YYYY-MM-DD");

function OCREngineToggle() {
  const [engine, setEngine] = useState<OCREngine>("apple");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // Get current engine on mount
    fetchOCREngine().then(setEngine).catch(console.error);
  }, []);

  const handleToggle = async (newEngine: OCREngine) => {
    if (newEngine === engine) return;

    setIsLoading(true);
    try {
      await setOCREngine(newEngine);
      setEngine(newEngine);
    } catch (error) {
      console.error("Failed to switch OCR engine:", error);
      alert("Failed to switch OCR engine. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <LoadingBar isLoading={isLoading} message="Switching OCR engine..." />
      <section className="ocr-engine-toggle filter-card">
        <h2>OCR Engine</h2>
        <div className="toggle-buttons">
          <Tooltip content={tipsData.tooltips.ocrEngineApple}>
            <button
              className={engine === "apple" ? "active" : ""}
              onClick={() => handleToggle("apple")}
              disabled={isLoading}
            >
              Apple Vision
            </button>
          </Tooltip>
          <Tooltip content={tipsData.tooltips.ocrEngineDeepSeek}>
            <button
              className={engine === "deepseek" ? "active" : ""}
              onClick={() => handleToggle("deepseek")}
              disabled={isLoading}
            >
              DeepSeek OCR
            </button>
          </Tooltip>
        </div>
        <div className="engine-status">
          <p>
            <strong>Currently using:</strong> {engine}
          </p>
          {engine === "apple" && (
            <p className="engine-info">✓ Local, fast, free (on-device)</p>
          )}
          {engine === "deepseek" && (
            <p className="engine-info">✓ Free, runs locally</p>
          )}
          <p className="engine-note">
            <small>Note: Restart capture service for changes to take effect</small>
          </p>
        </div>
      </section>
    </>
  );
}

export default function App() {
  const [appFilter, setAppFilter] = useState<string | null>(null);
  const [startDate, setStartDate] = useState<string | null>(null);
  const [endDate, setEndDate] = useState<string | null>(null);
  const [startTime, setStartTime] = useState<string | null>(null);
  const [endTime, setEndTime] = useState<string | null>(null);
  const [selectedFrameId, setSelectedFrameId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [zoomedFrame, setZoomedFrame] = useState<Frame | null>(null);
  const [question, setQuestion] = useState("");
  const [useSemantic, setUseSemantic] = useState(true);
  const [useReranker, setUseReranker] = useState(false);
  const [maxResults, setMaxResults] = useState(20);
  const [answer, setAnswer] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  // Query date range states
  const [queryDatePreset, setQueryDatePreset] = useState<"Last 7 Days" | "Last 30 Days" | "All Time" | "Custom Range">("Last 7 Days");
  const [queryStartDate, setQueryStartDate] = useState<string | null>(null);
  const [queryEndDate, setQueryEndDate] = useState<string | null>(null);

  // Calculate query timestamps based on preset
  const getQueryTimestamps = (): { start: number | null; end: number | null } => {
    const now = dayjs();
    if (queryDatePreset === "Last 7 Days") {
      return {
        start: now.subtract(7, "days").startOf("day").unix(),
        end: now.endOf("day").unix(),
      };
    } else if (queryDatePreset === "Last 30 Days") {
      return {
        start: now.subtract(30, "days").startOf("day").unix(),
        end: now.endOf("day").unix(),
      };
    } else if (queryDatePreset === "All Time") {
      return { start: null, end: null };
    } else if (queryDatePreset === "Custom Range") {
      return {
        start: queryStartDate ? dayjs(queryStartDate).startOf("day").unix() : null,
        end: queryEndDate ? dayjs(queryEndDate).endOf("day").unix() : null,
      };
    }
    return { start: null, end: null };
  };

  const framesQuery = useQuery({
    queryKey: ["frames", appFilter, startDate, endDate, startTime, endTime],
    queryFn: () => {
      let startTimestamp: number | null = null;
      let endTimestamp: number | null = null;

      try {
        if (startDate) {
          const startDateTime = dayjs(startDate);
          if (!startDateTime.isValid()) {
            throw new Error(`Invalid start date: ${startDate}`);
          }
          if (startTime) {
            const [hours, minutes] = startTime.split(':').map(Number);
            if (isNaN(hours) || isNaN(minutes)) {
              throw new Error(`Invalid start time: ${startTime}`);
            }
            startTimestamp = startDateTime.hour(hours).minute(minutes).second(0).unix();
          } else {
            startTimestamp = startDateTime.startOf("day").unix();
          }
        }

        if (endDate) {
          const endDateTime = dayjs(endDate);
          if (!endDateTime.isValid()) {
            throw new Error(`Invalid end date: ${endDate}`);
          }
          if (endTime) {
            const [hours, minutes] = endTime.split(':').map(Number);
            if (isNaN(hours) || isNaN(minutes)) {
              throw new Error(`Invalid end time: ${endTime}`);
            }
            endTimestamp = endDateTime.hour(hours).minute(minutes).second(59).unix();
          } else {
            endTimestamp = endDateTime.endOf("day").unix();
          }
        }

        return fetchFrames({
          app_bundle_id: appFilter,
          start: startTimestamp,
          end: endTimestamp
        });
      } catch (error) {
        console.error("Error processing date filters:", error);
        throw error;
      }
    },
    retry: false, // Don't retry on error
  });

  const appsQuery = useQuery({
    queryKey: ["apps"],
    queryFn: fetchApps
  });

  const selectedFrame = useMemo(() => {
    if (!selectedFrameId || !framesQuery.data) {
      return null;
    }
    return framesQuery.data.find((frame) => frame.frame_id === selectedFrameId) ?? null;
  }, [framesQuery.data, selectedFrameId]);

  const frameTextQuery = useQuery({
    queryKey: ["frame-text", selectedFrameId],
    queryFn: () => {
      if (!selectedFrameId) {
        return Promise.resolve<TextBlock[]>([]);
      }
      return fetchFrameText(selectedFrameId);
    },
    enabled: Boolean(selectedFrameId)
  });

  // Group frames by date and hour
  const groupedByDateAndHour = useMemo(() => {
    const dateGroups = new Map<string, Map<number, Frame[]>>();
    (framesQuery.data ?? []).forEach((frame) => {
      const dateKey = formatDate(frame.timestamp);
      const hour = dayjs.unix(frame.timestamp).hour();

      if (!dateGroups.has(dateKey)) {
        dateGroups.set(dateKey, new Map());
      }
      const hourGroups = dateGroups.get(dateKey)!;

      if (!hourGroups.has(hour)) {
        hourGroups.set(hour, []);
      }
      hourGroups.get(hour)!.push(frame);
    });

    return Array.from(dateGroups.entries())
      .map(([date, hourGroups]) => ({
        date,
        hours: Array.from(hourGroups.entries())
          .map(([hour, frames]) => ({
            hour,
            frames: frames.sort((a, b) => a.timestamp - b.timestamp)
          }))
          .sort((a, b) => a.hour - b.hour)
      }))
      .sort((a, b) => (a.date > b.date ? -1 : 1));
  }, [framesQuery.data]);

  // Track expanded hours
  const [expandedHours, setExpandedHours] = useState<Set<string>>(new Set());

  const toggleHour = (dateHourKey: string) => {
    setExpandedHours(prev => {
      const newSet = new Set(prev);
      if (newSet.has(dateHourKey)) {
        newSet.delete(dateHourKey);
      } else {
        newSet.add(dateHourKey);
      }
      return newSet;
    });
  };

  return (
    <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <LoadingBar
        isLoading={framesQuery.isLoading || asking}
        message={framesQuery.isLoading ? "Loading timeline frames..." : asking ? "Asking your Second Brain..." : undefined}
      />
      <aside className="sidebar">
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? '›' : '‹'}
        </button>
        <div className="sidebar-header">
          <h1>Second Brain Timeline</h1>
          <Tooltip content={tipsData.tooltips.settingsButton}>
            <button
              className="settings-button"
              onClick={() => setSettingsOpen(true)}
              title="Settings"
            >
              ⚙️
            </button>
          </Tooltip>
        </div>
        <section className="filter-card">
          <h2>Filters</h2>
          <label className="filter-field">
            <span>Application</span>
            <Tooltip content={tipsData.tooltips.appFilter}>
              <select
                value={appFilter ?? ""}
                onChange={(event) =>
                  setAppFilter(event.target.value ? event.target.value : null)
                }
              >
                <option value="">All applications</option>
                {appsQuery.data?.map((app) => (
                  <option key={app.app_bundle_id} value={app.app_bundle_id}>
                    {app.app_name} ({app.frame_count})
                  </option>
                ))}
              </select>
            </Tooltip>
          </label>
          <label className="filter-field">
            <span>From Date</span>
            <Tooltip content={tipsData.tooltips.startDate}>
              <input
                type="date"
                value={startDate ?? ""}
                onChange={(event) => {
                  const value = event.target.value || null;
                  if (value) {
                    // Validate date format
                    const dateCheck = dayjs(value);
                    if (!dateCheck.isValid()) {
                      console.error("Invalid date format:", value);
                      return;
                    }
                  }
                  setStartDate(value);
                }}
              />
            </Tooltip>
          </label>
          <label className="filter-field">
            <span>From Time</span>
            <input
              type="time"
              value={startTime ?? ""}
              onChange={(event) =>
                setStartTime(event.target.value || null)
              }
              disabled={!startDate}
            />
          </label>
          <label className="filter-field">
            <span>To Date</span>
            <Tooltip content={tipsData.tooltips.endDate}>
              <input
                type="date"
                value={endDate ?? ""}
                onChange={(event) => {
                  const value = event.target.value || null;
                  if (value) {
                    // Validate date format
                    const dateCheck = dayjs(value);
                    if (!dateCheck.isValid()) {
                      console.error("Invalid date format:", value);
                      return;
                    }
                  }
                  setEndDate(value);
                }}
              />
            </Tooltip>
          </label>
          <label className="filter-field">
            <span>To Time</span>
            <input
              type="time"
              value={endTime ?? ""}
              onChange={(event) =>
                setEndTime(event.target.value || null)
              }
              disabled={!endDate}
            />
          </label>
        </section>
        <OCREngineToggle />
        <section className="details-card">
          <h2>Details</h2>
          {selectedFrame ? (
            <>
              <div className="details-meta">
                <strong>{selectedFrame.window_title || "Untitled Window"}</strong>
                <span>{selectedFrame.app_name}</span>
                <span>{dayjs(selectedFrame.iso_timestamp).format("dddd, MMM D YYYY • HH:mm:ss")}</span>
              </div>
              <div className="details-preview">
                <img
                  src={selectedFrame.screenshot_url}
                  alt={selectedFrame.window_title}
                  loading="lazy"
                />
              </div>
              <div className="details-text">
                {frameTextQuery.isLoading && <p>Loading text…</p>}
                {frameTextQuery.data?.map((block) => (
                  <article key={block.block_id}>
                    <header>{block.block_type}</header>
                    <p>{block.text}</p>
                  </article>
                ))}
                {frameTextQuery.data?.length === 0 && !frameTextQuery.isLoading && (
                  <p>No OCR text available.</p>
                )}
              </div>
            </>
          ) : (
            <p>Select a frame from the timeline to view details.</p>
          )}
        </section>
      </aside>

      <main className="timeline-main">
        {/* Show daily stats if we have a single date selected */}
        {startDate && !endDate && (
          <DailyStats date={startDate} />
        )}

        {/* Show hourly summaries if we have a single date selected */}
        {startDate && !endDate && (
          <HourlySummaries date={startDate} />
        )}

        <section className="chat-card">
          <h2 style={{marginTop: 0}}>Ask Your Second Brain</h2>
          <div className="chat-row" style={{marginTop: 8}}>
            <textarea
              placeholder="What was I working on? Which repo did I open?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <div className="chat-controls">
              <Tooltip content={tipsData.tooltips.semanticToggle}>
                <label style={{display: 'flex', gap: 6, alignItems: 'center'}}>
                  <input type="checkbox" checked={useSemantic} onChange={(e) => setUseSemantic(e.target.checked)} />
                  Semantic
                </label>
              </Tooltip>
              <Tooltip content={tipsData.tooltips.rerankerToggle}>
                <label style={{display: 'flex', gap: 6, alignItems: 'center'}}>
                  <input type="checkbox" checked={useReranker} onChange={(e) => setUseReranker(e.target.checked)} disabled={!useSemantic} />
                  Reranker
                </label>
              </Tooltip>
              <Tooltip content={tipsData.tooltips.maxResults}>
                <label style={{display: 'flex', gap: 6, alignItems: 'center'}}>
                  Max
                  <input type="number" min={5} max={50} value={maxResults} onChange={(e) => setMaxResults(parseInt(e.target.value || '20'))} style={{width: 70}} />
                </label>
              </Tooltip>
            </div>
            <div className="chat-controls query-date-controls" style={{marginTop: 8}}>
              <label style={{fontSize: '0.9em', marginRight: 8}}>Date Range:</label>
              <button
                className="query-preset-btn"
                data-preset="last-7-days"
                onClick={() => setQueryDatePreset("Last 7 Days")}
                style={{
                  padding: '4px 8px',
                  fontSize: '0.85em',
                  background: queryDatePreset === "Last 7 Days" ? '#4a90e2' : '#f0f0f0',
                  color: queryDatePreset === "Last 7 Days" ? 'white' : 'black',
                  border: '1px solid #ccc',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                Last 7 Days
              </button>
              <button
                className="query-preset-btn"
                data-preset="last-30-days"
                onClick={() => setQueryDatePreset("Last 30 Days")}
                style={{
                  padding: '4px 8px',
                  fontSize: '0.85em',
                  background: queryDatePreset === "Last 30 Days" ? '#4a90e2' : '#f0f0f0',
                  color: queryDatePreset === "Last 30 Days" ? 'white' : 'black',
                  border: '1px solid #ccc',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                Last 30 Days
              </button>
              <button
                className="query-preset-btn"
                data-preset="all-time"
                onClick={() => setQueryDatePreset("All Time")}
                style={{
                  padding: '4px 8px',
                  fontSize: '0.85em',
                  background: queryDatePreset === "All Time" ? '#4a90e2' : '#f0f0f0',
                  color: queryDatePreset === "All Time" ? 'white' : 'black',
                  border: '1px solid #ccc',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                All Time
              </button>
              <button
                className="query-preset-btn"
                data-preset="custom"
                onClick={() => setQueryDatePreset("Custom Range")}
                style={{
                  padding: '4px 8px',
                  fontSize: '0.85em',
                  background: queryDatePreset === "Custom Range" ? '#4a90e2' : '#f0f0f0',
                  color: queryDatePreset === "Custom Range" ? 'white' : 'black',
                  border: '1px solid #ccc',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                Custom
              </button>
              {queryDatePreset === "Custom Range" && (
                <>
                  <label style={{marginLeft: 12, fontSize: '0.85em'}}>From:</label>
                  <input
                    type="date"
                    className="query-date-input"
                    data-query-date="start"
                    value={queryStartDate ?? ""}
                    onChange={(e) => setQueryStartDate(e.target.value || null)}
                    style={{fontSize: '0.85em', padding: '2px 4px'}}
                  />
                  <label style={{marginLeft: 8, fontSize: '0.85em'}}>To:</label>
                  <input
                    type="date"
                    className="query-date-input"
                    data-query-date="end"
                    value={queryEndDate ?? ""}
                    onChange={(e) => setQueryEndDate(e.target.value || null)}
                    style={{fontSize: '0.85em', padding: '2px 4px'}}
                  />
                </>
              )}
            </div>
            <div className="chat-controls" style={{marginTop: 8}}>
              <Tooltip content={tipsData.tooltips.askButton}>
                <DopamineButton
                  className="ask-button"
                  variant="primary"
                  disabled={!question.trim() || asking}
                  onClick={async () => {
                    setAsking(true);
                    setAnswer(null);
                    try {
                      // Use timeline date filters if set, otherwise use query date preset
                      let startTimestamp: number | null = null;
                      let endTimestamp: number | null = null;
                      
                      if (startDate || endDate) {
                        // Use timeline filters
                        if (startDate) {
                          const startDateTime = dayjs(startDate);
                          if (startTime) {
                            const [hours, minutes] = startTime.split(':').map(Number);
                            startTimestamp = startDateTime.hour(hours).minute(minutes).second(0).unix();
                          } else {
                            startTimestamp = startDateTime.startOf("day").unix();
                          }
                        }
                        if (endDate) {
                          const endDateTime = dayjs(endDate);
                          if (endTime) {
                            const [hours, minutes] = endTime.split(':').map(Number);
                            endTimestamp = endDateTime.hour(hours).minute(minutes).second(59).unix();
                          } else {
                            endTimestamp = endDateTime.endOf("day").unix();
                          }
                        }
                      } else {
                        // Use query date preset
                        const timestamps = getQueryTimestamps();
                        startTimestamp = timestamps.start;
                        endTimestamp = timestamps.end;
                      }

                      const res = await axios.post('/api/ask', {
                        query: question,
                        limit: maxResults,
                        app_bundle_id: appFilter,
                        semantic: useSemantic,
                        reranker: useReranker,
                        start: startTimestamp,
                        end: endTimestamp,
                      });
                      
                      const answerText = res.data?.answer;
                      const results = res.data?.results || [];
                      
                      // Handle None/null/empty responses
                      if (answerText && answerText !== "None" && answerText.trim()) {
                        setAnswer(answerText);
                      } else if (results.length === 0) {
                        setAnswer(`No matching frames found for your query "${question}". Try:\n\n• Removing date filters if you have any set\n• Using different keywords\n• Checking if frames have been captured for the selected date range`);
                      } else {
                        setAnswer(`Found ${results.length} matching frame(s) but couldn't generate an answer. Try refining your question or checking if OCR text is available for those frames.`);
                      }
                    } catch (err: any) {
                      console.error("Error asking question:", err);
                      setAnswer(`Error: ${err?.response?.data?.detail || err.message}`);
                    } finally {
                      setAsking(false);
                    }
                  }}
                >
                  {asking ? 'Thinking…' : 'Ask'}
                </DopamineButton>
              </Tooltip>
            </div>
          </div>
          {answer && (
            <div className="ai-answer" style={{marginTop: 12}}>
              <h3 style={{marginTop: 0}}>🤖 AI Answer</h3>
              <div style={{whiteSpace: 'pre-wrap'}}>{answer}</div>
            </div>
          )}
        </section>

        {framesQuery.isLoading ? (
          <div className="empty-state">
            <div className="loading-spinner"></div>
            <p>Loading frames…</p>
          </div>
        ) : framesQuery.error ? (
          <div className="empty-state empty-state-creative">
            <div className="empty-icon">⚠️</div>
            <h3>Error Loading Timeline</h3>
            <p>{framesQuery.error instanceof Error ? framesQuery.error.message : String(framesQuery.error)}</p>
            <p className="empty-hint">💡 Try clearing your date filters and selecting a different date range.</p>
          </div>
        ) : groupedByDateAndHour.length === 0 ? (
          <div className="empty-state empty-state-creative">
            <div className="empty-icon">🔍</div>
            <h3>No Frames Captured Yet</h3>
            <p>Start capturing your screen activity to build your visual memory timeline.</p>
            <p className="empty-hint">💡 Tip: Adjust your date range or app filters to see more frames.</p>
          </div>
        ) : (
          groupedByDateAndHour.map((dayGroup) => (
            <section key={dayGroup.date} className="timeline-day-group">
              <header className="day-header">
                <h3>{dayjs(dayGroup.date).format("dddd, MMM D, YYYY")}</h3>
                <span className="day-frame-count">
                  {dayGroup.hours.reduce((sum, h) => sum + h.frames.length, 0)} frames
                </span>
              </header>

              {dayGroup.hours.map((hourGroup) => {
                const hourKey = `${dayGroup.date}-${hourGroup.hour}`;
                const isExpanded = expandedHours.has(hourKey);
                const hourStart = `${hourGroup.hour.toString().padStart(2, '0')}:00`;
                const hourEnd = `${hourGroup.hour.toString().padStart(2, '0')}:59`;

                return (
                  <div key={hourKey} className="hour-group">
                    <div className="hour-header">
                      <button
                        className="hour-toggle"
                        onClick={() => toggleHour(hourKey)}
                      >
                        <span className="toggle-icon">{isExpanded ? '▼' : '▶'}</span>
                        <span className="hour-label">
                          {hourStart} - {hourEnd}
                        </span>
                        <span className="hour-badge">
                          {hourGroup.frames.length} frames
                        </span>
                      </button>
                    </div>

                    {isExpanded && (
                      <div className="frame-strip">
                        {hourGroup.frames.map((frame) => (
                          <Tooltip key={frame.frame_id} content={tipsData.tooltips.frameCard} position="bottom">
                            <button
                              className={`frame-card ${
                                frame.frame_id === selectedFrameId ? "active" : ""
                              }`}
                              onClick={() => setSelectedFrameId(frame.frame_id)}
                            >
                              <img
                                src={frame.screenshot_url}
                                alt={frame.window_title}
                                loading="lazy"
                                onError={(event) => {
                                  (event.currentTarget as HTMLImageElement).style.visibility = "hidden";
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setZoomedFrame(frame);
                                }}
                                style={{ cursor: 'zoom-in' }}
                              />
                              <div className="frame-meta">
                                <span className="frame-time">{formatTime(frame.timestamp)}</span>
                                <span className="frame-title">
                                  {frame.window_title || "Untitled"}
                                </span>
                                <span className="frame-app">{frame.app_name}</span>
                              </div>
                            </button>
                          </Tooltip>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </section>
          ))
        )}
      </main>

      <SettingsPanel
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />

      {zoomedFrame && (
        <div className="zoom-modal" onClick={() => setZoomedFrame(null)}>
          <div className="zoom-modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="zoom-close" onClick={() => setZoomedFrame(null)}>✕</button>
            <div className="zoom-header">
              <h2>{zoomedFrame.window_title || "Untitled"}</h2>
              <p>{zoomedFrame.app_name} • {dayjs(zoomedFrame.iso_timestamp).format("MMM D, YYYY HH:mm:ss")}</p>
            </div>
            <img
              src={zoomedFrame.screenshot_url}
              alt={zoomedFrame.window_title}
              className="zoom-image"
            />
            {frameTextQuery.data && frameTextQuery.data.length > 0 && (
              <div className="zoom-text">
                <h3>OCR Text</h3>
                <div className="zoom-text-blocks">
                  {frameTextQuery.data.map((block) => (
                    <div key={block.block_id} className="zoom-text-block">
                      <span className="block-type">{block.block_type}</span>
                      <p>{block.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
