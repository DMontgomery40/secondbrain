import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './SettingsPanel.css';

interface Settings {
  capture: {
    fps: number;
    format: string;
    quality: number;
    max_disk_usage_gb: number;
    min_free_space_gb: number;
  };
  ocr: {
    engine: 'apple' | 'deepseek';
    batch_size: number;
    max_retries: number;
    include_semantic_context: boolean;
    timeout_seconds: number;
    buffer_duration: number;
    // Apple Vision
    recognition_level?: 'fast' | 'accurate';
    // DeepSeek options (MLX backend only)
    deepseek_mode?: string;
    deepseek_model?: string; // MLX HF model id
    mlx_max_tokens?: number;
    mlx_temperature?: number;
  };
  storage: {
    retention_days: number;
    compression: boolean;
  };
  embeddings: {
    enabled: boolean;
    provider: 'sbert' | 'openai';
    model: string; // SBERT model
    openai_model?: string; // OpenAI embedding model
    reranker_enabled?: boolean;
    reranker_model?: string;
  };
  _paths?: {
    database: string;
    screenshots: string;
    embeddings: string;
    logs: string;
    config: string;
  };
}

interface SystemStats {
  database_size_mb: number;
  screenshots_size_gb: number;
  screenshot_count: number;
  frames_in_db: number;
  text_blocks: number;
  memory_usage_percent: number;
  disk_free_gb: number;
}

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [activeTab, setActiveTab] = useState('capture');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
      loadStats();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    try {
      const res = await axios.get('/api/settings/all');
      setSettings(normalizeSettings(res.data));
    } catch (error) {
      console.error('Failed to load settings:', error);
      alert('Failed to load settings');
    }
  };

  const normalizeSettings = (raw: any): Settings => {
    const ocr = raw.ocr || {};
    return {
      capture: {
        fps: raw.capture?.fps ?? 1,
        format: raw.capture?.format ?? 'png',
        quality: raw.capture?.quality ?? 85,
        max_disk_usage_gb: raw.capture?.max_disk_usage_gb ?? 100,
        min_free_space_gb: raw.capture?.min_free_space_gb ?? 10,
      },
      ocr: {
        engine: (ocr.engine === 'deepseek' ? 'deepseek' : 'apple'),
        batch_size: ocr.batch_size ?? 5,
        max_retries: ocr.max_retries ?? 3,
        include_semantic_context: !!ocr.include_semantic_context,
        timeout_seconds: ocr.timeout_seconds ?? 30,
        buffer_duration: ocr.buffer_duration ?? 30,
        recognition_level: (ocr.recognition_level === 'fast' ? 'fast' : 'accurate'),
        deepseek_mode: ocr.deepseek_mode ?? 'optimal',
        deepseek_model: ocr.deepseek_model ?? 'mlx-community/DeepSeek-OCR-4bit',
        mlx_max_tokens: ocr.mlx_max_tokens ?? 8192,
        mlx_temperature: ocr.mlx_temperature ?? 0.0,
        mlx_repetition_penalty: ocr.mlx_repetition_penalty ?? 1.2,
      },
      storage: {
        retention_days: raw.storage?.retention_days ?? 90,
        compression: !!raw.storage?.compression,
      },
      embeddings: {
        enabled: !!raw.embeddings?.enabled,
        provider: raw.embeddings?.provider ?? 'sbert',
        model: raw.embeddings?.model ?? 'sentence-transformers/all-MiniLM-L6-v2',
        openai_model: raw.embeddings?.openai_model ?? 'text-embedding-3-small',
        reranker_enabled: !!raw.embeddings?.reranker_enabled,
        reranker_model: raw.embeddings?.reranker_model ?? 'BAAI/bge-reranker-large',
      },
      _paths: raw._paths,
    };
  };

  const loadStats = async () => {
    try {
      const res = await axios.get('/api/settings/stats');
      setStats(res.data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const updateSetting = (category: string, key: string, value: any) => {
    if (!settings) return;

    setSettings({
      ...settings,
      [category]: {
        ...(settings as any)[category],
        [key]: value
      }
    });
    setHasChanges(true);
  };

  const saveSettings = async () => {
    if (!settings) return;

    setSaving(true);
    try {
      const { _paths, ...settingsToSave } = settings;
      await axios.post('/api/settings/update', settingsToSave);
      setHasChanges(false);
      alert('Settings saved! Some changes may require restarting the capture service.');
    } catch (error: any) {
      console.error('Failed to save settings:', error);
      const detail = error?.response?.data?.detail;
      if (detail && detail.errors) {
        const errs = detail.errors as Record<string, string>;
        const first = Object.entries(errs)[0];
        alert(`Validation error: ${first[0]} ${first[1]}`);
      } else if (typeof detail === 'string') {
        alert(`Error: ${detail}`);
      } else {
        alert('Failed to save settings');
      }
    } finally {
      setSaving(false);
    }
  };

  const resetCategory = async (category: string) => {
    if (!confirm(`Reset all ${category} settings to defaults?`)) return;

    try {
      await axios.post('/api/settings/reset', null, { params: { category } });
      await loadSettings();
      setHasChanges(false);
    } catch (error) {
      console.error('Failed to reset:', error);
      alert('Failed to reset settings');
    }
  };

  if (!isOpen || !settings) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>SecondBrain Settings</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {stats && (
          <div className="stats-bar">
            <span>💾 {stats.database_size_mb}MB</span>
            <span>📸 {stats.screenshot_count} screenshots</span>
            <span>🖼️ {stats.frames_in_db} frames</span>
            <span>💻 RAM {stats.memory_usage_percent}%</span>
            <span>💿 {stats.disk_free_gb}GB free</span>
          </div>
        )}

        <div className="settings-tabs">
          {['capture','ocr','storage','embeddings'].map(category => (
            <button
              key={category}
              className={`tab ${activeTab === category ? 'active' : ''}`}
              onClick={() => setActiveTab(category)}
            >
              {category.charAt(0).toUpperCase() + category.slice(1)}
            </button>
          ))}
        </div>

        <div className="settings-content">
          {/* CAPTURE SETTINGS */}
          {activeTab === 'capture' && (
            <div className="settings-section">
              <h3>Capture Settings</h3>

              <div className="setting-row">
                <label>Frames Per Second (FPS)</label>
                <input
                  type="range"
                  min="0.5"
                  max="5"
                  step="0.5"
                  value={settings.capture.fps}
                  onChange={(e) => updateSetting('capture', 'fps', parseFloat(e.target.value))}
                />
                <span>{settings.capture.fps} fps</span>
              </div>

              <div className="setting-row">
                <label>Image Format</label>
                <select
                  value={settings.capture.format}
                  onChange={(e) => updateSetting('capture', 'format', e.target.value)}
                >
                  <option value="png">PNG (Lossless)</option>
                  <option value="jpg">JPG (Compressed)</option>
                </select>
              </div>

              <div className="setting-row">
                <label>Image Quality (1-100)</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={settings.capture.quality}
                  onChange={(e) => updateSetting('capture', 'quality', parseInt(e.target.value))}
                />
              </div>

              <div className="setting-row">
                <label>Max Disk Usage (GB)</label>
                <input
                  type="number"
                  value={settings.capture.max_disk_usage_gb}
                  onChange={(e) => updateSetting('capture', 'max_disk_usage_gb', parseInt(e.target.value))}
                />
                <span className="hint">Stop capturing when total usage exceeds this</span>
              </div>

              <div className="setting-row">
                <label>Min Free Space (GB)</label>
                <input
                  type="number"
                  value={settings.capture.min_free_space_gb}
                  onChange={(e) => updateSetting('capture', 'min_free_space_gb', parseInt(e.target.value))}
                />
                <span className="hint">Stop capturing when disk space drops below this</span>
              </div>

              <button className="reset-btn" onClick={() => resetCategory('capture')}>Reset to Defaults</button>
            </div>
          )}

          {/* OCR SETTINGS */}
          {activeTab === 'ocr' && (
            <div className="settings-section">
              <h3>OCR Settings</h3>

              <div className="setting-row">
                <label>OCR Engine</label>
                <div className="radio-group">
                  <label>
                    <input
                      type="radio"
                      value="apple"
                      checked={settings.ocr.engine === 'apple'}
                      onChange={() => updateSetting('ocr', 'engine', 'apple')}
                    />
                    Apple Vision (Local, Free)
                  </label>
                  <label>
                    <input
                      type="radio"
                      value="deepseek"
                      checked={settings.ocr.engine === 'deepseek'}
                      onChange={() => updateSetting('ocr', 'engine', 'deepseek')}
                    />
                    DeepSeek OCR (Free, runs locally)
                  </label>
                </div>
              </div>

              {settings.ocr.engine === 'apple' && (
                <>
                  <div className="setting-row">
                    <label>Recognition Level</label>
                    <select
                      value={settings.ocr.recognition_level || 'accurate'}
                      onChange={(e) => updateSetting('ocr', 'recognition_level', e.target.value)}
                    >
                      <option value="fast">Fast</option>
                      <option value="accurate">Accurate</option>
                    </select>
                  </div>
                </>
              )}

              {settings.ocr.engine === 'deepseek' && (
                <>
                  <div className="setting-row">
                    <label>MLX Model (HF Id)</label>
                    <input
                      type="text"
                      value={settings.ocr.deepseek_model || 'mlx-community/DeepSeek-OCR-4bit'}
                      onChange={(e) => updateSetting('ocr', 'deepseek_model', e.target.value)}
                    />
                    <span className="hint">Downloaded on first run</span>
                  </div>
                  <div className="setting-row">
                    <label>MLX Max Tokens</label>
                    <input
                      type="number"
                      value={settings.ocr.mlx_max_tokens || 8192}
                      onChange={(e) => updateSetting('ocr', 'mlx_max_tokens', parseInt(e.target.value))}
                    />
                  </div>
                  <div className="setting-row">
                    <label>MLX Temperature</label>
                    <input
                      type="number"
                      step="0.1"
                      value={settings.ocr.mlx_temperature ?? 0.0}
                      onChange={(e) => updateSetting('ocr', 'mlx_temperature', parseFloat(e.target.value))}
                    />
                  </div>
                  <div className="setting-row">
                    <label>MLX Repetition Penalty</label>
                    <input
                      type="number"
                      step="0.1"
                      value={settings.ocr.mlx_repetition_penalty ?? 1.2}
                      onChange={(e) => updateSetting('ocr', 'mlx_repetition_penalty', parseFloat(e.target.value))}
                    />
                    <span className="hint">Prevents hallucination loops (1.0-2.0)</span>
                  </div>

                  <div className="setting-row">
                    <label>Processing Mode</label>
                    <select
                      value={settings.ocr.deepseek_mode}
                      onChange={(e) => updateSetting('ocr', 'deepseek_mode', e.target.value)}
                    >
                      <option value="tiny">Tiny (64 tokens, fastest)</option>
                      <option value="small">Small (100 tokens)</option>
                      <option value="base">Base (256 tokens)</option>
                      <option value="large">Large (400 tokens)</option>
                      <option value="gundam">Gundam (Dynamic)</option>
                      <option value="optimal">Optimal (Auto)</option>
                    </select>
                  </div>
                </>
              )}

              <div className="setting-row">
                <label>Batch Size</label>
                <input
                  type="number"
                  value={settings.ocr.batch_size}
                  onChange={(e) => updateSetting('ocr', 'batch_size', parseInt(e.target.value))}
                />
                <span className="hint">Number of frames to process together</span>
              </div>

              <div className="setting-row">
                <label>Max Retries</label>
                <input
                  type="number"
                  value={settings.ocr.max_retries}
                  onChange={(e) => updateSetting('ocr', 'max_retries', parseInt(e.target.value))}
                />
              </div>

              <div className="setting-row">
                <label>Timeout (seconds)</label>
                <input
                  type="number"
                  value={settings.ocr.timeout_seconds}
                  onChange={(e) => updateSetting('ocr', 'timeout_seconds', parseInt(e.target.value))}
                />
              </div>

              <div className="setting-row">
                <label>
                  <input
                    type="checkbox"
                    checked={settings.ocr.include_semantic_context}
                    onChange={(e) => updateSetting('ocr', 'include_semantic_context', e.target.checked)}
                  />
                  Include semantic context in OCR
                </label>
              </div>

              <button className="reset-btn" onClick={() => resetCategory('ocr')}>Reset to Defaults</button>
            </div>
          )}

          {/* STORAGE SETTINGS */}
          {activeTab === 'storage' && (
            <div className="settings-section">
              <h3>Storage Settings</h3>

              {settings._paths && (
                <>
                  <div className="setting-row">
                    <label>Database Path</label>
                    <input
                      type="text"
                      value={settings._paths.database}
                      readOnly
                      className="readonly"
                    />
                  </div>

                  <div className="setting-row">
                    <label>Screenshots Directory</label>
                    <input
                      type="text"
                      value={settings._paths.screenshots}
                      readOnly
                      className="readonly"
                    />
                  </div>
                </>
              )}

              <div className="setting-row">
                <label>Retention Days</label>
                <input
                  type="number"
                  value={settings.storage.retention_days}
                  onChange={(e) => updateSetting('storage', 'retention_days', parseInt(e.target.value))}
                />
                <span className="hint">Screenshots older than this will be eligible for cleanup</span>
              </div>

              <div className="setting-row">
                <label>
                  <input
                    type="checkbox"
                    checked={settings.storage.compression}
                    onChange={(e) => updateSetting('storage', 'compression', e.target.checked)}
                  />
                  Enable compression
                </label>
              </div>

              <button className="reset-btn" onClick={() => resetCategory('storage')}>Reset to Defaults</button>
            </div>
          )}

          {/* EMBEDDINGS SETTINGS */}
          {activeTab === 'embeddings' && (
            <div className="settings-section">
              <h3>Embeddings Settings</h3>

              <div className="setting-row">
                <label>
                  <input
                    type="checkbox"
                    checked={settings.embeddings.enabled}
                    onChange={(e) => updateSetting('embeddings', 'enabled', e.target.checked)}
                  />
                  Enable Semantic Search
                </label>
              </div>

              <div className="setting-row">
                <label>Provider</label>
                <select
                  value={settings.embeddings.provider || 'sbert'}
                  onChange={(e) => updateSetting('embeddings', 'provider', e.target.value)}
                  disabled={!settings.embeddings.enabled}
                >
                  <option value="sbert">SentenceTransformers (local)</option>
                  <option value="openai">OpenAI (API)</option>
                </select>
              </div>

              {(!settings.embeddings.provider || settings.embeddings.provider === 'sbert') && (
                <div className="setting-row">
                  <label>SBERT Model</label>
                  <select
                    value={settings.embeddings.model}
                    onChange={(e) => updateSetting('embeddings', 'model', e.target.value)}
                    disabled={!settings.embeddings.enabled}
                  >
                    <option value="sentence-transformers/all-MiniLM-L6-v2">MiniLM (Fast, 384-dim)</option>
                    <option value="sentence-transformers/all-mpnet-base-v2">MPNet (Accurate, 768-dim)</option>
                  </select>
                </div>
              )}

              {settings.embeddings.provider === 'openai' && (
                <div className="setting-row">
                  <label>OpenAI Embedding Model</label>
                  <select
                    value={settings.embeddings.openai_model || 'text-embedding-3-small'}
                    onChange={(e) => updateSetting('embeddings', 'openai_model', e.target.value)}
                    disabled={!settings.embeddings.enabled}
                  >
                    <option value="text-embedding-3-small">text-embedding-3-small</option>
                    <option value="text-embedding-3-large">text-embedding-3-large</option>
                  </select>
                </div>
              )}

              <div className="setting-row">
                <label>
                  <input
                    type="checkbox"
                    checked={!!settings.embeddings.reranker_enabled}
                    onChange={(e) => updateSetting('embeddings', 'reranker_enabled', e.target.checked)}
                    disabled={!settings.embeddings.enabled}
                  />
                  Enable BAAI/bge Reranker
                </label>
              </div>

              {settings.embeddings.reranker_enabled && (
                <div className="setting-row">
                  <label>Reranker Model</label>
                  <input
                    type="text"
                    value={settings.embeddings.reranker_model || 'BAAI/bge-reranker-large'}
                    onChange={(e) => updateSetting('embeddings', 'reranker_model', e.target.value)}
                    disabled={!settings.embeddings.enabled}
                  />
                </div>
              )}

              <button className="reset-btn" onClick={() => resetCategory('embeddings')}>Reset to Defaults</button>
            </div>
          )}

          
        </div>

        <div className="settings-footer">
          <button className="cancel-btn" onClick={onClose}>Cancel</button>
          <button
            className="save-btn"
            onClick={saveSettings}
            disabled={!hasChanges || saving}
          >
            {saving ? 'Saving...' : hasChanges ? 'Save Changes' : 'No Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
