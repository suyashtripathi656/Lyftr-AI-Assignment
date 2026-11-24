import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { sendMessage, checkHealth, ChatMeta } from './api';
import { ErrorBoundary } from './ErrorBoundary';

/* ───────── types ───────── */
interface UIMessage {
  role: 'user' | 'assistant' | 'error';
  content: string;
  metadata?: ChatMeta;
}

interface Conversation {
  id: string;
  title: string;
  messages: UIMessage[];
}

const SIMULATION_OPTIONS = [
  { label: 'None', value: '' },
  { label: 'key_1=429', value: 'key_1=429' },
  { label: 'key_1=500', value: 'key_1=500' },
  { label: '*=429 (all fail)', value: '*=429' },
];

/* ───────── icons ───────── */
const IconPlus = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);
const IconSend = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);
const IconChat = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);
const IconSettings = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);
const IconSidebar = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <rect x="3" y="3" width="18" height="18" rx="2" /><line x1="9" y1="3" x2="9" y2="21" />
  </svg>
);
const IconTrash = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </svg>
);

/* ───────── Sidebar ───────── */
function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  collapsed,
  onToggle,
}: {
  conversations: Conversation[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  collapsed: boolean;
  onToggle: () => void;
}) {
  if (collapsed) return null;

  return (
    <div className="w-64 h-screen flex flex-col border-r bg-[#f5f0e8]" style={{ borderColor: 'var(--border)' }}>
      {/* Sidebar header */}
      <div className="flex items-center justify-between px-3 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <button onClick={onToggle} className="p-1.5 rounded-lg hover:bg-black/5 text-[var(--text-secondary)] transition">
          <IconSidebar />
        </button>
        <button
          onClick={onNew}
          className="p-1.5 rounded-lg hover:bg-black/5 text-[var(--text-secondary)] transition"
          title="New chat"
        >
          <IconPlus />
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {conversations.length === 0 && (
          <p className="text-xs text-[var(--text-muted)] text-center mt-8">No conversations yet</p>
        )}
        {conversations.map(conv => (
          <div
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
              conv.id === activeId
                ? 'bg-[var(--bg-primary)] text-[var(--text-primary)] font-medium'
                : 'text-[var(--text-secondary)] hover:bg-black/[0.04]'
            }`}
          >
            <IconChat />
            <span className="flex-1 truncate">{conv.title}</span>
            <button
              onClick={e => { e.stopPropagation(); onDelete(conv.id); }}
              className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-black/10 text-[var(--text-muted)] transition"
              title="Delete"
            >
              <IconTrash />
            </button>
          </div>
        ))}
      </div>

      {/* Sidebar footer */}
      <div className="px-3 py-3 border-t text-xs text-[var(--text-muted)]" style={{ borderColor: 'var(--border)' }}>
        Lyftr AI Chatbot
      </div>
    </div>
  );
}

/* ───────── Empty state ───────── */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full select-none">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-200 to-orange-200 flex items-center justify-center mb-6 shadow-sm">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#92400e" strokeWidth="1.5" strokeLinecap="round">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">How can I help you today?</h2>
      <p className="text-sm text-[var(--text-muted)] max-w-sm text-center">
        Start a conversation by typing a message below. I can help with questions, writing, analysis, and more.
      </p>
    </div>
  );
}

/* ───────── Metadata badge ───────── */
function MetadataBadge({ metadata }: { metadata: ChatMeta }) {
  const isCached = metadata.resolution_source === 'LLM_CACHE';
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-2 text-[11px] text-[var(--text-muted)] animate-fade-in">
      <span
        data-testid="meta-source"
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-medium ${
          isCached ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
        }`}
      >
        {isCached ? '⚡' : '🔗'} {metadata.resolution_source}
      </span>
      <span data-testid="meta-model" className="px-1.5 py-0.5 rounded bg-black/[0.04]">{metadata.model}</span>
      <span data-testid="meta-latency" className="px-1.5 py-0.5 rounded bg-black/[0.04]">{metadata.latency_ms}ms</span>
      <span data-testid="meta-input-tokens" className="px-1.5 py-0.5 rounded bg-black/[0.04]">{metadata.input_tokens} in</span>
      <span data-testid="meta-output-tokens" className="px-1.5 py-0.5 rounded bg-black/[0.04]">{metadata.output_tokens} out</span>
      {metadata.key_id && (
        <span className="px-1.5 py-0.5 rounded bg-black/[0.04]">{metadata.key_id} · {metadata.fallback_attempts} retry</span>
      )}
    </div>
  );
}

/* ───────── Main Chat ───────── */
function Chat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>('');
  const [input, setInput] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [backendReady, setBackendReady] = useState<boolean | null>(null);
  const [simulateFailure, setSimulateFailure] = useState('');
  const [showTestTools, setShowTestTools] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const activeConv = conversations.find(c => c.id === activeId);
  const messages = activeConv?.messages ?? [];

  // Create a new conversation
  const createConversation = useCallback(() => {
    const id = crypto.randomUUID();
    const conv: Conversation = { id, title: 'New conversation', messages: [] };
    setConversations(prev => [conv, ...prev]);
    setActiveId(id);
    setInput('');
    return id;
  }, []);

  // Initialize with one conversation
  useEffect(() => {
    if (conversations.length === 0) {
      createConversation();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Health poll
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      while (!cancelled) {
        try {
          await checkHealth();
          if (!cancelled) setBackendReady(true);
          return;
        } catch {
          if (!cancelled) setBackendReady(false);
        }
        await new Promise(r => setTimeout(r, 2000));
      }
    };
    poll();
    return () => { cancelled = true; };
  }, []);

  const updateMessages = useCallback((convId: string, updater: (prev: UIMessage[]) => UIMessage[]) => {
    setConversations(prev =>
      prev.map(c => c.id === convId ? { ...c, messages: updater(c.messages) } : c)
    );
  }, []);

  const updateTitle = useCallback((convId: string, firstMsg: string) => {
    const title = firstMsg.length > 35 ? firstMsg.slice(0, 35) + '…' : firstMsg;
    setConversations(prev =>
      prev.map(c => c.id === convId ? { ...c, title } : c)
    );
  }, []);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    let targetId = activeId;
    if (!targetId) {
      targetId = createConversation();
    }

    const conv = conversations.find(c => c.id === targetId);
    if (conv && conv.messages.length === 0) {
      updateTitle(targetId, trimmed);
    }

    updateMessages(targetId, prev => [...prev, { role: 'user', content: trimmed }]);
    setInput('');
    setLoading(true);

    try {
      const res = await sendMessage(
        targetId,
        trimmed,
        systemPrompt || undefined,
        simulateFailure || undefined,
      );
      updateMessages(targetId, prev => [
        ...prev,
        { role: 'assistant', content: res.reply, metadata: res.metadata },
      ]);
    } catch (err: any) {
      updateMessages(targetId, prev => [
        ...prev,
        { role: 'error', content: err.message || 'An error occurred' },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, activeId, conversations, systemPrompt, simulateFailure, createConversation, updateMessages, updateTitle]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDelete = useCallback((id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
    if (activeId === id) {
      const remaining = conversations.filter(c => c.id !== id);
      if (remaining.length > 0) {
        setActiveId(remaining[0].id);
      } else {
        createConversation();
      }
    }
  }, [activeId, conversations, createConversation]);

  // Loading screen
  if (backendReady === false) {
    return (
      <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg-primary)' }}>
        <div className="text-center">
          <div className="relative w-12 h-12 mx-auto mb-5">
            <div className="absolute inset-0 rounded-full border-2 border-[var(--border)]" />
            <div className="absolute inset-0 rounded-full border-2 border-t-amber-500 animate-spin" />
          </div>
          <p className="text-[var(--text-primary)] text-base font-medium">Connecting to server…</p>
          <p className="text-[var(--text-muted)] text-sm mt-1.5">The backend is starting up. This may take a moment.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={createConversation}
        onDelete={handleDelete}
        collapsed={!sidebarOpen}
        onToggle={() => setSidebarOpen(false)}
      />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col h-screen min-w-0">
        {/* Top bar */}
        <header className="flex items-center justify-between px-4 py-2.5 border-b" style={{ borderColor: 'var(--border)', background: 'var(--bg-primary)' }}>
          <div className="flex items-center gap-2">
            {!sidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} className="p-1.5 rounded-lg hover:bg-black/5 text-[var(--text-secondary)] transition">
                <IconSidebar />
              </button>
            )}
            <span className="text-sm font-medium text-[var(--text-primary)]">
              {activeConv?.title || 'New conversation'}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setShowTestTools(prev => !prev)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition ${
                showTestTools
                  ? 'bg-amber-100 text-amber-800'
                  : 'hover:bg-black/5 text-[var(--text-muted)]'
              }`}
            >
              <IconSettings />
              <span className="hidden sm:inline">Test tools</span>
            </button>
          </div>
        </header>

        {/* Test Tools Panel */}
        {showTestTools && (
          <div className="border-b px-6 py-3 flex flex-wrap items-center gap-4 text-xs" style={{ borderColor: 'var(--border)', background: '#f5f0e8' }}>
            <div className="flex items-center gap-2">
              <label className="font-medium text-[var(--text-secondary)]">Simulate:</label>
              <select
                value={simulateFailure}
                onChange={e => setSimulateFailure(e.target.value)}
                className="border rounded-lg px-2 py-1 bg-white text-[var(--text-primary)] text-xs focus:outline-none focus:ring-1 focus:ring-amber-400"
                style={{ borderColor: 'var(--border)' }}
              >
                {SIMULATION_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2 flex-1 min-w-[200px]">
              <label className="font-medium text-[var(--text-secondary)] whitespace-nowrap">System prompt:</label>
              <input
                data-testid="system-prompt-input"
                type="text"
                value={systemPrompt}
                onChange={e => setSystemPrompt(e.target.value)}
                placeholder="Optional system prompt…"
                className="flex-1 border rounded-lg px-2.5 py-1 bg-white text-xs focus:outline-none focus:ring-1 focus:ring-amber-400"
                style={{ borderColor: 'var(--border)' }}
              />
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-1">
              {messages.map((msg, idx) => {
                if (msg.role === 'error') {
                  return (
                    <div key={idx} className="flex justify-center my-3 animate-fade-in">
                      <div className="bg-red-50 text-red-700 px-4 py-2.5 rounded-xl text-sm border border-red-200 max-w-lg">
                        <span className="font-medium">Error: </span>{msg.content}
                      </div>
                    </div>
                  );
                }

                const isUser = msg.role === 'user';

                return (
                  <div
                    key={idx}
                    className="animate-fade-in"
                    {...(!isUser ? { 'data-testid': 'assistant-message' } : {})}
                  >
                    {/* Full-width row like Claude */}
                    <div className={`py-5 ${isUser ? '' : ''}`}>
                      <div className="flex gap-4">
                        {/* Avatar */}
                        <div className="flex-shrink-0 mt-0.5">
                          {isUser ? (
                            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center">
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
                                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                                <circle cx="12" cy="7" r="4" />
                              </svg>
                            </div>
                          ) : (
                            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-amber-300 to-orange-400 flex items-center justify-center">
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
                                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                              </svg>
                            </div>
                          )}
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
                            {isUser ? 'You' : 'Assistant'}
                          </div>
                          {isUser ? (
                            <div className="text-[0.9375rem] leading-relaxed text-[var(--text-primary)] whitespace-pre-wrap">
                              {msg.content}
                            </div>
                          ) : (
                            <div className="prose-chat">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {msg.content}
                              </ReactMarkdown>
                            </div>
                          )}
                          {!isUser && msg.metadata && <MetadataBadge metadata={msg.metadata} />}
                        </div>
                      </div>
                    </div>
                    {/* Divider */}
                    {idx < messages.length - 1 && (
                      <div className="border-b" style={{ borderColor: 'var(--border)', opacity: 0.5 }} />
                    )}
                  </div>
                );
              })}

              {/* Typing indicator */}
              {loading && (
                <div className="py-5 animate-fade-in">
                  <div className="flex gap-4">
                    <div className="flex-shrink-0 mt-0.5">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-amber-300 to-orange-400 flex items-center justify-center">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
                          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                        </svg>
                      </div>
                    </div>
                    <div className="flex-1">
                      <div className="text-xs font-semibold text-[var(--text-secondary)] mb-2">Assistant</div>
                      <div className="flex items-center gap-1.5">
                        <div className="typing-dot" />
                        <div className="typing-dot" />
                        <div className="typing-dot" />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area — Claude-style bottom bar */}
        <div className="px-4 pb-4 pt-2" style={{ background: 'var(--bg-primary)' }}>
          <div className="max-w-3xl mx-auto">
            <div
              className="flex items-end gap-2 rounded-2xl border px-4 py-3 shadow-sm transition-shadow focus-within:shadow-md"
              style={{ background: 'var(--bg-white)', borderColor: 'var(--border)' }}
            >
              <textarea
                ref={inputRef}
                data-testid="chat-input"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message…"
                rows={1}
                className="chat-input flex-1 resize-none bg-transparent text-[0.9375rem] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none leading-relaxed"
                disabled={loading}
              />
              <button
                data-testid="send-button"
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="flex-shrink-0 p-2 rounded-xl bg-[var(--text-primary)] text-white hover:bg-black disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                <IconSend />
              </button>
            </div>
            <p className="text-center text-[10px] text-[var(--text-muted)] mt-2">
              LLM Chatbot may produce inaccurate information. Verify important details.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Chat />
    </ErrorBoundary>
  );
}
