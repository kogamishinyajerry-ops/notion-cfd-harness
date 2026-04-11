/**
 * ParaView Web API Client
 * Handles ParaView Web session lifecycle management.
 */

import { API_BASE_URL, API_PREFIX } from './config';

export interface VisualizationLaunchResponse {
  session_id: string;   // PVW-{8-char-hex}
  session_url: string;  // ws://localhost:{port}/ws
  auth_key: string;      // secrets.token_urlsafe(16)
  port: number;
  job_id: string;
}

export interface VisualizationStatusResponse {
  session_id: string;
  job_id: string | null;
  status: string;
  port: number;
  case_dir: string;
  created_at: string;
  last_activity: string;
}

/**
 * Launch a new ParaView Web session for a completed job.
 * @param jobId - The job ID
 * @param caseDir - Absolute path to OpenFOAM case directory
 * @param port - Optional preferred port (auto-allocated if not specified)
 */
export async function launchVisualizationSession(
  jobId: string,
  caseDir: string,
  port?: number
): Promise<VisualizationLaunchResponse> {
  const url = `${API_BASE_URL}${API_PREFIX}/visualization/launch`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, case_dir: caseDir, ...(port && { port }) }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Launch failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Get the current status of a ParaView Web session.
 */
export async function getVisualizationSession(
  sessionId: string
): Promise<VisualizationStatusResponse> {
  const url = `${API_BASE_URL}${API_PREFIX}/visualization/${sessionId}`;
  const response = await fetch(url);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Status check failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Send a heartbeat to keep a ParaView Web session alive.
 * Should be called every 60 seconds while the viewer is active.
 */
export async function sendHeartbeat(sessionId: string): Promise<void> {
  const url = `${API_BASE_URL}${API_PREFIX}/visualization/${sessionId}/activity`;
  await fetch(url, { method: 'POST' });
}
