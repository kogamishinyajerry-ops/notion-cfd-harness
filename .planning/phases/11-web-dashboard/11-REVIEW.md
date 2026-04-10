---
phase: 11-web-dashboard
reviewed: 2026-04-10T00:00:00Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - dashboard/src/App.tsx
  - dashboard/src/main.tsx
  - dashboard/src/router.tsx
  - dashboard/src/theme.css
  - dashboard/src/index.css
  - dashboard/src/layouts/MainLayout.tsx
  - dashboard/src/layouts/MainLayout.css
  - dashboard/src/pages/DashboardPage.tsx
  - dashboard/src/pages/CasesPage.tsx
  - dashboard/src/pages/JobsPage.tsx
  - dashboard/src/pages/ReportsPage.tsx
  - dashboard/src/pages/SettingsPage.tsx
  - dashboard/src/pages/JobDetailPage.tsx
  - dashboard/src/pages/JobDetailPage.css
  - dashboard/src/pages/ReportViewerPage.tsx
  - dashboard/src/pages/ReportViewerPage.css
  - dashboard/src/components/CaseList.tsx
  - dashboard/src/components/CaseWizard.tsx
  - dashboard/src/components/GeometryForm.tsx
  - dashboard/src/components/GeometryPreview.tsx
  - dashboard/src/components/JobQueueView.tsx
  - dashboard/src/components/JobQueueView.css
  - dashboard/src/services/api.ts
  - dashboard/src/services/types.ts
  - dashboard/src/services/caseTypes.ts
  - dashboard/src/services/caseStorage.ts
  - dashboard/src/services/config.ts
  - dashboard/src/services/websocket.ts
  - dashboard/vite.config.ts
  - dashboard/package.json
findings:
  critical: 3
  warning: 4
  info: 5
  total: 12
status: issues_found
---
# Phase 11: Web Dashboard Code Review Report

**Reviewed:** 2026-04-10
**Depth:** standard
**Files Reviewed:** 30
**Status:** issues_found

## Summary

The React dashboard is well-structured with proper TypeScript types and React Router setup. However, several security and robustness issues were identified, particularly around WebSocket reconnection, token handling, and XSS prevention in SVG rendering.

## Critical Issues

### CR-01: Hardcoded API Base URL

**File:** `dashboard/src/services/config.ts:6`
**Issue:** API_BASE_URL is hardcoded to `http://localhost:8000`. This will fail in production and does not support environment-based configuration.
**Fix:**
```typescript
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
```

### CR-02: WebSocket Token Passed in URL Query Parameter

**File:** `dashboard/src/services/websocket.ts:33`
**Issue:** Authentication token is passed as a query parameter (`?token=${token}`) instead of in headers. Tokens in URLs can be leaked via server logs, browser history, and referrer headers.
**Fix:** Pass token via WebSocket subprotocol or use a separate authentication handshake. If the backend requires query param, ensure tokens are short-lived and implement proper server-side token invalidation.

### CR-03: XSS via SVG text Content

**File:** `dashboard/src/components/GeometryPreview.tsx:177`
**Issue:** User-controlled data (bodyXMin, bodyYMin, etc.) is rendered directly into SVG `<text>` elements without sanitization. Values like `</text><script>alert(1)</script><text>` could execute XSS.
**Fix:**
```typescript
// Sanitize text content before rendering
const sanitizeText = (text: string): string => {
  return text.replace(/[<>]/g, '').slice(0, 50);
};

<span className="body-label" textAnchor="middle">
  {sanitizeText(bodyLabel)}
</span>
```

## Warnings

### WR-01: WebSocket Lacks Reconnection Logic

**File:** `dashboard/src/services/websocket.ts`
**Issue:** When a WebSocket connection drops (e.g., network interruption), there is no automatic reconnection. Active jobs will stop receiving updates until page refresh.
**Fix:** Implement exponential backoff reconnection:
```typescript
connect(jobId: string, token?: string): void {
  // ... existing connection code
  ws.onclose = () => {
    this.connections.delete(jobId);
    // Reconnect with backoff
    let delay = 1000;
    const reconnect = () => {
      if (!this.connections.has(jobId)) {
        this.connect(jobId, token);
        delay = Math.min(delay * 2, 30000);
        setTimeout(reconnect, delay);
      }
    };
    setTimeout(reconnect, delay);
  };
}
```

### WR-02: Token Not Persisted Across Page Refreshes

**File:** `dashboard/src/services/api.ts:21`
**Issue:** The authentication token is stored only in memory (`this.token`). Users must re-login after every page refresh.
**Fix:** Store token in sessionStorage (not localStorage for security) with proper CSRF protection:
```typescript
private getToken(): string | null {
  return sessionStorage.getItem('auth_token');
}

private setToken(token: string | null): void {
  if (token) {
    sessionStorage.setItem('auth_token', token);
  } else {
    sessionStorage.removeItem('auth_token');
  }
}
```

### WR-03: Unchecked JSON Import in caseStorage.ts

**File:** `dashboard/src/services/caseStorage.ts:105`
**Issue:** `importCase` parses user-uploaded JSON and only does shallow type assertion. Malformed or malicious JSON could corrupt application state.
**Fix:** Validate the imported data structure before accepting:
```typescript
const data = JSON.parse(e.target?.result as string);
if (!isValidCaseDefinition(data)) {
  throw new Error('Invalid case file structure');
}
```

### WR-04: CasesPage Uses Synchronous URL-Based Mode Detection

**File:** `dashboard/src/pages/CasesPage.tsx:19-30`
**Issue:** The component uses `if (mode === 'new')` synchronously in the render body. This causes React warnings about updating state during render and can lead to inconsistent behavior.
**Fix:** Use useEffect for URL parameter side effects:
```typescript
useEffect(() => {
  if (mode === 'new') {
    setShowWizard(true);
  }
}, [mode]);
```

## Info

### IN-01: Redundant App.tsx Navigation

**File:** `dashboard/src/App.tsx:6-12`
**Issue:** App.tsx has hardcoded `<a href>` links instead of React Router `<Link>` components. This causes full page reloads defeating SPA navigation.
**Fix:** Use `<NavLink>` from react-router-dom:
```tsx
<nav>
  <NavLink to="/">Dashboard</NavLink>
  <NavLink to="/cases">Cases</NavLink>
  {/* ... */}
</nav>
```
Note: MainLayout.tsx already does this correctly. App.tsx appears unused.

### IN-02: No Request Timeout on API Client

**File:** `dashboard/src/services/api.ts:31-56`
**Issue:** No timeout configured for fetch requests. Requests can hang indefinitely.
**Fix:**
```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 30000);

try {
  const response = await fetch(url, {
    ...options,
    headers,
    signal: controller.signal,
  });
} finally {
  clearTimeout(timeoutId);
}
```

### IN-03: Predictable Case ID Generation

**File:** `dashboard/src/services/caseStorage.ts:80-84`
**Issue:** Case IDs use timestamp + counter pattern which is predictable. An attacker could enumerate case IDs.
**Fix:** Use crypto.randomUUID() or similar:
```typescript
export function generateCaseId(): string {
  return `case_${crypto.randomUUID().slice(0, 8)}`;
}
```

### IN-04: Missing Error Boundary

**File:** Multiple components
**Issue:** No React error boundary is defined. Any uncaught error will crash the entire application.
**Fix:** Add a root-level error boundary component.

### IN-05: Potential State Mutation During Render

**File:** `dashboard/src/components/JobQueueView.tsx:69-103`
**Issue:** WebSocket subscription in useEffect calls `setJobs` directly. If jobs array reference changes between renders, this can cause infinite update loops.
**Fix:** Use useRef to track jobIds that need subscriptions, or use a more stable subscription pattern.

---

_Reviewed: 2026-04-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
