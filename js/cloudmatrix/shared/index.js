/**
 * CloudMatrix Shared Module
 */


const { ServiceClient, CircuitBreaker } = require('./clients');
const { EventBus, BaseEvent } = require('./events');
const { DistributedLock, LeaderElection, generateId } = require('./utils');
const { CRDTDocument, OperationalTransform, WebSocketManager } = require('./realtime');

module.exports = {
  ServiceClient,
  CircuitBreaker,
  EventBus,
  BaseEvent,
  DistributedLock,
  LeaderElection,
  generateId,
  CRDTDocument,
  OperationalTransform,
  WebSocketManager,
};
