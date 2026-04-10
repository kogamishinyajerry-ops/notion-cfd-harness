/**
 * WebSocket service for real-time job updates
 */

import { API_BASE_URL } from './config';
import type { Job } from './types';

export type WebSocketMessageType = 'status' | 'progress' | 'completion' | 'error' | 'residual';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  job?: Job;
  progress?: number;
  status?: string;
  result?: Record<string, unknown>;
  error?: string;
}

/**
 * ResidualMessage - Real-time residual data from CFD solver
 * Received via WebSocket when a job is running
 */
export interface ResidualMessage {
  type: 'residual';
  job_id: string;
  iteration: number;
  time_value: number;
  residuals: {
    Ux?: number;
    Uy?: number;
    Uz?: number;
    p?: number;
    [key: string]: number | undefined;
  };
  status: string;
}

type MessageHandler = (message: WebSocketMessage) => void;

class WebSocketService {
  private connections: Map<string, WebSocket> = new Map();
  private handlers: Map<string, Set<MessageHandler>> = new Map();

  /**
   * Connect to a job's WebSocket channel
   */
  connect(jobId: string, token?: string): void {
    if (this.connections.has(jobId)) {
      return; // Already connected
    }

    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}/ws/jobs/${jobId}${token ? `?token=${token}` : ''}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`WebSocket connected: ${jobId}`);
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.notifyHandlers(jobId, message);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error for job ${jobId}:`, error);
    };

    ws.onclose = () => {
      console.log(`WebSocket disconnected: ${jobId}`);
      this.connections.delete(jobId);
      this.handlers.delete(jobId);
    };

    this.connections.set(jobId, ws);
  }

  /**
   * Disconnect from a job's WebSocket channel
   */
  disconnect(jobId: string): void {
    const ws = this.connections.get(jobId);
    if (ws) {
      ws.close();
      this.connections.delete(jobId);
      this.handlers.delete(jobId);
    }
  }

  /**
   * Disconnect from all WebSocket channels
   */
  disconnectAll(): void {
    for (const [jobId] of this.connections) {
      this.disconnect(jobId);
    }
  }

  /**
   * Subscribe to messages for a specific job
   */
  subscribe(jobId: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(jobId)) {
      this.handlers.set(jobId, new Set());
    }
    this.handlers.get(jobId)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.handlers.get(jobId)?.delete(handler);
    };
  }

  /**
   * Send a ping to keep connection alive
   */
  ping(jobId: string): void {
    const ws = this.connections.get(jobId);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('ping');
    }
  }

  private notifyHandlers(jobId: string, message: WebSocketMessage): void {
    const handlers = this.handlers.get(jobId);
    if (handlers) {
      handlers.forEach((handler) => handler(message));
    }
  }

  /**
   * Check if connected to a job
   */
  isConnected(jobId: string): boolean {
    const ws = this.connections.get(jobId);
    return ws !== undefined && ws.readyState === WebSocket.OPEN;
  }
}

export const wsService = new WebSocketService();
export default wsService;
