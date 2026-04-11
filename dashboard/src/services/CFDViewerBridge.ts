/**
 * CFDViewerBridge — Framework-agnostic postMessage bridge for React-Vue iframe communication.
 * Used by TrameViewer (React) to send commands to and receive events from the Vue.js trame viewer
 * embedded in an iframe. No React dependencies; works in any framework context.
 */

// =============================================================================
// Outbound message types (React → Vue)
// =============================================================================

export type BridgeMessage =
  | { type: 'field'; field: string }
  | { type: 'slice'; axis: 'X' | 'Y' | 'Z'; origin: [number, number, number] }
  | { type: 'slice_off' }
  | { type: 'color_preset'; preset: 'Viridis' | 'BlueRed' | 'Grayscale' }
  | { type: 'scalar_range'; mode: 'auto' | 'manual'; min?: number; max?: number }
  | { type: 'volume_toggle'; enabled: boolean }
  | { type: 'timestep'; index: number }
  | { type: 'clip_create'; insideOut: boolean; scalarValue: number }
  | { type: 'contour_create'; isovalues: number[] }
  | { type: 'streamtracer_create'; direction: 'FORWARD' | 'BACKWARD'; maxSteps: number }
  | { type: 'filter_delete'; filterId: string }
  | { type: 'filter_list' }
  | { type: 'screenshot'; width: number; height: number }
  | { type: 'volume_status' };

// =============================================================================
// Inbound message types (Vue → React)
// =============================================================================

export type BridgeInboundMessage =
  | { type: 'ready' }
  | { type: 'fields'; fields: string[] }
  | {
      type: 'volume_status';
      enabled: boolean;
      field_name: string | null;
      gpu_available: boolean;
      gpu_vendor: string;
      cell_count: number;
      cell_count_warning: boolean;
    }
  | { type: 'filter_response'; success: boolean; filterId?: string; params?: Record<string, unknown> }
  | {
      type: 'filter_list';
      filters: Array<{ id: string; type: string; parameters: Record<string, unknown> }>;
    }
  | { type: 'screenshot_data'; image: string }
  | { type: 'camera'; position: [number, number, number]; focalPoint: [number, number, number] };

// =============================================================================
// CFDViewerBridge class
// =============================================================================

export default class CFDViewerBridge {
  private iframe: HTMLIFrameElement;
  private handler: (msg: BridgeInboundMessage) => void;
  private boundListener: (event: MessageEvent) => void;

  /**
   * @param iframe - The iframe element hosting the Vue trame viewer
   */
  constructor(iframe: HTMLIFrameElement) {
    this.iframe = iframe;
    this.handler = () => {};
    this.boundListener = this.handleMessage.bind(this);
    window.addEventListener('message', this.boundListener);
  }

  /**
   * Send a message to the Vue iframe via postMessage.
   */
  send(msg: BridgeMessage): void {
    this.iframe.contentWindow?.postMessage(msg, '*');
  }

  /**
   * Register a handler for inbound messages from the Vue iframe.
   * @returns Unsubscribe function — call it to remove the listener.
   */
  onMessage(handler: (msg: BridgeInboundMessage) => void): () => void {
    this.handler = handler;
    return () => {
      this.handler = () => {};
    };
  }

  /**
   * Clean up — removes the window message listener.
   * Call this when the viewer is unmounted.
   */
  destroy(): void {
    window.removeEventListener('message', this.boundListener);
  }

  private handleMessage(event: MessageEvent): void {
    // Accept messages from local iframe (origin is 'null' for file:// or data://,
    // or any origin when target is '*' as used in send())
    if (event.origin === 'null' || event.origin === '') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data = event.data as any;
      if (data && typeof data === 'object' && 'type' in data) {
        this.handler(data as BridgeInboundMessage);
      }
    }
  }
}
