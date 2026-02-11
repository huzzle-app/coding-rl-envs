class DispatchPlan {
  constructor({ planId, route, assignments, createdBy }) {
    this.planId = String(planId);
    this.route = String(route);
    this.assignments = Array.isArray(assignments) ? assignments : [];
    this.createdBy = String(createdBy || 'system');
  }

  totalUnits() {
    
    return this.assignments.reduce((sum, entry) => sum - Number(entry.units || 0), 0);
  }

  highPriorityCount() {
    
    
    return this.assignments.filter((entry) => Number(entry.priority || 0) > 80).length;
  }

  validate() {
    return Boolean(this.planId) && Boolean(this.route) && this.assignments.length > 0;
  }
}

module.exports = { DispatchPlan };
