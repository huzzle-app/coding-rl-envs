/**
 * Element Model Unit Tests
 *
 * Tests CRDT element operations using actual CRDTService.
 * Tests bugs B1 (vector clock), B2 (shallow copy), B3 (prototype pollution)
 */

const CRDTService = require('../../../src/services/canvas/crdt.service');

describe('Element Model and CRDT Operations', () => {
  let crdtService;

  beforeEach(() => {
    crdtService = new CRDTService();
  });

  describe('element creation', () => {
    it('should create element operation', () => {
      const operation = crdtService.createOperation('elem-1', {
        type: 'rectangle',
        x: 100,
        y: 100,
        width: 200,
        height: 150,
      }, 'create');

      expect(operation).toBeDefined();
      expect(operation.elementId).toBe('elem-1');
    });

    it('should generate unique operation IDs', () => {
      const op1 = crdtService.createOperation('elem-1', { x: 0 }, 'create');
      const op2 = crdtService.createOperation('elem-2', { x: 0 }, 'create');

      expect(op1.id).not.toBe(op2.id);
    });
  });

  describe('element updates', () => {
    it('should apply update operation to state', () => {
      const state = {
        elements: {
          'elem-1': { type: 'rectangle', x: 0, y: 0, width: 100, height: 100 },
        },
        clock: {},
      };

      const operation = crdtService.createOperation('elem-1', {
        x: 50,
        y: 75,
      }, 'update');

      const newState = crdtService.applyOperation(operation, state);

      expect(newState.elements['elem-1'].x).toBe(50);
      expect(newState.elements['elem-1'].y).toBe(75);
    });

    /**
     * BUG B2: Shallow copy loses deeply nested properties.
     * mergeState only does one level of deep merge — updating a nested
     * object replaces it entirely rather than merging recursively.
     */
    it('should preserve deeply nested properties on partial style update', () => {
      const state = {
        elements: {
          'elem-1': {
            type: 'text',
            x: 0,
            y: 0,
            content: {
              text: 'Hello',
              style: { bold: true, italic: false, fontSize: 16 },
            },
          },
        },
        clock: {},
      };

      // Update style partially — only set italic to true
      const operation = crdtService.createOperation('elem-1', {
        content: { style: { italic: true } },
      }, 'update');

      const newState = crdtService.applyOperation(operation, state);

      // BUG B2: Shallow spread at content level replaces entire style object
      // After updating style.italic, style.bold and style.fontSize should be preserved
      expect(newState.elements['elem-1'].content.style.italic).toBe(true);
      expect(newState.elements['elem-1'].content.style.bold).toBe(true);
      expect(newState.elements['elem-1'].content.style.fontSize).toBe(16);
    });
  });

  describe('vector clock', () => {
    /**
     * BUG B1: Vector clock values compared without parseInt.
     * String comparison: '10' < '9' is true (lexicographic)
     * but numerically 10 > 9.
     */
    it('should correctly compare vector clock values above 9', () => {
      // When clock values come from serialized sources (Redis/JSON), they may be strings
      // Numerically: 10 > 9, so clock1 is newer (result should be 1)
      // BUG B1: Without parseInt, string comparison makes '10' < '9', giving -1
      const result = crdtService.compareVectorClocks(
        { 'node-1': '10' },
        { 'node-1': '9' }
      );
      expect(result).toBe(1);
    });

    it('should handle mixed string/number clock values', () => {
      // Clock values may be strings from JSON deserialization
      const result = crdtService.compareVectorClocks(
        { 'node-1': '20', 'node-2': '3' },
        { 'node-1': '9', 'node-2': '3' }
      );
      // node-1: 20 > 9 numerically, so clock1 is newer
      expect(result).toBe(1);
    });
  });

  describe('prototype pollution', () => {
    /**
     * BUG B3: for-in loop without hasOwnProperty check allows
     * inherited properties to be merged into element state.
     */
    it('should not merge inherited properties into element state', () => {
      const state = {
        elements: { 'elem-1': { x: 0, y: 0 } },
        clock: {},
      };

      // Create changes with inherited properties via prototype chain
      const proto = { inheritedProp: 'should-not-be-merged' };
      const changes = Object.create(proto);
      changes.x = 100;

      const operation = crdtService.createOperation('elem-1', changes, 'update');

      const newState = crdtService.applyOperation(operation, state);

      // BUG B3: for-in without hasOwnProperty includes inherited properties
      expect(newState.elements['elem-1'].x).toBe(100);
      expect(newState.elements['elem-1'].inheritedProp).toBeUndefined();
    });
  });

  describe('element serialization', () => {
    it('should handle element with all properties', () => {
      const state = {
        elements: {},
        clock: {},
      };

      const operation = crdtService.createOperation('elem-1', {
        type: 'rectangle',
        x: 100,
        y: 200,
        width: 300,
        height: 150,
        fill: '#ff0000',
        stroke: '#000000',
        strokeWidth: 2,
        opacity: 0.8,
        rotation: 45,
        metadata: { createdBy: 'user-1', createdAt: new Date().toISOString() },
      }, 'create');

      const newState = crdtService.applyOperation(operation, state);

      expect(newState.elements['elem-1']).toBeDefined();
      expect(newState.elements['elem-1'].type).toBe('rectangle');
    });
  });
});
