/**
 * MediaFlow Shared Module
 *
 * BUG L1: Circular import between clients, events, and utils
 */


// clients -> events -> utils -> clients
const { ServiceClient, CircuitBreaker } = require('./clients');
const { EventBus, BaseEvent } = require('./events');
const { DistributedLock, LeaderElection } = require('./utils');

module.exports = {
  ServiceClient,
  CircuitBreaker,
  EventBus,
  BaseEvent,
  DistributedLock,
  LeaderElection,
};
