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
