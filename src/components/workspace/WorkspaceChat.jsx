import React, { useState, useRef, useEffect } from 'react';
import { 
  Plus, Brain, Image as ImageIcon, ChevronDown, ArrowUp, 
  Sparkles, Check, Store, TrendingUp, AlertTriangle, 
  BarChart3, Layers, Database, ArrowRight, RefreshCw, Copy, CheckCircle2, FileText, Download
} from 'lucide-react';
import { api } from '../../lib/api';
import { downloadCsv } from '../../lib/csv';
import AnalyticsChart from './AnalyticsChart';
import UploadCSVButton from './UploadCSVButton';
import { useAuth } from '../../context/AuthContext';

const STORES = [
  { id: 'amazon', name: 'Amazon', isSelected: true },
  { id: 'shopify', name: 'Shopify', isNew: true },
  { id: 'ebay', name: 'eBay' },
  { id: 'etsy', name: 'Etsy' },
  { id: 'woocommerce', name: 'WooCommerce' },
  { id: 'aliexpress', name: 'AliExpress' },
  { id: 'walmart', name: 'Walmart' },
];

const MORE_STORES = [
  'TikTok Shop',
  'BigCommerce',
  'Magento / Adobe',
  'Target Plus',
  'Mercado Libre',
  'Square POS',
  'Custom GraphQL Store'
];

const MODELS = [
  { id: 'merchlayer-2.0', name: 'Merchlayer 2.0', desc: 'Commerce analytics engine (Groq)' },
];

const QUICK_PROMPTS = {
  amazon: [
    'Analyze low inventory risks across Amazon FBA warehouses',
    'Calculate buy-box win rate vs. top 5 competitors this week',
    'Reconcile unfulfilled orders and return chargebacks for Sep',
    'Generate unified sales forecast for Q4 holiday peak season'
  ],
  shopify: [
    'Find highest margin product bundles based on customer carts',
    'Audit abandoned checkout recovery flow drop-off rates',
    'Compare Shopify retail sales with wholesale order batches',
    'Sync customer lifetime value (LTV) cohorts into CRM'
  ],
  ebay: [
    'Check listing fee optimizations and promoted listings ROI',
    'Identify underperforming SKUs with zero views in 14 days'
  ],
  etsy: [
    'Analyze handmade product inventory turn rate and raw material supply',
    'Review shipping delay patterns by carrier and destination region'
  ],
  woocommerce: [
    'Audit database query response latency on high-traffic product pages',
    'Check webhook delivery health for order creation triggers'
  ],
  aliexpress: [
    'Track international supplier lead times and customs delays',
    'Audit dropshipping unit cost margins across fulfillment partners'
  ],
  walmart: [
    'Verify Walmart 2-day delivery badge eligibility across all SKUs',
    'Compare pricing parity between Walmart and Amazon listings'
  ]
};


const toSteps = (r) => (Array.isArray(r) ? r.map(String) : typeof r === 'string' ? r.split('\n').filter(Boolean) : []);
const cell = (v) => (v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v));

function computeKpis(dashboard, rows) {
  if (!dashboard?.kpis?.length || !rows?.length) return [];
  return dashboard.kpis.map((k) => {
    const nums = rows.map((r) => Number(r[k.column])).filter((n) => Number.isFinite(n));
    const agg = (k.aggregation || 'value').toLowerCase();
    let v = null;
    if (agg === 'value') v = rows[0]?.[k.column];
    else if (agg === 'count') v = rows.length;
    else if (agg === 'avg') v = nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null;
    else if (agg === 'min') v = nums.length ? Math.min(...nums) : null;
    else if (agg === 'max') v = nums.length ? Math.max(...nums) : null;
    else v = nums.length ? nums.reduce((a, b) => a + b, 0) : null;
    if (v === null || v === undefined) return null;
    if (typeof v === 'string' && !Number.isFinite(Number(v))) {
      return { label: k.label || k.column, value: v };
    }
    v = Number(v);
    return { label: k.label || k.column, value: v.toLocaleString(undefined, { maximumFractionDigits: 2 }) };
  }).filter(Boolean);
}

export default function WorkspaceChat({ initialStore = 'Shopify', onLimitReached }) {
  const { tenantId, user } = useAuth();
  const [conversationId, setConversationId] = useState(null);
  const [selectedStore, setSelectedStore] = useState(initialStore.toLowerCase());
  const [promptText, setPromptText] = useState('');
  const [isReasoningActive, setIsReasoningActive] = useState(true);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState(MODELS[0]);
  const [isMoreDropdownOpen, setIsMoreDropdownOpen] = useState(false);
  
  // Chat message thread state
  const [chatThread, setChatThread] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeReasoningStep, setActiveReasoningStep] = useState(0);

  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);
  const moreRef = useRef(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsModelDropdownOpen(false);
      }
      if (moreRef.current && !moreRef.current.contains(e.target)) {
        setIsMoreDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const handleSend = async (textToSend = promptText) => {
    const query = textToSend.trim();
    if (query.length < 2 || isGenerating || !tenantId) return;
    const time = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const base = { store: selectedStore, model: selectedModel.name };

    setChatThread((prev) => [...prev, { id: Date.now(), role: 'user', ...base, reasoningEnabled: isReasoningActive, text: query, timestamp: time() }]);
    setPromptText('');
    setIsGenerating(true);
    setActiveReasoningStep(0);
    const ticker = setInterval(() => setActiveReasoningStep((n) => Math.min(n + 1, 3)), 1500);

    try {
      let convId = conversationId;
      if (!convId) {
        const conv = await api.createConversation({ tenant_id: tenantId, title: query.slice(0, 80) });
        convId = conv.id;
        setConversationId(convId);
      }
      // The server saves BOTH the question and the answer - do not save messages from the frontend.
      const res = await api.sendMessage(convId, {
        tenant_id: tenantId, content: query, reasoning: isReasoningActive, model_id: selectedModel.id,
      });
      setChatThread((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', ...base, data: res, timestamp: time() }]);
    } catch (err) {
      if (err.status === 402) onLimitReached?.();
      const hint = err.status === 503 && /RAG index is empty/i.test(err.message || '')
        ? ' (RAG index is empty. Rebuild it after syncing the store.)'
        : '';
      setChatThread((prev) => [...prev, { id: Date.now() + 1, role: 'assistant', ...base, error: err.message + hint, timestamp: time() }]);
    } finally {
      clearInterval(ticker);
      setIsGenerating(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const currentQuickPrompts = QUICK_PROMPTS[selectedStore] || QUICK_PROMPTS.amazon;

  return (
    <div className="workspace-chat-container">
      {/* If chat thread is empty, show the pristine Hero Screen matching user screenshot */}
      {chatThread.length === 0 && (
        <div className="workspace-chat-hero">
          {/* Main big centered heading */}
          <h1 className="workspace-chat-hero__title">
            What can I do for you today?
          </h1>

          {/* Central AI prompt input card */}
          <div className="ws-prompt-card">
            <textarea
              ref={textareaRef}
              className="ws-prompt-card__textarea"
              placeholder="Ask about any ecommerce store..."
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
            />

            {/* Bottom toolbar inside input card */}
            <div className="ws-prompt-card__toolbar">
              <div className="ws-prompt-card__tools-left">
                {/* Upload CSV button */}
                <UploadCSVButton
                  variant="pill"
                  size="md"
                  buttonText="Upload CSV"
                  title="Upload CSV dataset for analysis"
                  onUploadSuccess={(_res, file) => {
                    setPromptText((prev) => (prev ? `${prev} (using ${file.name})` : `Analyze the uploaded dataset: ${file.name}`));
                  }}
                />

                {/* Reasoning pill toggle */}
                <button
                  type="button"
                  className={`ws-reasoning-toggle ${isReasoningActive ? 'ws-reasoning-toggle--active' : ''}`}
                  onClick={() => setIsReasoningActive((v) => !v)}
                  title="Toggle deep reasoning engine"
                >
                  <Brain size={14} />
                  <span>Reasoning</span>
                </button>

                {/* Media / catalog icon */}
                <button 
                  className="ws-tool-btn ws-tool-btn--icon"
                  title="Attach product images or barcodes"
                  type="button"
                >
                  <ImageIcon size={16} />
                </button>
              </div>

              <div className="ws-prompt-card__tools-right">
                {/* Model dropdown */}
                <div className="ws-model-selector" ref={dropdownRef}>
                  <button
                    type="button"
                    className="ws-model-selector__trigger"
                    onClick={() => setIsModelDropdownOpen((v) => !v)}
                  >
                    <span>{selectedModel.name}</span>
                    <ChevronDown size={14} className={`chevron ${isModelDropdownOpen ? 'open' : ''}`} />
                  </button>

                  {isModelDropdownOpen && (
                    <div className="ws-model-dropdown">
                      {MODELS.map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          className={`ws-model-option ${m.id === selectedModel.id ? 'active' : ''}`}
                          onClick={() => {
                            setSelectedModel(m);
                            setIsModelDropdownOpen(false);
                          }}
                        >
                          <div className="ws-model-option__name">
                            <span>{m.name}</span>
                            {m.id === selectedModel.id && <Check size={14} />}
                          </div>
                          <span className="ws-model-option__desc">{m.desc}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Submit button (Upward circle arrow) */}
                <button
                  type="button"
                  className={`ws-submit-btn ${promptText.trim() ? 'ws-submit-btn--active' : ''}`}
                  onClick={() => handleSend()}
                  disabled={!promptText.trim() || isGenerating}
                  title="Send query"
                >
                  <ArrowUp size={16} />
                </button>
              </div>
            </div>
          </div>

          {/* Store selector filter chips matching screenshot */}
          <div className="ws-store-chips-row">
            {STORES.map((store) => {
              const isActive = selectedStore === store.id;
              return (
                <button
                  key={store.id}
                  type="button"
                  className={`ws-store-chip ${isActive ? 'ws-store-chip--active' : ''}`}
                  onClick={() => setSelectedStore(store.id)}
                >
                  {store.isNew && <span className="chip-new-badge">NEW</span>}
                  <span>{store.name}</span>
                </button>
              );
            })}

            <div className="ws-more-wrapper" ref={moreRef}>
              <button
                type="button"
                className={`ws-store-chip ws-store-chip--more ${isMoreDropdownOpen ? 'active' : ''}`}
                onClick={() => setIsMoreDropdownOpen((v) => !v)}
              >
                <span>More</span>
                <ChevronDown size={13} />
              </button>

              {isMoreDropdownOpen && (
                <div className="ws-more-dropdown">
                  {MORE_STORES.map((store) => (
                    <button
                      key={store}
                      type="button"
                      className="ws-more-option"
                      onClick={() => {
                        setSelectedStore(store.toLowerCase());
                        setIsMoreDropdownOpen(false);
                      }}
                    >
                      <Store size={14} />
                      <span>{store}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Recommended prompts */}
          <div className="ws-quick-prompts">
            <div className="ws-quick-prompts__label">
              <Sparkles size={13} />
              Recommended prompts for {selectedStore.toUpperCase()}:
            </div>
            <div className="ws-quick-prompts__grid">
              {currentQuickPrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="ws-quick-prompt-btn"
                  onClick={() => handleSend(prompt)}
                >
                  <span>{prompt}</span>
                  <ArrowRight size={14} className="arrow-icon" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {chatThread.length > 0 && (
        <div className="workspace-chat-thread">
          <div className="workspace-chat-thread__header">
            <button
              className="ws-btn ws-btn--secondary ws-btn--sm"
              onClick={() => {
                setChatThread([]);
                setConversationId(null);
                setPromptText('');
              }}
            >
              <Plus size={14} /> New Chat
            </button>
            <div className="active-chat-info">
              <span className="info-tag store-badge">{selectedStore.toUpperCase()}</span>
              <span className="info-tag model-badge">{selectedModel.name}</span>
              {isReasoningActive && (
                <span className="info-tag reasoning-badge">
                  <Brain size={12} /> Deep Reasoning
                </span>
              )}
            </div>
          </div>

          <div className="workspace-messages-list">
            {chatThread.map((msg) => (
              <div key={msg.id} className={`ws-message ws-message--${msg.role}`}>
                {msg.role === 'user' ? (
                  <div className="ws-user-bubble">
                    <div className="ws-user-bubble__header">
                      <div className="user-avatar-sm">U</div>
                      <span className="user-label">{user?.email}</span>
                      <span className="timestamp">{msg.timestamp}</span>
                    </div>
                    <p className="user-text">{msg.text}</p>
                  </div>
                ) : (
                  <div className="ws-assistant-bubble">
                    <div className="ws-assistant-bubble__header">
                      <div className="bot-avatar-sm">
                        <Sparkles size={14} />
                      </div>
                      <span className="bot-name">Merchlayer Commerce AI</span>
                      <span className="timestamp">{msg.timestamp}</span>
                    </div>

                    {msg.error ? (
                      <div className="ws-assistant-summary">
                        <p style={{ color: '#F87171' }}>⚠ {msg.error}</p>
                      </div>
                    ) : (
                      <>
                        {toSteps(msg.data.reasoning).length > 0 && (
                          <details className="ws-reasoning-trace">
                            <summary>
                              <Brain size={14} />
                              <span>Reasoning</span>
                            </summary>
                            <div className="ws-reasoning-steps">
                              {toSteps(msg.data.reasoning).map((step, idx) => (
                                <div key={idx} className="ws-reasoning-step">
                                  <CheckCircle2 size={13} className="step-check" />
                                  <span>{step}</span>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}

                        <div className="ws-assistant-summary">
                          <p style={{ whiteSpace: 'pre-wrap' }}>{msg.data.answer}</p>
                        </div>

                        {computeKpis(msg.data.dashboard, msg.data.rows).length > 0 && (
                          <div className="ws-response-metrics-grid">
                            {computeKpis(msg.data.dashboard, msg.data.rows).map((kpi, idx) => (
                              <div key={idx} className="ws-metric-box">
                                <span className="metric-label">{kpi.label}</span>
                                <span className="metric-val">{kpi.value}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {msg.data.dashboard?.charts?.map((spec, idx) => (
                          <AnalyticsChart
                            key={`${spec.title || 'chart'}-${idx}`}
                            spec={spec}
                            rows={msg.data.rows}
                          />
                        ))}

                        {msg.data.rows?.length > 0 && (
                          <div className="ws-response-table-wrap">
                            <table className="ws-response-table">
                              <thead>
                                <tr>
                                  {Object.keys(msg.data.rows[0]).map((col) => (
                                    <th key={col}>{col}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {msg.data.rows.slice(0, 50).map((row, idx) => (
                                  <tr key={idx}>
                                    {Object.keys(msg.data.rows[0]).map((col) => (
                                      <td key={col}>{cell(row[col])}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {msg.data.sql && (
                          <details className="ws-reasoning-trace">
                            <summary>
                              <Database size={14} />
                              <span>Show SQL</span>
                            </summary>
                            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, padding: 12, margin: 0 }}>
                              {msg.data.sql}
                            </pre>
                          </details>
                        )}
                      </>
                    )}

                    {!msg.error && (
                      <div className="ws-bubble-actions">
                        <button
                          className="ws-action-btn"
                          title="Copy response"
                          onClick={() => navigator.clipboard?.writeText(msg.data.answer || '')}
                        >
                          <Copy size={13} /> Copy Analysis
                        </button>
                        {msg.data.rows?.length > 0 && (
                          <button
                            className="ws-action-btn"
                            title="Export as CSV"
                            onClick={() => downloadCsv(msg.data.rows)}
                          >
                            <Download size={13} /> Export CSV
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {isGenerating && (
              <div className="ws-message ws-message--assistant ws-message--generating">
                <div className="ws-assistant-bubble">
                  <div className="ws-assistant-bubble__header">
                    <div className="bot-avatar-sm spin-slow">
                      <Sparkles size={14} />
                    </div>
                    <span className="bot-name">Merchlayer Commerce AI</span>
                    <span className="timestamp">Reasoning live...</span>
                  </div>
                  <div className="ws-generating-reasoning">
                    <div className="reasoning-pulse-bar">
                      <div className="pulse-bar-fill" />
                    </div>
                    <div className="reasoning-live-text">
                      <Brain size={14} className="spin-fast" />
                      <span>
                        {activeReasoningStep === 0 && 'Connecting to store API endpoint...'}
                        {activeReasoningStep === 1 && 'Ingesting unified order & inventory schema...'}
                        {activeReasoningStep === 2 && 'Executing real-time price & margin calculations...'}
                        {activeReasoningStep >= 3 && 'Synthesizing actionable executive recommendations...'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="workspace-thread-composer">
            <div className="ws-prompt-card ws-prompt-card--compact">
              <textarea
                className="ws-prompt-card__textarea"
                placeholder={`Ask a follow up question about ${selectedStore.toUpperCase()}...`}
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
              />
              <div className="ws-prompt-card__toolbar">
                <div className="ws-prompt-card__tools-left">
                  <UploadCSVButton
                    variant="pill"
                    size="sm"
                    buttonText="Upload CSV"
                    title="Upload CSV dataset for analysis"
                    onUploadSuccess={(_res, file) => {
                      setPromptText((prev) => (prev ? `${prev} (using ${file.name})` : `Analyze the uploaded dataset: ${file.name}`));
                    }}
                  />
                  <button
                    type="button"
                    className={`ws-reasoning-toggle ws-reasoning-toggle--sm ${isReasoningActive ? 'ws-reasoning-toggle--active' : ''}`}
                    onClick={() => setIsReasoningActive((v) => !v)}
                  >
                    <Brain size={13} />
                    <span>Reasoning</span>
                  </button>
                </div>
                <div className="ws-prompt-card__tools-right">
                  <button
                    type="button"
                    className={`ws-submit-btn ${promptText.trim() ? 'ws-submit-btn--active' : ''}`}
                    onClick={() => handleSend()}
                    disabled={!promptText.trim() || isGenerating}
                  >
                    <ArrowUp size={15} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
