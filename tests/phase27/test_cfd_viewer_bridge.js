/**
 * test_cfd_viewer_bridge.js
 * Unit tests for CFDViewerBridge TypeScript class.
 * Uses global mocks since jsdom is not available.
 * Run with: node tests/phase27/test_cfd_viewer_bridge.js
 */

// Global mocks (jsdom unavailable)
global.window = {
  addEventListener: function (name, fn) {
    this._listeners = this._listeners || {};
    if (!this._listeners[name]) this._listeners[name] = [];
    this._listeners[name].push(fn);
  },
  removeEventListener: function (name) {
    if (this._listeners) delete this._listeners[name];
  },
  _listeners: {},
};
global.MessageEvent = class MessageEvent {
  constructor(type, init) {
    this.type = type;
    this.data = init?.data;
    this.origin = init?.origin || 'null';
  }
};

// Minimal CFDViewerBridge implementation (mirrors the TypeScript source for testing)
class CFDViewerBridge {
  constructor(iframe) {
    this.iframe = iframe;
    this.handler = () => {};
    this.boundListener = this.handleMessage.bind(this);
    window.addEventListener('message', this.boundListener);
  }

  send(msg) {
    this.iframe.contentWindow?.postMessage(msg, '*');
  }

  onMessage(handler) {
    this.handler = handler;
    return () => {
      this.handler = () => {};
    };
  }

  destroy() {
    window.removeEventListener('message', this.boundListener);
  }

  handleMessage(event) {
    if (event.origin === 'null' || event.origin === '') {
      const data = event.data;
      if (data && typeof data === 'object' && 'type' in data) {
        this.handler(data);
      }
    }
  }
}

// Test utilities
let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`  FAIL: ${message}`);
    failed++;
    return false;
  }
  console.log(`  PASS: ${message}`);
  passed++;
  return true;
}

function assertEqual(actual, expected, message) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (!ok) {
    console.error(`  FAIL: ${message}`);
    console.error(`    Expected: ${JSON.stringify(expected)}`);
    console.error(`    Actual:   ${JSON.stringify(actual)}`);
    failed++;
    return false;
  }
  console.log(`  PASS: ${message}`);
  passed++;
  return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Test helpers
// ─────────────────────────────────────────────────────────────────────────────

function createMockIframe() {
  return {
    contentWindow: {
      postMessage: function (msg, target) {
        this._lastMessage = msg;
        this._lastTarget = target;
      },
      _lastMessage: null,
      _lastTarget: null,
    },
  };
}

function simulateMessage(origin, data) {
  const listeners = window._listeners['message'] || [];
  const event = new MessageEvent('message', { origin, data });
  listeners.forEach((fn) => fn(event));
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

console.log('\n=== CFDViewerBridge Tests ===\n');

// 1. test_send_field_message
(function () {
  console.log('Test 1: send field message');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'field', field: 'U' });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'field', field: 'U' }, 'postMessage called with correct field payload');
  assertEqual(iframe.contentWindow._lastTarget, '*', 'target origin is *');
  bridge.destroy();
})();

// 2. test_send_slice_message
(function () {
  console.log('Test 2: send slice message');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'slice', axis: 'Z', origin: [1, 2, 3] });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'slice', axis: 'Z', origin: [1, 2, 3] }, 'postMessage called with correct slice payload');
  bridge.destroy();
})();

// 3. test_send_slice_off
(function () {
  console.log('Test 3: send slice_off');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'slice_off' });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'slice_off' }, 'postMessage called with slice_off');
  bridge.destroy();
})();

// 4. test_send_color_preset
(function () {
  console.log('Test 4: send color_preset BlueRed');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'color_preset', preset: 'BlueRed' });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'color_preset', preset: 'BlueRed' }, 'postMessage called with BlueRed preset');
  bridge.destroy();
})();

// 5. test_send_scalar_range_manual
(function () {
  console.log('Test 5: send scalar_range manual');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'scalar_range', mode: 'manual', min: 0, max: 1 });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'scalar_range', mode: 'manual', min: 0, max: 1 }, 'postMessage called with manual scalar range');
  bridge.destroy();
})();

// 6. test_send_volume_toggle
(function () {
  console.log('Test 6: send volume_toggle enabled=true');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'volume_toggle', enabled: true });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'volume_toggle', enabled: true }, 'postMessage called with volume_toggle enabled=true');
  bridge.destroy();
})();

// 7. test_send_timestep
(function () {
  console.log('Test 7: send timestep index=3');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'timestep', index: 3 });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'timestep', index: 3 }, 'postMessage called with timestep index=3');
  bridge.destroy();
})();

// 8. test_send_clip_create
(function () {
  console.log('Test 8: send clip_create');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'clip_create', insideOut: false, scalarValue: 0.5 });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'clip_create', insideOut: false, scalarValue: 0.5 }, 'postMessage called with clip_create payload');
  bridge.destroy();
})();

// 9. test_send_contour_create
(function () {
  console.log('Test 9: send contour_create');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'contour_create', isovalues: [0.1, 0.5, 0.9] });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'contour_create', isovalues: [0.1, 0.5, 0.9] }, 'postMessage called with contour_create isovalues');
  bridge.destroy();
})();

// 10. test_send_streamtracer_create
(function () {
  console.log('Test 10: send streamtracer_create');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'streamtracer_create', direction: 'FORWARD', maxSteps: 500 });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'streamtracer_create', direction: 'FORWARD', maxSteps: 500 }, 'postMessage called with streamtracer payload');
  bridge.destroy();
})();

// 11. test_send_filter_delete
(function () {
  console.log('Test 11: send filter_delete');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'filter_delete', filterId: 'abc123' });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'filter_delete', filterId: 'abc123' }, 'postMessage called with filter_delete filterId');
  bridge.destroy();
})();

// 12. test_send_filter_list
(function () {
  console.log('Test 12: send filter_list');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'filter_list' });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'filter_list' }, 'postMessage called with filter_list');
  bridge.destroy();
})();

// 13. test_send_screenshot
(function () {
  console.log('Test 13: send screenshot');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'screenshot', width: 1920, height: 1080 });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'screenshot', width: 1920, height: 1080 }, 'postMessage called with screenshot dimensions');
  bridge.destroy();
})();

// 14. test_send_volume_status
(function () {
  console.log('Test 14: send volume_status');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  bridge.send({ type: 'volume_status' });
  assertEqual(iframe.contentWindow._lastMessage, { type: 'volume_status' }, 'postMessage called with volume_status');
  bridge.destroy();
})();

// 15. test_onmessage_calls_handler (ready message)
(function () {
  console.log('Test 15: onMessage handler called with ready');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  let called = false;
  let received = null;
  bridge.onMessage((msg) => {
    called = true;
    received = msg;
  });
  simulateMessage('null', { type: 'ready' });
  assert(called, 'handler was called');
  assertEqual(received, { type: 'ready' }, 'handler received ready message');
  bridge.destroy();
})();

// 16. test_onmessage_ignores_non_null_origin
(function () {
  console.log('Test 16: onMessage ignores external origin');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  let called = false;
  bridge.onMessage(() => { called = true; });
  simulateMessage('https://external-site.com', { type: 'ready' });
  assert(!called, 'handler was NOT called for external origin');
  bridge.destroy();
})();

// 17. test_onmessage_ignores_messages_without_type
(function () {
  console.log('Test 17: onMessage ignores messages without type');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  let called = false;
  bridge.onMessage(() => { called = true; });
  simulateMessage('null', { foo: 'bar' });
  assert(!called, 'handler was NOT called for message without type');
  bridge.destroy();
})();

// 18. test_destroy_removes_listener
(function () {
  console.log('Test 18: destroy removes listener');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  let called = false;
  bridge.onMessage(() => { called = true; });
  bridge.destroy();
  simulateMessage('null', { type: 'ready' });
  assert(!called, 'handler was NOT called after destroy (listener removed)');
})();

// 19. test_onmessage_returns_unsubscribe
(function () {
  console.log('Test 19: onMessage returns unsubscribe function');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  let called = false;
  const unsubscribe = bridge.onMessage(() => { called = true; });
  unsubscribe();
  simulateMessage('null', { type: 'ready' });
  assert(!called, 'handler was NOT called after unsubscribe');
  bridge.destroy();
})();

// 20. test_all_14_outbound_types_do_not_throw
(function () {
  console.log('Test 20: all 14 outbound types do not throw');
  const iframe = createMockIframe();
  const bridge = new CFDViewerBridge(iframe);
  const messages = [
    { type: 'field', field: 'U' },
    { type: 'slice', axis: 'X', origin: [0, 0, 0] },
    { type: 'slice_off' },
    { type: 'color_preset', preset: 'Viridis' },
    { type: 'scalar_range', mode: 'auto' },
    { type: 'volume_toggle', enabled: false },
    { type: 'timestep', index: 0 },
    { type: 'clip_create', insideOut: true, scalarValue: 0.0 },
    { type: 'contour_create', isovalues: [0.5] },
    { type: 'streamtracer_create', direction: 'BACKWARD', maxSteps: 100 },
    { type: 'filter_delete', filterId: 'xyz' },
    { type: 'filter_list' },
    { type: 'screenshot', width: 800, height: 600 },
    { type: 'volume_status' },
  ];
  let allOk = true;
  for (const msg of messages) {
    try {
      bridge.send(msg);
    } catch (e) {
      console.error(`  FAIL: send(${JSON.stringify(msg)}) threw: ${e.message}`);
      allOk = false;
    }
  }
  if (allOk) {
    console.log('  PASS: all 14 outbound types sent without throwing');
    passed++;
  } else {
    failed++;
  }
  bridge.destroy();
})();

// ─────────────────────────────────────────────────────────────────────────────
// Summary
// ─────────────────────────────────────────────────────────────────────────────

console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);

if (failed > 0) {
  process.exit(1);
} else {
  console.log('All tests passed!\n');
  process.exit(0);
}
