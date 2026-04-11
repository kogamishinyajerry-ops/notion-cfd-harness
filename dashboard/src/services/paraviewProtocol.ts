/**
 * ParaView Web protocol message builders and parsers.
 * These functions create JSON-RPC style messages for ParaView Web server communication.
 */

/**
 * Create a protocol message to open an OpenFOAM case reader.
 * Called after WebSocket authentication.
 */
export function createOpenFOAMReaderMessage(caseDir: string): object {
  return {
    id: "pv-1",
    method: "OpenFOAMReader.Open",
    params: { fileName: caseDir }
  };
}

/**
 * Create a protocol message to request available fields from the OpenFOAM reader.
 */
export function createGetFieldsMessage(): object {
  return {
    id: "pv-fields",
    method: "OpenFOAMReader.GetPropertyList",
    params: {}
  };
}

/**
 * Create a protocol message to set the active field for display.
 */
export function createFieldDisplayMessage(fieldName: string): object {
  return {
    id: "pv-field-display",
    method: "OpenFOAMReader.SetProperty",
    params: { property: "Fields", value: fieldName }
  };
}

/**
 * Create a protocol message to request available time steps from the OpenFOAM reader.
 */
export function createGetTimeStepsMessage(): object {
  return {
    id: "pv-timesteps",
    method: "OpenFOAMReader.GetTimeSteps",
    params: {}
  };
}

/**
 * Create a protocol message to set the active time step.
 */
export function createTimeStepMessage(timeStepIndex: number): object {
  return {
    id: "pv-timestep",
    method: "OpenFOAMReader.SetTimeStep",
    params: { timeStep: timeStepIndex }
  };
}

/**
 * Create a protocol message to trigger a render update.
 */
export function createRenderMessage(): object {
  return {
    id: "pv-render",
    method: "Render",
    params: {}
  };
}

/**
 * Parse available fields from a ParaView Web protocol response.
 * Response format: { id, result: { fields: [...] } } or { id, result: [...] }
 */
export function parseAvailableFields(response: { id?: string; result?: unknown }): string[] {
  if (response && typeof response === 'object') {
    const r = response as Record<string, unknown>;
    if (r.result && typeof r.result === 'object') {
      const result = r.result as Record<string, unknown>;
      if (Array.isArray(result.fields)) {
        return result.fields as string[];
      }
      if (Array.isArray(result)) {
        return result.filter((f) => typeof f === 'string');
      }
    }
  }
  return [];
}

/**
 * Parse available time steps from a ParaView Web protocol response.
 * Response format: { id, result: { timeSteps: [...] } } or { id, result: [...] }
 */
export function parseAvailableTimeSteps(response: { id?: string; result?: unknown }): number[] {
  if (response && typeof response === 'object') {
    const r = response as Record<string, unknown>;
    if (r.result && typeof r.result === 'object') {
      const result = r.result as Record<string, unknown>;
      if (Array.isArray(result.timeSteps)) {
        return (result.timeSteps as (string | number)[]).map(Number);
      }
      if (Array.isArray(result)) {
        return result.map((v) => Number(v)).filter((n) => !isNaN(n));
      }
    }
  }
  return [];
}

/**
 * Create a protocol message to reset the camera to default orientation.
 * Maps to PV-04.2: Camera reset button.
 */
export function createCameraResetMessage(): object {
  return {
    id: "pv-camera-reset",
    method: "view.resetCamera",
    params: {}
  };
}

/**
 * Create a protocol message to create or update an axis-aligned slice filter.
 * Maps to PV-04.3: Slice filter with adjustable origin.
 *
 * @param axis - "X" | "Y" | "Z" — the plane normal direction
 * @param origin - [number, number, number] — point the plane passes through
 */
export function createSliceMessage(axis: 'X' | 'Y' | 'Z', origin: [number, number, number]): object {
  const normalMap: Record<string, [number, number, number]> = {
    X: [1, 0, 0],
    Y: [0, 1, 0],
    Z: [0, 0, 1]
  };
  return {
    id: "pv-slice",
    method: "Slice.Create",
    params: {
      input: "OpenFOAMReader",
      normal: normalMap[axis] ?? [0, 0, 1],
      origin: origin
    }
  };
}

/**
 * Create a protocol message to change the color lookup table preset.
 * Maps to PV-04.4: Color presets — Viridis, BlueRed, Grayscale.
 *
 * @param preset - "Viridis" | "BlueRed" | "Grayscale"
 */
export function createColorPresetMessage(preset: 'Viridis' | 'BlueRed' | 'Grayscale'): object {
  return {
    id: "pv-lut",
    method: "UpdateLUT",
    params: {
      property: "lookupTable",
      preset: preset
    }
  };
}

/**
 * Create a protocol message to set the scalar color range.
 * Maps to PV-04.6: Scalar range — Auto or Manual.
 *
 * @param mode - "auto" | "manual"
 * @param min - minimum value (used in manual mode)
 * @param max - maximum value (used in manual mode)
 */
export function createScalarRangeMessage(mode: 'auto' | 'manual', min?: number, max?: number): object {
  if (mode === 'auto') {
    return {
      id: "pv-range",
      method: "UpdateScalarRange",
      params: { mode: "auto" }
    };
  }
  return {
    id: "pv-range",
    method: "UpdateScalarRange",
    params: { mode: "manual", min: min ?? 0, max: max ?? 1 }
  };
}

/**
 * Create a protocol message to show or hide the scalar color bar (legend).
 * Maps to PV-04.5: Scalar bar with min/max values and labeled ticks.
 *
 * @param visible - true to show the scalar bar, false to hide
 */
export function createScalarBarMessage(visible: boolean): object {
  return {
    id: "pv-scalarbar",
    method: "CreateScalarBar",
    params: {
      visible: visible,
      component: "ScalarBarWidget"
    }
  };
}

/**
 * Create a protocol message to toggle volume rendering on/off.
 * Maps to VOL-01.1: Volume rendering toggle RPC.
 *
 * @param fieldName - Name of the scalar field to render as volume
 * @param enabled - true to enable volume, false to restore surface
 */
export function createVolumeRenderingToggle(fieldName: string, enabled: boolean): object {
  return {
    id: "pv-volume-toggle",
    method: "visualization.volume.rendering.toggle",
    params: { fieldName, enabled }
  };
}

/**
 * Create a protocol message to query volume rendering status.
 * Maps to VOL-01.2/01.3: GPU availability and cell count status RPC.
 */
export function createVolumeRenderingStatus(): object {
  return {
    id: "pv-volume-status",
    method: "visualization.volume.rendering.status",
    params: {}
  };
}

/**
 * Volume rendering status response parser.
 * Maps to VOL-01.2/01.3: GPU warning and cell count warning.
 */
export interface VolumeRenderingStatus {
  enabled: boolean;
  field_name: string | null;
  gpu_available: boolean;
  gpu_vendor: string;
  cell_count: number;
  cell_count_warning: boolean;
}

export function parseVolumeRenderingStatus(response: { id?: string; result?: unknown }): VolumeRenderingStatus | null {
  if (response && typeof response === 'object') {
    const r = response as Record<string, unknown>;
    if (r.result && typeof r.result === 'object') {
      const result = r.result as Record<string, unknown>;
      return {
        enabled: Boolean(result.enabled),
        field_name: typeof result.field_name === 'string' ? result.field_name : null,
        gpu_available: Boolean(result.gpu_available),
        gpu_vendor: typeof result.gpu_vendor === 'string' ? result.gpu_vendor : 'unknown',
        cell_count: typeof result.cell_count === 'number' ? result.cell_count : 0,
        cell_count_warning: Boolean(result.cell_count_warning),
      };
    }
  }
  return null;
}
