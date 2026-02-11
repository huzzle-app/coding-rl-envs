pub const REQUIRED_EVENT_FIELDS: &[&str] = &[
    "event_id",
    "trace_id",
    "shipment_id",
    "timestamp",
    "service",
    "kind",
    "payload",
];

pub const REQUIRED_COMMAND_FIELDS: &[&str] = &[
    "command_id",
    "lane",
    "units",
    "issued_by",
    "signature",
    "deadline",
];
