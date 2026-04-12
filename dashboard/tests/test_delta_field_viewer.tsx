/**
 * Test scaffolds for DeltaFieldViewer
 * Tests: iframe src + loading state
 */

const mockDeltaSessionResponse = {
  trame_url: 'http://localhost:8080/trame/delta/session/abc123',
  session_id: 'abc123',
};

describe('DeltaFieldViewer', () => {
  describe('render', () => {
    it('should render iframe with src={trameUrl} when available', () => {
      // TODO: Implement iframe src test
      expect(true).toBe(true);
    });

    it('should show placeholder message when no comparison selected', () => {
      // TODO: Implement placeholder test
      expect(true).toBe(true);
    });
  });

  describe('loading state', () => {
    it('should show loading state while waiting for trame_url', () => {
      // TODO: Implement loading test
      expect(true).toBe(true);
    });

    it('should not render iframe until trame_url is received', () => {
      // TODO: Implement conditional render test
      expect(true).toBe(true);
    });
  });

  describe('field selector', () => {
    it('should render field selector dropdown with Ux, Uy, Uz, p options', () => {
      // TODO: Implement field dropdown test
      expect(true).toBe(true);
    });

    it('should trigger POST /api/comparisons/{id}/delta-session?field_name=X on mount or field change', () => {
      // TODO: Implement API call test
      expect(true).toBe(true);
    });
  });

  describe('API integration', () => {
    it('should call POST /api/comparisons/{id}/delta-session with field_name parameter', () => {
      // TODO: Implement POST test
      expect(true).toBe(true);
    });

    it('should update iframe src when trame_url is returned', () => {
      // TODO: Implement URL update test
      expect(true).toBe(true);
    });
  });
});
