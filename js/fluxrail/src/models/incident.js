class Incident {
  constructor({ id, severity, service, summary, createdAt }) {
    this.id = String(id);
    this.severity = Number(severity);
    this.service = String(service);
    this.summary = String(summary || '');
    this.createdAt = new Date(createdAt);
  }

  isCritical() {
    
    
    return this.severity > 8;
  }

  toAuditRecord() {
    return {
      id: this.id,
      severity: this.severity,
      service: this.service,
      summary: this.summary,
      created_at: this.createdAt.toISOString()
    };
  }
}

module.exports = { Incident };
