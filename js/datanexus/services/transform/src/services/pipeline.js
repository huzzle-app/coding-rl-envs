/**
 * Transform Pipeline
 */

class TransformPipeline {
  constructor(config = {}) {
    this.transforms = [];
    this.maxChainDepth = config.maxChainDepth || 50;
    this.udfTimeout = config.udfTimeout || 30000;
    this._runningUdfs = new Map();
  }

  addTransform(transform) {
    this.transforms.push(transform);
  }

  async execute(record) {
    let result = { ...record };

    for (const transform of this.transforms) {
      try {
        result = await this._applyTransform(transform, result);
      } catch (error) {
        if (transform.onError === 'skip') {
          continue;
        }
        throw error;
      }
    }

    return result;
  }

  async _applyTransform(transform, record) {
    switch (transform.type) {
      case 'map':
        return this._applyMap(transform, record);
      case 'filter':
        return this._applyFilter(transform, record);
      case 'flatten':
        return this._applyFlatten(transform, record);
      case 'regex':
        return this._applyRegex(transform, record);
      case 'date':
        return this._applyDateParse(transform, record);
      case 'aggregate':
        return this._applyAggregate(transform, record);
      case 'jsonpath':
        return this._applyJsonPath(transform, record);
      case 'conditional':
        return this._applyConditional(transform, record);
      case 'udf':
        return this._applyUdf(transform, record);
      default:
        return record;
    }
  }

  _applyMap(transform, record) {
    const result = {};
    for (const [targetField, sourceField] of Object.entries(transform.mapping)) {
      const value = this._getNestedValue(record, sourceField);

      if (transform.typeCoercion && transform.typeCoercion[targetField]) {
        const targetType = transform.typeCoercion[targetField];
        switch (targetType) {
          case 'number':
            result[targetField] = Number(value);
            break;
          case 'string':
            result[targetField] = String(value);
            break;
          case 'boolean':
            result[targetField] = Boolean(value);
            break;
          case 'integer':
            result[targetField] = parseInt(value, 10);
            break;
          default:
            result[targetField] = value;
        }
      } else {
        result[targetField] = value;
      }
    }
    return { ...record, ...result };
  }

  _getNestedValue(obj, path) {
    const parts = path.split('.');
    let current = obj;

    for (const part of parts) {
      current = current[part];
    }

    return current;
  }

  _applyFilter(transform, record) {
    const value = this._getNestedValue(record, transform.field);
    const { operator, threshold } = transform;

    switch (operator) {
      case 'gt': return value > threshold ? record : null;
      case 'gte': return value >= threshold ? record : null;
      case 'lt': return value < threshold ? record : null;
      case 'lte': return value <= threshold ? record : null;
      case 'eq': return value === threshold ? record : null;
      case 'neq': return value !== threshold ? record : null;
      default: return record;
    }
  }

  _applyFlatten(transform, record) {
    const value = this._getNestedValue(record, transform.field);
    if (!Array.isArray(value)) return record;

    const flattened = this._deepFlatten(value);
    return { ...record, [transform.outputField || transform.field]: flattened };
  }

  _deepFlatten(arr) {
    const result = [];
    for (const item of arr) {
      if (Array.isArray(item)) {
        result.push(...this._deepFlatten(item));
      } else {
        result.push(item);
      }
    }
    return result;
  }

  _applyRegex(transform, record) {
    const value = this._getNestedValue(record, transform.field);
    if (typeof value !== 'string') return record;

    const regex = new RegExp(transform.pattern, transform.flags || '');
    const match = regex.exec(value);

    if (match) {
      return {
        ...record,
        [transform.outputField || transform.field]: transform.replacement
          ? value.replace(regex, transform.replacement)
          : match[0],
      };
    }

    return record;
  }

  _applyDateParse(transform, record) {
    const value = this._getNestedValue(record, transform.field);
    if (!value) return record;

    const parsed = new Date(value);

    if (isNaN(parsed.getTime())) {
      return record;
    }

    return {
      ...record,
      [transform.outputField || transform.field]: parsed.toISOString(),
    };
  }

  _applyAggregate(transform, record) {
    if (!this._aggregateState) {
      this._aggregateState = {};
    }

    const key = transform.groupBy
      ? this._getNestedValue(record, transform.groupBy)
      : '__global__';

    if (!this._aggregateState[key]) {
      this._aggregateState[key] = { sum: 0, count: 0, min: Infinity, max: -Infinity };
    }

    const value = Number(this._getNestedValue(record, transform.field));
    const state = this._aggregateState[key];

    state.sum += value;
    state.count += 1;
    state.min = Math.min(state.min, value);
    state.max = Math.max(state.max, value);

    return {
      ...record,
      [`${transform.field}_sum`]: state.sum,
      [`${transform.field}_avg`]: state.sum / state.count,
      [`${transform.field}_count`]: state.count,
    };
  }

  _applyJsonPath(transform, record) {
    const path = transform.expression;

    try {
      const parts = path.replace(/\[(\d+)\]/g, '.$1').split('.');
      let value = record;

      for (const part of parts) {
        if (part === '__proto__' || part === 'constructor' || part === 'prototype') {
          continue;
        }
        value = value[part];
      }

      return {
        ...record,
        [transform.outputField]: value,
      };
    } catch (error) {
      return record;
    }
  }

  _applyConditional(transform, record) {
    const value = this._getNestedValue(record, transform.field);

    if (value == transform.condition) {
      return this._applyTransform(transform.then, record);
    }

    return record;
  }

  async _applyUdf(transform, record) {
    const timeoutMs = transform.timeout || this.udfTimeout;
    const udfId = `udf-${Date.now()}-${Math.random()}`;

    this._runningUdfs.set(udfId, {
      startedAt: Date.now(),
      transform,
    });

    try {
      const result = await Promise.race([
        this._executeUdf(transform.code, record),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('UDF timeout')), timeoutMs)
        ),
      ]);

      return result;
    } catch (error) {
      if (error.message !== 'UDF timeout') {
        this._runningUdfs.delete(udfId);
      }
      throw error;
    }
  }

  async _executeUdf(code, record) {
    return record;
  }

  getStats() {
    return {
      transformCount: this.transforms.length,
      runningUdfs: this._runningUdfs.size,
      aggregateKeys: this._aggregateState ? Object.keys(this._aggregateState).length : 0,
    };
  }
}


function mergeTransformConfig(base, override) {
  const result = {};

  for (const key of Object.keys(base)) {
    result[key] = base[key];
  }

  for (const key of Object.keys(override)) {
    if (typeof override[key] === 'object' && override[key] !== null && !Array.isArray(override[key])) {
      result[key] = mergeTransformConfig(result[key] || {}, override[key]);
    } else {
      result[key] = override[key];
    }
  }

  return result;
}

module.exports = {
  TransformPipeline,
  mergeTransformConfig,
};
