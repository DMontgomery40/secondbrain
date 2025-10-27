import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import dayjs from "dayjs";
import { SettingsPanel } from "./components/SettingsPanel";

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

type OCREngine = "openai" | "deepseek";

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
  const [engine, setEngine] = useState<OCREngine>("openai");
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
    <section className="ocr-engine-toggle filter-card">
      <h2>OCR Engine</h2>
      <div className="toggle-buttons">
        <button
          className={engine === "openai" ? "active" : ""}
          onClick={() => handleToggle("openai")}
          disabled={isLoading}
        >
          OpenAI GPT-5
        </button>
        <button
          className={engine === "deepseek" ? "active" : ""}
          onClick={() => handleToggle("deepseek")}
          disabled={isLoading}
        >
          DeepSeek OCR
        </button>
      </div>
      <div className="engine-status">
        <p>
          <strong>Currently using:</strong> {engine}
        </p>
        {engine === "openai" && (
          <p className="engine-warning">⚠️ Costs ~$0.01 per frame</p>
        )}
        {engine === "deepseek" && (
          <p className="engine-info">✓ Free, runs locally</p>
        )}
        <p className="engine-note">
          <small>Note: Restart capture service for changes to take effect</small>
        </p>
      </div>
    </section>
  );
}

export default function App() {
  const [appFilter, setAppFilter] = useState<string | null>(null);
  const [startDate, setStartDate] = useState<string | null>(null);
  const [endDate, setEndDate] = useState<string | null>(null);
  const [selectedFrameId, setSelectedFrameId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const framesQuery = useQuery({
    queryKey: ["frames", appFilter, startDate, endDate],
    queryFn: () =>
      fetchFrames({
        app_bundle_id: appFilter,
        start: startDate ? dayjs(startDate).startOf("day").unix() : null,
        end: endDate ? dayjs(endDate).endOf("day").unix() : null
      })
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

  const groupedByDate = useMemo(() => {
    const groups = new Map<string, Frame[]>();
    (framesQuery.data ?? []).forEach((frame) => {
      const dateKey = formatDate(frame.timestamp);
      if (!groups.has(dateKey)) {
        groups.set(dateKey, []);
      }
      groups.get(dateKey)!.push(frame);
    });
    return Array.from(groups.entries())
      .map(([date, frames]) => ({
        date,
        frames: frames.sort((a, b) => a.timestamp - b.timestamp)
      }))
      .sort((a, b) => (a.date > b.date ? -1 : 1));
  }, [framesQuery.data]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Second Brain Timeline</h1>
          <button
            className="settings-button"
            onClick={() => setSettingsOpen(true)}
            title="Settings"
          >
            ⚙️
          </button>
        </div>
        <section className="filter-card">
          <h2>Filters</h2>
          <label className="filter-field">
            <span>Application</span>
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
          </label>
          <label className="filter-field">
            <span>From</span>
            <input
              type="date"
              value={startDate ?? ""}
              onChange={(event) =>
                setStartDate(event.target.value || null)
              }
            />
          </label>
          <label className="filter-field">
            <span>To</span>
            <input
              type="date"
              value={endDate ?? ""}
              onChange={(event) =>
                setEndDate(event.target.value || null)
              }
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
        {framesQuery.isLoading ? (
          <div className="empty-state">Loading frames…</div>
        ) : groupedByDate.length === 0 ? (
          <div className="empty-state">No frames captured for this range.</div>
        ) : (
          groupedByDate.map((group) => (
            <section key={group.date} className="timeline-group">
              <header>
                <h3>{dayjs(group.date).format("dddd, MMM D")}</h3>
              </header>
              <div className="frame-strip">
                {group.frames.map((frame) => (
                  <button
                    key={frame.frame_id}
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
                    />
                    <div className="frame-meta">
                      <span className="frame-time">{formatTime(frame.timestamp)}</span>
                      <span className="frame-title">
                        {frame.window_title || "Untitled"}
                      </span>
                      <span className="frame-app">{frame.app_name}</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ))
        )}
      </main>

      <SettingsPanel
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}
