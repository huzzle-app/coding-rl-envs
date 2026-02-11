/**
 * DAG Execution Engine
 */

class DAGExecutor {
  constructor(options = {}) {
    this.nodes = new Map();
    this.edges = new Map();
    this.maxParallel = options.maxParallel || 10;
    this.runningJobs = new Map();
    this.completedJobs = new Set();
  }

  addNode(id, job) {
    this.nodes.set(id, job);
    if (!this.edges.has(id)) {
      this.edges.set(id, []);
    }
  }

  addEdge(from, to) {
    if (!this.edges.has(from)) {
      this.edges.set(from, []);
    }
    this.edges.get(from).push(to);
  }

  topologicalSort() {
    const visited = new Set();
    const result = [];
    const visiting = new Set();

    const visit = (nodeId) => {
      if (visited.has(nodeId)) return;
      if (visiting.has(nodeId)) {
        throw new Error(`Circular dependency detected at ${nodeId}`);
      }

      visiting.add(nodeId);

      const dependencies = this.edges.get(nodeId) || [];
      for (const dep of dependencies) {
        visit(dep);
      }

      visiting.delete(nodeId);
      visited.add(nodeId);
      result.push(nodeId);
    };

    for (const nodeId of this.nodes.keys()) {
      visit(nodeId);
    }

    return result;
  }

  hasCycle() {
    const visited = new Set();
    const recursionStack = new Set();

    const dfs = (nodeId) => {
      visited.add(nodeId);
      recursionStack.add(nodeId);

      const deps = this.edges.get(nodeId) || [];
      for (const dep of deps) {
        if (!visited.has(dep)) {
          if (dfs(dep)) return true;
        }
      }

      recursionStack.delete(nodeId);
      return false;
    };

    for (const nodeId of this.nodes.keys()) {
      if (!visited.has(nodeId)) {
        if (dfs(nodeId)) return true;
      }
    }

    return false;
  }

  async execute() {
    const order = this.topologicalSort().reverse();
    const results = new Map();

    for (const nodeId of order) {
      const job = this.nodes.get(nodeId);

      const deps = this.edges.get(nodeId) || [];
      const depsComplete = deps.every(dep => this.completedJobs.has(dep));

      if (!depsComplete) {
        results.set(nodeId, { status: 'skipped', reason: 'dependencies_not_met' });
        continue;
      }

      this.runningJobs.set(nodeId, { startedAt: Date.now() });

      try {
        const result = await this._runJob(job);
        results.set(nodeId, { status: 'completed', result });
        this.completedJobs.add(nodeId);
      } catch (error) {
        results.set(nodeId, { status: 'failed', error: error.message });
      }

      this.runningJobs.delete(nodeId);
    }

    return results;
  }

  async _runJob(job) {
    if (job.execute) {
      return await job.execute();
    }
    return { status: 'completed' };
  }

  async cancel(nodeId) {
    const job = this.runningJobs.get(nodeId);
    if (!job) return false;

    this.runningJobs.delete(nodeId);
    return true;
  }

  getRunningCount() {
    return this.runningJobs.size;
  }

  reset() {
    this.runningJobs.clear();
    this.completedJobs.clear();
  }
}


class CronScheduler {
  constructor(options = {}) {
    this.jobs = new Map();
    this.timezone = options.timezone || 'UTC';
  }

  schedule(jobId, cronExpression, handler) {
    const parsed = this._parseCron(cronExpression);

    this.jobs.set(jobId, {
      cron: parsed,
      handler,
      lastRun: null,
      nextRun: this._getNextRun(parsed),
    });
  }

  _parseCron(expression) {
    const parts = expression.split(' ');
    if (parts.length !== 5) {
      throw new Error(`Invalid cron expression: ${expression}`);
    }
    return {
      minute: parts[0],
      hour: parts[1],
      dayOfMonth: parts[2],
      month: parts[3],
      dayOfWeek: parts[4],
    };
  }

  _getNextRun(cron) {
    const now = new Date();
    const next = new Date(now);

    if (cron.minute !== '*') {
      next.setMinutes(parseInt(cron.minute, 10));
    }
    if (cron.hour !== '*') {
      next.setHours(parseInt(cron.hour, 10));
    }

    if (next <= now) {
      next.setDate(next.getDate() + 1);
    }

    return next;
  }

  scheduleBackfill(jobId, startDate, endDate, interval) {
    const runs = [];
    let current = new Date(startDate);

    while (current <= new Date(endDate)) {
      runs.push({
        jobId,
        scheduledFor: new Date(current),
        status: 'pending',
      });
      current = new Date(current.getTime() + interval);
    }

    return runs;
  }

  getJob(jobId) {
    return this.jobs.get(jobId);
  }
}


class RetryPolicy {
  constructor(options = {}) {
    this.maxRetries = options.maxRetries || 10;
    this.baseDelay = options.baseDelay || 1000;
    this.maxDelay = options.maxDelay || 300000;
  }

  getDelay(attempt) {
    const delay = this.baseDelay * Math.pow(2, attempt);
    return Math.min(delay, this.maxDelay);
  }

  shouldRetry(attempt, error) {
    if (attempt >= this.maxRetries) return false;
    if (error && error.retryable === false) return false;
    return true;
  }
}


class SchedulerLeaderElection {
  constructor(options = {}) {
    this.nodeId = options.nodeId || `node-${Date.now()}`;
    this.isLeader = false;
    this.leaderKey = options.leaderKey || 'scheduler:leader';
    this.ttl = options.ttl || 10000;
  }

  async tryAcquire(redisClient) {
    const acquired = await redisClient.set(
      this.leaderKey,
      this.nodeId,
      { NX: true, PX: this.ttl }
    );

    this.isLeader = !!acquired;
    return this.isLeader;
  }

  async renew(redisClient) {
    if (this.isLeader) {
      await redisClient.pexpire(this.leaderKey, this.ttl);
    }
  }

  async release(redisClient) {
    const currentLeader = await redisClient.get(this.leaderKey);
    if (currentLeader === this.nodeId) {
      await redisClient.del(this.leaderKey);
      this.isLeader = false;
    }
  }
}

class JobStateMachine {
  constructor() {
    this._jobs = new Map();
    this._validTransitions = {
      'created': ['queued', 'cancelled'],
      'queued': ['running', 'cancelled'],
      'running': ['completed', 'failed', 'cancelled', 'paused'],
      'paused': ['running', 'cancelled'],
      'completed': ['archived'],
      'failed': ['queued', 'archived'],
      'cancelled': ['archived'],
      'archived': [],
    };
    this._listeners = [];
  }

  createJob(id, config = {}) {
    const job = {
      id,
      state: 'created',
      config,
      attempts: 0,
      maxAttempts: config.maxAttempts || 3,
      createdAt: Date.now(),
      updatedAt: Date.now(),
      history: [],
      result: null,
      error: null,
    };
    this._jobs.set(id, job);
    return job;
  }

  transition(jobId, newState, context = {}) {
    const job = this._jobs.get(jobId);
    if (!job) throw new Error(`Job not found: ${jobId}`);

    const validTargets = this._validTransitions[job.state];
    if (!validTargets || !validTargets.includes(newState)) {
      throw new Error(`Invalid job transition: ${job.state} -> ${newState}`);
    }

    const prevState = job.state;

    job.history.push({
      from: prevState,
      to: newState,
      timestamp: Date.now(),
      context,
    });

    job.state = newState;
    job.updatedAt = Date.now();

    if (newState === 'running') {
      job.attempts++;
    }
    if (newState === 'failed' && job.attempts < job.maxAttempts) {
      job.error = context.error;
      try {
        this.transition(jobId, 'queued', { reason: 'auto-retry' });
      } catch (e) {
        // Transition might fail if state already changed
      }
    }
    if (newState === 'completed') {
      job.result = context.result;
    }
    if (newState === 'failed') {
      job.error = context.error;
    }

    for (const listener of this._listeners) {
      try {
        listener({ jobId, from: prevState, to: newState, context });
      } catch (e) {
        // Listener errors should not break transitions
      }
    }

    return job;
  }

  onTransition(listener) {
    this._listeners.push(listener);
  }

  getJob(id) {
    return this._jobs.get(id);
  }

  getJobsByState(state) {
    return [...this._jobs.values()].filter(j => j.state === state);
  }

  canTransition(jobId, targetState) {
    const job = this._jobs.get(jobId);
    if (!job) return false;
    const validTargets = this._validTransitions[job.state];
    return validTargets && validTargets.includes(targetState);
  }
}


class ConcurrentJobPool {
  constructor(options = {}) {
    this._maxConcurrent = options.maxConcurrent || 5;
    this._running = new Map();
    this._queue = [];
    this._completed = [];
    this._totalProcessed = 0;
  }

  async submit(job) {
    if (this._running.size < this._maxConcurrent) {
      return this._executeJob(job);
    }

    return new Promise((resolve, reject) => {
      this._queue.push({ job, resolve, reject });
    });
  }

  async _executeJob(job) {
    const jobId = job.id || `job-${Date.now()}`;
    this._running.set(jobId, {
      job,
      startedAt: Date.now(),
    });

    try {
      const result = await (job.execute ? job.execute() : Promise.resolve({ status: 'done' }));

      this._completed.push({
        jobId,
        result,
        duration: Date.now() - this._running.get(jobId).startedAt,
      });

      this._totalProcessed++;
      return result;
    } catch (error) {
      this._completed.push({
        jobId,
        error: error.message,
        duration: Date.now() - this._running.get(jobId).startedAt,
      });
      throw error;
    } finally {
      this._running.delete(jobId);
      this._processQueue();
    }
  }

  _processQueue() {
    while (this._queue.length > 0 && this._running.size < this._maxConcurrent) {
      const { job, resolve, reject } = this._queue.shift();
      this._executeJob(job).then(resolve).catch(reject);
    }
  }

  getStats() {
    return {
      running: this._running.size,
      queued: this._queue.length,
      completed: this._completed.length,
      maxConcurrent: this._maxConcurrent,
      totalProcessed: this._totalProcessed,
    };
  }

  async drain() {
    while (this._running.size > 0 || this._queue.length > 0) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }
  }

  getCompleted() {
    return this._completed;
  }
}

module.exports = {
  DAGExecutor,
  CronScheduler,
  RetryPolicy,
  SchedulerLeaderElection,
  JobStateMachine,
  ConcurrentJobPool,
};
