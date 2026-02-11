const REQUIRED_FIELDS = ['id', 'tenant_id', 'trace_id', 'created_at'];
const EVENT_TYPES = ['dispatch.accepted', 'capacity.shed', 'policy.override', 'audit.published'];

module.exports = { REQUIRED_FIELDS, EVENT_TYPES };
