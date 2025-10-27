import React, { useEffect, useState } from 'react';
import './SettingsPanel.css';

interface Settings {
  capture: {
    fps: number;
    max_disk_usage_gb: number;
    min_free_space_gb: number;
    buffer_enabled: boolean;
    buffer_duration: number;
  };
  ocr: {
    engine: 'openai' | 'deepseek';
    model: string;
    rate_limit_rpm: number;
    deepseek_docker: boolean;
    deepseek_docker_url: string;
    deepseek_mode: string;
    batch_size: number;
  };
  embeddings: {
    enabled: boolean;
    model: string;
  };
  storage: {
    database_path: string;
    screenshots_dir: string;
    max_screenshots: number;
    retention_days: number;
  };
  api: {
    host: string;
    port: number;
    cors_enabled: boolean;
  };
  logging: {
    level: string;
    file: string;
    max_size_mb: number;
  };
  mcp: {
    enabled: boolean;
    port: number;
    transport: string;
  };
}

export function SettingsPanel({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [activeTab, setActiveTab] = useState<keyof Settings>('capture');

  useEffect(() => {
    if (isOpen) {
      loadSettings();
      loadStats();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    const res = await fetch('/api/settings/all');
    const data = await res.json();
    setSettings(data);
    setHasChanges(false);
  };

  const loadStats = async () => {
    const res = await fetch('/api/settings/stats');
    const data = await res.json();
    setStats(data);
  };

  const updateSetting = (category: keyof Settings, key: string, value: any) => {
    setSettings(prev => {
      if (!prev) return prev;
      return { ...prev, [category]: { ...prev[category], [key]: value } } as Settings;
    });
    setHasChanges(true);
  };

  const saveSettings = async () => {
    await fetch('/api/settings/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    setHasChanges(false);
    alert('Settings saved! Some changes may restart the capture service.');
  };

  const resetCategory = async (category: keyof Settings) => {
    if (!confirm(`Reset all ${category} settings to defaults?`)) return;
    await fetch('/api/settings/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category })
    });
    await loadSettings();
  };

  const clearOldScreenshots = async () => {
    if (!settings) return;
    if (!confirm(`Clear screenshots older than ${settings.storage.retention_days} days?`)) return;
    await fetch('/api/settings/maintenance/clear-screenshots', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ retention_days: settings.storage.retention_days })
    });
    await loadStats();
  };

  const compactDatabase = async () => {
    await fetch('/api/settings/maintenance/compact-db', { method: 'POST' });
    await loadStats();
  };

  const downloadLogs = async () => {
    if (!settings) return;
    const file = settings.logging.file || 'capture.log';
    const res = await fetch(`/api/settings/logs?file=${encodeURIComponent(file)}`);
    if (!res.ok) {
      alert('Could not download log file');
      return;
    }
    const text = await res.text();
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  if (!isOpen || !settings) return null;

  return (
    <div className="settings-overlay">
      <div className="settings-panel">
        <div className="settings-header">
          <h2>SecondBrain Settings</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {stats && (
          <div className="stats-bar">
            <span>💾 {stats.database_size_mb}MB</span>
            <span>📸 {stats.screenshot_count} screenshots</span>
            <span>🖼️ {stats.frames_processed_today} today</span>
            <span className={stats.deepseek_docker_running ? 'status-ok' : 'status-error'}>
              🤖 DeepSeek {stats.deepseek_docker_running ? '✓' : '✗'}
            </span>
            <span>💻 RAM {stats.memory_usage_percent}%</span>
          </div>
        )}

        <div className="settings-tabs">
          {(Object.keys(settings) as (keyof Settings)[]).map(category => (
            <button
              key={category}
              className={`tab ${activeTab === category ? 'active' : ''}`}
              onClick={() => setActiveTab(category)}
            >
              {String(category).charAt(0).toUpperCase() + String(category).slice(1)}
            </button>
          ))}
        </div>

        <div className="settings-content">
          {activeTab === 'capture' && (
            <div className="settings-section">
              <h3>Capture Settings</h3>
              <div className="setting-row">
                <label>Frames Per Second (FPS)</label>
                <input type="range" min={0.5} max={5} step={0.5} value={settings.capture.fps}
                  onChange={(e) => updateSetting('capture', 'fps', parseFloat(e.target.value))} />
                <span>{settings.capture.fps} fps</span>
              </div>
              <div className="setting-row">
                <label>Max Disk Usage (GB)</label>
                <input type="number" value={settings.capture.max_disk_usage_gb}
                  onChange={(e) => updateSetting('capture', 'max_disk_usage_gb', parseInt(e.target.value))} />
              </div>
              <div className="setting-row">
                <label>Min Free Space (GB)</label>
                <input type="number" value={settings.capture.min_free_space_gb}
                  onChange={(e) => updateSetting('capture', 'min_free_space_gb', parseInt(e.target.value))} />
              </div>
              <div className="setting-row">
                <label>
                  <input type="checkbox" checked={settings.capture.buffer_enabled}
                    onChange={(e) => updateSetting('capture', 'buffer_enabled', e.target.checked)} />
                  Enable Screenshot Buffering
                </label>
              </div>
              {settings.capture.buffer_enabled && (
                <div className="setting-row indent">
                  <label>Buffer Duration (seconds)</label>
                  <input type="number" value={settings.capture.buffer_duration}
                    onChange={(e) => updateSetting('capture', 'buffer_duration', parseInt(e.target.value))} />
                </div>
              )}
              <button onClick={() => resetCategory('capture')}>Reset to Defaults</button>
            </div>
          )}

          {activeTab === 'ocr' && (
            <div className="settings-section">
              <h3>OCR Settings</h3>
              <div className="setting-row">
                <label>OCR Engine</label>
                <div className="radio-group">
                  <label>
                    <input type="radio" value="openai" checked={settings.ocr.engine === 'openai'}
                      onChange={() => updateSetting('ocr', 'engine', 'openai')} />
                    OpenAI GPT-5 (Costs ~$0.01/frame)
                  </label>
                  <label>
                    <input type="radio" value="deepseek" checked={settings.ocr.engine === 'deepseek'}
                      onChange={() => updateSetting('ocr', 'engine', 'deepseek')} />
                    DeepSeek OCR (Free, Local)
                  </label>
                </div>
              </div>
              {settings.ocr.engine === 'openai' && (
                <>
                  <div className="setting-row">
                    <label>Model</label>
                    <select value={settings.ocr.model} onChange={(e) => updateSetting('ocr', 'model', e.target.value)}>
                      <option value="gpt-5">GPT-5 Vision</option>
                      <option value="gpt-4-vision">GPT-4 Vision</option>
                    </select>
                  </div>
                  <div className="setting-row">
                    <label>Rate Limit (requests/min)</label>
                    <input type="number" value={settings.ocr.rate_limit_rpm}
                      onChange={(e) => updateSetting('ocr', 'rate_limit_rpm', parseInt(e.target.value))} />
                  </div>
                </>
              )}
              {settings.ocr.engine === 'deepseek' && (
                <>
                  <div className="setting-row">
                    <label>
                      <input type="checkbox" checked={settings.ocr.deepseek_docker}
                        onChange={(e) => updateSetting('ocr', 'deepseek_docker', e.target.checked)} />
                      Use Docker Service
                    </label>
                  </div>
                  <div className="setting-row">
                    <label>Docker URL</label>
                    <input type="text" value={settings.ocr.deepseek_docker_url}
                      onChange={(e) => updateSetting('ocr', 'deepseek_docker_url', e.target.value)} />
                  </div>
                  <div className="setting-row">
                    <label>Processing Mode</label>
                    <select value={settings.ocr.deepseek_mode}
                      onChange={(e) => updateSetting('ocr', 'deepseek_mode', e.target.value)}>
                      <option value="tiny">Tiny (64 tokens)</option>
                      <option value="small">Small (100 tokens)</option>
                      <option value="base">Base (256 tokens)</option>
                      <option value="large">Large (400 tokens)</option>
                      <option value="gundam">Gundam (Dynamic)</option>
                      <option value="optimal">Optimal (Auto)</option>
                    </select>
                  </div>
                  <div className="setting-row">
                    <label>Batch Size</label>
                    <input type="number" value={settings.ocr.batch_size}
                      onChange={(e) => updateSetting('ocr', 'batch_size', parseInt(e.target.value))} />
                  </div>
                </>
              )}
              <button onClick={() => resetCategory('ocr')}>Reset to Defaults</button>
            </div>
          )}

          {activeTab === 'embeddings' && (
            <div className="settings-section">
              <h3>Embeddings Settings</h3>
              <div className="setting-row">
                <label>
                  <input type="checkbox" checked={settings.embeddings.enabled}
                    onChange={(e) => updateSetting('embeddings', 'enabled', e.target.checked)} />
                  Enable Semantic Search
                </label>
              </div>
              <div className="setting-row">
                <label>Embedding Model</label>
                <select value={settings.embeddings.model}
                  onChange={(e) => updateSetting('embeddings', 'model', e.target.value)}>
                  <option value="sentence-transformers/all-MiniLM-L6-v2">MiniLM (Fast)</option>
                  <option value="sentence-transformers/all-mpnet-base-v2">MPNet (Accurate)</option>
                  <option value="openai/text-embedding-ada-002">OpenAI Ada (Best)</option>
                </select>
              </div>
              <button onClick={() => resetCategory('embeddings')}>Reset to Defaults</button>
            </div>
          )}

          {activeTab === 'storage' && (
            <div className="settings-section">
              <h3>Storage Settings</h3>
              <div className="setting-row">
                <label>Database Path</label>
                <input type="text" value={settings.storage.database_path} readOnly className="readonly" />
              </div>
              <div className="setting-row">
                <label>Screenshots Directory</label>
                <input type="text" value={settings.storage.screenshots_dir} readOnly className="readonly" />
              </div>
              <div className="setting-row">
                <label>Max Screenshots to Keep</label>
                <input type="number" value={settings.storage.max_screenshots}
                  onChange={(e) => updateSetting('storage', 'max_screenshots', parseInt(e.target.value))} />
              </div>
              <div className="setting-row">
                <label>Retention Days</label>
                <input type="number" value={settings.storage.retention_days}
                  onChange={(e) => updateSetting('storage', 'retention_days', parseInt(e.target.value))} />
                <span className="hint">Screenshots older than this will be deleted</span>
              </div>
              <div className="danger-zone">
                <h4>Danger Zone</h4>
                <button className="danger-btn" onClick={clearOldScreenshots}>Clear Old Screenshots</button>
                <button className="danger-btn" onClick={compactDatabase}>Compact Database</button>
              </div>
            </div>
          )}

          {activeTab === 'api' && (
            <div className="settings-section">
              <h3>API Settings</h3>
              <div className="setting-row">
                <label>Host</label>
                <input type="text" value={settings.api.host}
                  onChange={(e) => updateSetting('api', 'host', e.target.value)} />
              </div>
              <div className="setting-row">
                <label>Port</label>
                <input type="number" value={settings.api.port}
                  onChange={(e) => updateSetting('api', 'port', parseInt(e.target.value))} />
              </div>
              <div className="setting-row">
                <label>
                  <input type="checkbox" checked={settings.api.cors_enabled}
                    onChange={(e) => updateSetting('api', 'cors_enabled', e.target.checked)} />
                  Enable CORS
                </label>
              </div>
            </div>
          )}

          {activeTab === 'logging' && (
            <div className="settings-section">
              <h3>Logging Settings</h3>
              <div className="setting-row">
                <label>Log Level</label>
                <select value={settings.logging.level}
                  onChange={(e) => updateSetting('logging', 'level', e.target.value)}>
                  <option value="DEBUG">Debug</option>
                  <option value="INFO">Info</option>
                  <option value="WARNING">Warning</option>
                  <option value="ERROR">Error</option>
                </select>
              </div>
              <div className="setting-row">
                <label>Log File</label>
                <input type="text" value={settings.logging.file}
                  onChange={(e) => updateSetting('logging', 'file', e.target.value)} />
              </div>
              <div className="setting-row">
                <label>Max Log Size (MB)</label>
                <input type="number" value={settings.logging.max_size_mb}
                  onChange={(e) => updateSetting('logging', 'max_size_mb', parseInt(e.target.value))} />
              </div>
              <button onClick={downloadLogs}>Download Logs</button>
            </div>
          )}

          {activeTab === 'mcp' && (
            <div className="settings-section">
              <h3>MCP Server Settings</h3>
              <div className="setting-row">
                <label>
                  <input type="checkbox" checked={settings.mcp.enabled}
                    onChange={(e) => updateSetting('mcp', 'enabled', e.target.checked)} />
                  Enable MCP Server
                </label>
              </div>
              <div className="setting-row">
                <label>Port</label>
                <input type="number" value={settings.mcp.port}
                  onChange={(e) => updateSetting('mcp', 'port', parseInt(e.target.value))} />
              </div>
              <div className="setting-row">
                <label>Transport</label>
                <select value={settings.mcp.transport}
                  onChange={(e) => updateSetting('mcp', 'transport', e.target.value)}>
                  <option value="stdio">stdio</option>
                  <option value="streamable_http">Streamable HTTP</option>
                  <option value="websocket">WebSocket</option>
                </select>
              </div>
            </div>
          )}
        </div>

        <div className="settings-footer">
          <button className="cancel-btn" onClick={onClose}>Close</button>
          <button className="save-btn" onClick={saveSettings} disabled={!hasChanges}>
            {hasChanges ? 'Save Changes' : 'No Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

