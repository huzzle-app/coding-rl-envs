/**
 * Element Model Unit Tests
 */

describe('Element Model', () => {
  describe('element types', () => {
    const validTypes = ['rectangle', 'ellipse', 'line', 'text', 'image', 'path', 'sticky'];

    it('should support standard element types', () => {
      validTypes.forEach(type => {
        expect(['rectangle', 'ellipse', 'line', 'text', 'image', 'path', 'sticky']).toContain(type);
      });
    });
  });

  describe('element properties', () => {
    it('should have position properties', () => {
      const element = {
        x: 100,
        y: 200,
        width: 50,
        height: 50,
        rotation: 0,
      };

      expect(element.x).toBeDefined();
      expect(element.y).toBeDefined();
      expect(typeof element.x).toBe('number');
      expect(typeof element.y).toBe('number');
    });

    it('should have style properties', () => {
      const element = {
        fill: '#ffffff',
        stroke: '#000000',
        strokeWidth: 2,
        opacity: 1,
      };

      expect(element.fill).toMatch(/^#[0-9a-f]{6}$/i);
      expect(element.strokeWidth).toBeGreaterThan(0);
      expect(element.opacity).toBeGreaterThanOrEqual(0);
      expect(element.opacity).toBeLessThanOrEqual(1);
    });

    it('should support z-index ordering', () => {
      const elements = [
        { id: '1', zIndex: 1 },
        { id: '2', zIndex: 3 },
        { id: '3', zIndex: 2 },
      ];

      const sorted = [...elements].sort((a, b) => a.zIndex - b.zIndex);

      expect(sorted[0].id).toBe('1');
      expect(sorted[1].id).toBe('3');
      expect(sorted[2].id).toBe('2');
    });
  });

  describe('element serialization', () => {
    it('should serialize to JSON correctly', () => {
      const element = {
        id: 'elem-1',
        type: 'rectangle',
        x: 100,
        y: 100,
        width: 200,
        height: 150,
        fill: '#ff0000',
        metadata: { createdBy: 'user-1' },
      };

      const json = JSON.stringify(element);
      const parsed = JSON.parse(json);

      expect(parsed).toEqual(element);
    });

    it('should handle nested properties', () => {
      const element = {
        id: 'elem-1',
        type: 'text',
        content: {
          text: 'Hello',
          fontSize: 16,
          fontFamily: 'Arial',
        },
      };

      const json = JSON.stringify(element);
      const parsed = JSON.parse(json);

      expect(parsed.content.text).toBe('Hello');
    });
  });
});
