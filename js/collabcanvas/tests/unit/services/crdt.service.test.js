/**
 * CRDT Service Unit Tests
 *
 * Tests for bugs B1, B2, B3
 */

const CRDTService = require('../../../src/services/canvas/crdt.service');

describe('CRDTService', () => {
  let crdtService;

  beforeEach(() => {
    crdtService = new CRDTService();
  });

  describe('compareVectorClocks', () => {
    test('should correctly compare numeric values', () => {
      const clock1 = { node1: 5, node2: 3 };
      const clock2 = { node1: 4, node2: 3 };

      expect(crdtService.compareVectorClocks(clock1, clock2)).toBe(1);
    });

    test('should return -1 when clock2 is ahead', () => {
      const clock1 = { node1: 3, node2: 3 };
      const clock2 = { node1: 5, node2: 3 };

      expect(crdtService.compareVectorClocks(clock1, clock2)).toBe(-1);
    });

    test('should return 0 for equal clocks', () => {
      const clock1 = { node1: 5, node2: 3 };
      const clock2 = { node1: 5, node2: 3 };

      expect(crdtService.compareVectorClocks(clock1, clock2)).toBe(0);
    });

    test('should return null for concurrent clocks', () => {
      const clock1 = { node1: 5, node2: 2 };
      const clock2 = { node1: 3, node2: 4 };

      expect(crdtService.compareVectorClocks(clock1, clock2)).toBeNull();
    });

    
    test('should handle string values from JSON parsing', () => {
      // Simulates values that came from JSON.parse()
      const clock1 = { node1: '10', node2: '3' };
      const clock2 = { node1: '9', node2: '3' };

      
      // Expected: 1 (clock1 is ahead because 10 > 9)
      expect(crdtService.compareVectorClocks(clock1, clock2)).toBe(1);
    });

    test('should handle mixed string and number values', () => {
      const clock1 = { node1: '5', node2: 3 };
      const clock2 = { node1: 4, node2: '3' };

      expect(crdtService.compareVectorClocks(clock1, clock2)).toBe(1);
    });

    test('should handle missing nodes in one clock', () => {
      const clock1 = { node1: 5 };
      const clock2 = { node1: 5, node2: 3 };

      expect(crdtService.compareVectorClocks(clock1, clock2)).toBe(-1);
    });
  });

  describe('tick', () => {
    test('should increment local clock', () => {
      const clock1 = crdtService.tick();
      const clock2 = crdtService.tick();

      expect(clock1[crdtService.nodeId]).toBe(1);
      expect(clock2[crdtService.nodeId]).toBe(2);
    });
  });

  describe('mergeClock', () => {
    test('should take max of each node', () => {
      crdtService.vectorClock = { node1: 5, node2: 3 };
      const remote = { node1: 3, node2: 7, node3: 2 };

      const merged = crdtService.mergeClock(remote);

      expect(merged.node1).toBe(5);
      expect(merged.node2).toBe(7);
      expect(merged.node3).toBe(2);
    });
  });

  describe('mergeState', () => {
    
    test('should preserve nested object properties after merge', () => {
      const localState = {
        element1: {
          x: 0,
          y: 0,
          properties: {
            fill: 'red',
            stroke: 'black',
            nested: { deep: 'value' }
          }
        }
      };

      const remoteState = {
        element1: {
          properties: {
            fill: 'blue'
          }
        }
      };

      const merged = crdtService.mergeState(localState, remoteState);

      
      expect(merged.element1.properties.stroke).toBe('black');
      expect(merged.element1.properties.nested).toBeDefined();
      expect(merged.element1.properties.nested.deep).toBe('value');
    });

    test('should not mutate original state objects', () => {
      const localState = {
        element1: { x: 0, y: 0 }
      };
      const original = JSON.parse(JSON.stringify(localState));

      const remoteState = {
        element1: { x: 100 }
      };

      crdtService.mergeState(localState, remoteState);

      
      expect(localState).toEqual(original);
    });

    
    test('should prevent prototype pollution attacks', () => {
      const maliciousPayload = JSON.parse('{"__proto__": {"polluted": true}}');
      const localState = { element1: { x: 0 } };

      crdtService.mergeState(localState, maliciousPayload);

      
      expect({}.polluted).toBeUndefined();
    });

    test('should prevent constructor pollution', () => {
      const maliciousPayload = {
        constructor: {
          prototype: {
            malicious: true
          }
        }
      };
      const localState = { element1: { x: 0 } };

      crdtService.mergeState(localState, maliciousPayload);

      expect({}.malicious).toBeUndefined();
    });

    test('should merge simple values correctly', () => {
      const localState = { a: 1, b: 2 };
      const remoteState = { b: 3, c: 4 };

      const merged = crdtService.mergeState(localState, remoteState);

      expect(merged.a).toBe(1);
      expect(merged.b).toBe(3);
      expect(merged.c).toBe(4);
    });
  });

  describe('createOperation', () => {
    test('should create operation with incremented clock', () => {
      const op = crdtService.createOperation('elem1', { x: 100 }, 'update');

      expect(op.id).toBeDefined();
      expect(op.elementId).toBe('elem1');
      expect(op.type).toBe('update');
      expect(op.changes.x).toBe(100);
      expect(op.clock[crdtService.nodeId]).toBe(1);
      expect(op.timestamp).toBeDefined();
    });
  });

  describe('applyOperation', () => {
    test('should create new element', () => {
      const state = { elements: {} };
      const op = {
        elementId: 'elem1',
        type: 'create',
        changes: { x: 0, y: 0, type: 'rectangle' }
      };

      const newState = crdtService.applyOperation(op, state);

      expect(newState.elements.elem1).toBeDefined();
      expect(newState.elements.elem1.type).toBe('rectangle');
    });

    test('should update existing element', () => {
      const state = {
        elements: {
          elem1: { x: 0, y: 0, type: 'rectangle' }
        }
      };
      const op = {
        elementId: 'elem1',
        type: 'update',
        changes: { x: 100 }
      };

      const newState = crdtService.applyOperation(op, state);

      expect(newState.elements.elem1.x).toBe(100);
      expect(newState.elements.elem1.type).toBe('rectangle');
    });

    test('should delete element', () => {
      const state = {
        elements: {
          elem1: { x: 0, y: 0 },
          elem2: { x: 100, y: 100 }
        }
      };
      const op = {
        elementId: 'elem1',
        type: 'delete',
        changes: {}
      };

      const newState = crdtService.applyOperation(op, state);

      expect(newState.elements.elem1).toBeUndefined();
      expect(newState.elements.elem2).toBeDefined();
    });

    test('should ignore update to non-existent element', () => {
      const state = { elements: {} };
      const op = {
        elementId: 'elem1',
        type: 'update',
        changes: { x: 100 }
      };

      const newState = crdtService.applyOperation(op, state);

      expect(newState.elements.elem1).toBeUndefined();
    });
  });

  describe('detectConflicts', () => {
    test('should detect concurrent operations on same element', () => {
      const localOps = [{
        elementId: 'elem1',
        type: 'update',
        clock: { node1: 2, node2: 1 },
        timestamp: 1000
      }];

      const remoteOps = [{
        elementId: 'elem1',
        type: 'update',
        clock: { node1: 1, node2: 2 },
        timestamp: 1001
      }];

      const conflicts = crdtService.detectConflicts(localOps, remoteOps);

      expect(conflicts.length).toBe(1);
      expect(conflicts[0].local).toBe(localOps[0]);
      expect(conflicts[0].remote).toBe(remoteOps[0]);
    });

    test('should not detect conflict for different elements', () => {
      const localOps = [{
        elementId: 'elem1',
        type: 'update',
        clock: { node1: 2 },
        timestamp: 1000
      }];

      const remoteOps = [{
        elementId: 'elem2',
        type: 'update',
        clock: { node1: 1 },
        timestamp: 1001
      }];

      const conflicts = crdtService.detectConflicts(localOps, remoteOps);

      expect(conflicts.length).toBe(0);
    });
  });
});
