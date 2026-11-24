/**
 * API client — single module for all backend calls.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ChatMeta {
  resolution_source: 'LIVE_INFERENCE' | 'LLM_CACHE';
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id: string | null;
  fallback_attempts: number;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  metadata: ChatMeta;
}

export interface HealthResponse {
  status: string;
  keys_configured: number;
  cache_enabled: boolean;
}

export interface MessageItem {
  role: string;
  content: string;
  metadata?: ChatMeta;
}

export interface MessagesResponse {
  session_id: string;
  messages: MessageItem[];
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function sendMessage(
  sessionId: string,
  message: string,
  systemPrompt?: string,
  simulateFailure?: string,
): Promise<ChatResponse> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (simulateFailure) {
    headers['X-Simulate-Failure'] = simulateFailure;
  }

  const body: Record<string, string> = { session_id: sessionId, message };
  if (systemPrompt) body.system_prompt = systemPrompt;

  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }

  return res.json();
}

export async function getMessages(sessionId: string): Promise<MessagesResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail);
  }
  return res.json();
}
