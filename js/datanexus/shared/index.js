/**
 * DataNexus Shared Module
 *
 * BUG L1: Circular import between clients, events, utils, and stream
 */


// clients -> events -> utils -> stream -> clients
const { ServiceClient, CircuitBreaker } = require('./clients');
const { EventBus, BaseEvent, SchemaRegistry } = require('./events');
const { DistributedLock, LeaderElection, generateId } = require('./utils');
const { StreamProcessor, WindowManager, WatermarkTracker } = require('./stream');

module.exports = {
  ServiceClient,
  CircuitBreaker,
  EventBus,
  BaseEvent,
  SchemaRegistry,
  DistributedLock,
  LeaderElection,
  generateId,
  StreamProcessor,
  WindowManager,
  WatermarkTracker,
};
