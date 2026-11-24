import { useState, useRef, useEffect, useCallback } from 'react';
import { sendMessage, checkHealth, ChatMeta } from './api';
import { ErrorBoundary } from './ErrorBoundary';

interface UIMessage {
  role: 'user' | 'assistant' | 'error';
  content: string;
  metadata?: ChatMeta;
}

const SIMULATION_OPTIONS = [
  { label: 'None', value: '' },
  { label: 'key_1=429', value: 'key_1=429' },
  { label: 'key_1=500', value: 'key_1=500' },
  { label: '*=429 (all fail)', value: '*=429' },
];

function Chat() {
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [backendReady, setBackendReady] = useState<boolean | null>(null);
  const [simulateFailure, setSimulateFailure] = useState('');
  const [showTestTools, setShowTestTools] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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

  const handleNewChat = useCallback(() => {
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setInput('');
  }, []);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setMessages(prev => [...prev, { role: 'user', content: trimmed }]);
    setInput('');
    setLoading(true);

    try {
      const res = await sendMessage(
        sessionId,
        trimmed,
        systemPrompt || undefined,
        simulateFailure || undefined,
      );
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: res.reply, metadata: res.metadata },
      ]);
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        { role: 'error', content: err.message || 'An error occurred' },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, sessionId, systemPrompt, simulateFailure]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (backendReady === false) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-600 text-lg">Waking up server...</p>
          <p className="text-gray-400 text-sm mt-1">The backend is starting, please wait.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto bg-white shadow-xl">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b bg-white sticky top-0 z-10">
        <h1 className="text-lg font-bold text-gray-800">💬 LLM Chatbot</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowTestTools(prev => !prev)}
            className="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-600"
          >
            {showTestTools ? 'Hide' : 'Test'} tools
          </button>
          <button
            onClick={handleNewChat}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            New chat
          </button>
        </div>
      </header>

      {/* Test Tools Panel */}
      {showTestTools && (
        <div className="border-b bg-gray-50 px-4 py-3 space-y-2">
          <div className="flex items-center gap-3">
            <label className="text-xs font-medium text-gray-500 whitespace-nowrap">Simulate failure:</label>
            <select
              value={simulateFailure}
              onChange={e => setSimulateFailure(e.target.value)}
              className="text-sm border rounded px-2 py-1 bg-white"
            >
              {SIMULATION_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs font-medium text-gray-500 whitespace-nowrap">System prompt:</label>
            <input
              data-testid="system-prompt-input"
              type="text"
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
              placeholder="Optional system prompt..."
              className="flex-1 text-sm border rounded px-2 py-1"
            />
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-4xl mb-2">🤖</p>
            <p>Start a conversation!</p>
          </div>
        )}

        {messages.map((msg, idx) => {
          if (msg.role === 'error') {
            return (
              <div key={idx} className="flex justify-center">
                <div className="bg-red-50 text-red-700 px-4 py-2 rounded-lg text-sm max-w-lg border border-red-200">
                  ⚠️ {msg.content}
                </div>
              </div>
            );
          }

          const isUser = msg.role === 'user';
          return (
            <div
              key={idx}
              className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
              {...(!isUser ? { 'data-testid': 'assistant-message' } : {})}
            >
              <div className={`max-w-[80%] ${isUser ? '' : ''}`}>
                <div
                  className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                    isUser
                      ? 'bg-blue-600 text-white rounded-br-md'
                      : 'bg-gray-100 text-gray-800 rounded-bl-md'
                  }`}
                >
                  {msg.content}
                </div>

                {/* Metadata for assistant messages */}
                {!isUser && msg.metadata && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-gray-400 px-1">
                    <span
                      data-testid="meta-source"
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        msg.metadata.resolution_source === 'LLM_CACHE'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {msg.metadata.resolution_source}
                    </span>
                    <span data-testid="meta-model" className="text-gray-500">{msg.metadata.model}</span>
                    <span data-testid="meta-latency">{msg.metadata.latency_ms} ms</span>
                    <span data-testid="meta-input-tokens">{msg.metadata.input_tokens}</span>
                    <span className="text-gray-300">in</span>
                    <span data-testid="meta-output-tokens">{msg.metadata.output_tokens}</span>
                    <span className="text-gray-300">out</span>
                    {msg.metadata.key_id && (
                      <span className="text-gray-400">{msg.metadata.key_id} · {msg.metadata.fallback_attempts} fallback</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Typing indicator */}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-bl-md">
              <div className="flex space-x-1.5">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t bg-white px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            data-testid="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            data-testid="send-button"
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition text-sm font-medium"
          >
            Send
          </button>
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
