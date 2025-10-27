import { useEffect, useState } from "react";

export default function OCREngineToggle() {
  const [engine, setEngine] = useState<"openai" | "deepseek">("openai");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/settings/ocr-engine")
      .then((r) => r.json())
      .then((data) => setEngine(data.engine || "openai"))
      .catch(() => {});
  }, []);

  const handleToggle = async (newEngine: "openai" | "deepseek") => {
    if (newEngine === engine) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/settings/ocr-engine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engine: newEngine }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || "Failed to switch engine");
      }
      setEngine(newEngine);
    } catch (e: any) {
      setError(e?.message || "Error switching engine");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ocr-engine-toggle">
      <label>OCR Engine:</label>
      <div className="toggle-buttons">
        <button
          className={engine === "openai" ? "active" : ""}
          onClick={() => handleToggle("openai")}
          disabled={loading}
          title="Accurate, uses OpenAI Vision"
        >
          OpenAI GPT-5 (Accurate, $$$)
        </button>
        <button
          className={engine === "deepseek" ? "active" : ""}
          onClick={() => handleToggle("deepseek")}
          disabled={loading}
          title="Local DeepSeek OCR"
        >
          DeepSeek OCR (Free, Local)
        </button>
      </div>
      <p className="engine-status">
        Currently using: <strong>{engine}</strong>
        {engine === "openai" && " (⚠️ Costs ~$0.01/frame)"}
        {engine === "deepseek" && " (✓ Free, runs locally)"}
      </p>
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

