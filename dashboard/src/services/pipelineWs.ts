/**
 * WebSocket service for real-time pipeline updates
 *
 * Extends the existing wsService pattern with:
 * - Auto-reconnect with exponential backoff (1s, 2s, 4s, 8s, 16s), max 5 retries
 * - After 5 failed reconnects, falls back to HTTP polling every 5s
 * - Handles pipeline event types: pipeline_started, step_started, step_completed,
 *   step_failed, pipeline_completed, pipeline_failed, pipeline_cancelled,
 *   pipeline_paused, pipeline_resumed
 * - Sequence number tracking for reconnect replay
 */

import { API_BASE_URL, API_PREFIX } from './config';
import type { PipelineEvent } from './types';

export type PipelineMessageHandler = (event: PipelineEvent) => void;

class PipelineWebSocketService {
  private connections: Map<string, WebSocket> = new Map();
  private handlers: Map<string, Set<PipelineMessageHandler>> = new Map();
  private reconnectAttempts: Map<string, number> = new Map();
  private reconnectTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();
  private pollingIntervals: Map<string, ReturnType<typeof setInterval>> = new Map();
  private lastSequence: Map<string, number> = new Map();
  private pipelineIds: Map<string, string> = new Map(); // wsUrl -> pipelineId

  private readonly MAX_RECONNECT_RETRIES = 5;
  private readonly POLLING_INTERVAL_MS = 5000;
  private readonly RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000]; // exponential backoff

  /**
   * Connect to a pipeline's WebSocket channel at ws://localhost:8000/ws/pipelines/{pipelineId}
   */
  connect(pipelineId: string): void {
    if (this.connections.has(pipelineId)) {
      return; // Already connected
    }

    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}${API_PREFIX}/ws/pipelines/${pipelineId}`;
    const ws = new WebSocket(wsUrl);
    this.pipelineIds.set(wsUrl, pipelineId);

    ws.onopen = () => {
      console.log(`[pipelineWs] Connected: ${pipelineId}`);
      this.reconnectAttempts.set(pipelineId, 0);

      // Replay events from last sequence on reconnect
      const lastSeq = this.lastSequence.get(pipelineId) ?? 0;
      if (lastSeq > 0) {
        ws.send(JSON.stringify({ type: 'replay', last_sequence: lastSeq }));
      }
    };

    ws.onmessage = (event) => {
      try {
        const message: PipelineEvent = JSON.parse(event.data);
        // Track sequence
        if (message.sequence !== undefined) {
          this.lastSequence.set(pipelineId, message.sequence);
        }
        this.notifyHandlers(pipelineId, message);
      } catch (e) {
        console.error('[pipelineWs] Failed to parse message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error(`[pipelineWs] Error for pipeline ${pipelineId}:`, error);
    };

    ws.onclose = () => {
      console.log(`[pipelineWs] Disconnected: ${pipelineId}`);
      this.connections.delete(pipelineId);
      this.pipelineIds.delete(wsUrl);
      this.handleDisconnect(pipelineId);
    };

    this.connections.set(pipelineId, ws);
  }

  /**
   * Disconnect from a pipeline's WebSocket channel
   */
  disconnect(pipelineId: string): void {
    const ws = this.connections.get(pipelineId);
    if (ws) {
      ws.close();
      this.connections.delete(pipelineId);
    }

    // Clear any pending reconnect/polling
    const timer = this.reconnectTimers.get(pipelineId);
    if (timer) {
      clearTimeout(timer);
      this.reconnectTimers.delete(pipelineId);
    }
    const interval = this.pollingIntervals.get(pipelineId);
    if (interval) {
      clearInterval(interval);
      this.pollingIntervals.delete(pipelineId);
    }
    this.handlers.delete(pipelineId);
  }

  /**
   * Subscribe to pipeline events
   */
  subscribe(pipelineId: string, handler: PipelineMessageHandler): () => void {
    if (!this.handlers.has(pipelineId)) {
      this.handlers.set(pipelineId, new Set());
    }
    this.handlers.get(pipelineId)!.add(handler);

    return () => {
      this.handlers.get(pipelineId)?.delete(handler);
    };
  }

  /**
   * Check if connected
   */
  isConnected(pipelineId: string): boolean {
    const ws = this.connections.get(pipelineId);
    return ws !== undefined && ws.readyState === WebSocket.OPEN;
  }

  /**
   * Get reconnect state for UI indicator
   */
  getReconnectState(pipelineId: string): 'connected' | 'reconnecting' | 'polling' {
    if (this.isConnected(pipelineId)) return 'connected';
    const attempts = this.reconnectAttempts.get(pipelineId) ?? 0;
    if (attempts >= this.MAX_RECONNECT_RETRIES) return 'polling';
    return 'reconnecting';
  }

  private handleDisconnect(pipelineId: string): void {
    const attempts = (this.reconnectAttempts.get(pipelineId) ?? 0) + 1;
    this.reconnectAttempts.set(pipelineId, attempts);

    if (attempts <= this.MAX_RECONNECT_RETRIES) {
      // Exponential backoff
      const delay = this.RECONNECT_DELAYS[Math.min(attempts - 1, this.RECONNECT_DELAYS.length - 1)];
      console.log(`[pipelineWs] Reconnecting ${pipelineId} in ${delay}ms (attempt ${attempts}/${this.MAX_RECONNECT_RETRIES})`);
      const timer = setTimeout(() => {
        this.connect(pipelineId);
      }, delay);
      this.reconnectTimers.set(pipelineId, timer);
    } else {
      // Fall back to polling
      console.log(`[pipelineWs] Max retries reached for ${pipelineId}, falling back to polling`);
      this.startPolling(pipelineId);
    }
  }

  private startPolling(pipelineId: string): void {
    // Poll GET /pipelines/{id} every 5s and emit synthetic events
    const interval = setInterval(async () => {
      try {
        const { apiClient } = await import('./api');
        const pipeline = await apiClient.getPipeline(pipelineId);
        // Emit a synthetic event for the current pipeline status
        const event: PipelineEvent = {
          sequence: Date.now(), // synthetic sequence
          type: 'pipeline_started' as const, // placeholder
          pipeline_id: pipelineId,
          timestamp: new Date().toISOString(),
          data: { pipeline },
        };
        this.notifyHandlers(pipelineId, event);
      } catch (e) {
        console.error(`[pipelineWs] Polling error for ${pipelineId}:`, e);
      }
    }, this.POLLING_INTERVAL_MS);
    this.pollingIntervals.set(pipelineId, interval);
  }

  private notifyHandlers(pipelineId: string, message: PipelineEvent): void {
    const handlers = this.handlers.get(pipelineId);
    if (handlers) {
      handlers.forEach((handler) => handler(message));
    }
  }
}

export const pipelineWs = new PipelineWebSocketService();
export default pipelineWs;
