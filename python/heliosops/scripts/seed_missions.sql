-- HeliosOps Seed Data
-- Populates baseline data for development and testing

-- Organizations
INSERT INTO organizations (id, name, slug, settings) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'Metro Fire Department', 'metro-fd', '{"dispatch_mode": "auto", "max_units_per_incident": 10}'),
    ('a0000000-0000-0000-0000-000000000002', 'County EMS', 'county-ems', '{"dispatch_mode": "manual", "max_units_per_incident": 6}'),
    ('a0000000-0000-0000-0000-000000000003', 'State Police HQ', 'state-police', '{"dispatch_mode": "auto", "max_units_per_incident": 15}')
ON CONFLICT (slug) DO NOTHING;

-- Users (password_hash = bcrypt of 'password123')
INSERT INTO users (id, org_id, email, password_hash, role) VALUES
    ('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'admin@metro-fd.gov', '$2b$12$LJ3m4ys3GZ.kFzAU.RHV3Ov5dXQWG5p0x.tUvCXGE5HE6YQJhBW9C', 'admin'),
    ('b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'dispatch@metro-fd.gov', '$2b$12$LJ3m4ys3GZ.kFzAU.RHV3Ov5dXQWG5p0x.tUvCXGE5HE6YQJhBW9C', 'dispatcher'),
    ('b0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000002', 'ops@county-ems.gov', '$2b$12$LJ3m4ys3GZ.kFzAU.RHV3Ov5dXQWG5p0x.tUvCXGE5HE6YQJhBW9C', 'operator'),
    ('b0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000003', 'admin@state-police.gov', '$2b$12$LJ3m4ys3GZ.kFzAU.RHV3Ov5dXQWG5p0x.tUvCXGE5HE6YQJhBW9C', 'admin')
ON CONFLICT (email) DO NOTHING;

-- Units (response vehicles)
INSERT INTO units (id, org_id, name, unit_type, status, location_lat, location_lng, certifications) VALUES
    ('c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Engine 1', 'fire', 'available', 40.7128, -74.0060, '{"structure_fire","hazmat_basic"}'),
    ('c0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'Engine 2', 'fire', 'available', 40.7200, -74.0100, '{"structure_fire","wildland"}'),
    ('c0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Ladder 1', 'fire', 'on_call', 40.7150, -74.0080, '{"structure_fire","high_rise","rescue"}'),
    ('c0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'HazMat 1', 'hazmat', 'available', 40.7180, -74.0050, '{"hazmat_advanced","decon"}'),
    ('c0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000002', 'Medic 1', 'medical', 'available', 40.7300, -73.9900, '{"als","critical_care"}'),
    ('c0000000-0000-0000-0000-000000000006', 'a0000000-0000-0000-0000-000000000002', 'Medic 2', 'medical', 'dispatched', 40.7250, -73.9950, '{"bls"}'),
    ('c0000000-0000-0000-0000-000000000007', 'a0000000-0000-0000-0000-000000000002', 'Supervisor 1', 'medical', 'available', 40.7280, -73.9920, '{"als","critical_care","supervisor"}'),
    ('c0000000-0000-0000-0000-000000000008', 'a0000000-0000-0000-0000-000000000003', 'Unit 101', 'police', 'available', 40.7500, -73.9800, '{"patrol","traffic"}'),
    ('c0000000-0000-0000-0000-000000000009', 'a0000000-0000-0000-0000-000000000003', 'Unit 102', 'police', 'on_call', 40.7520, -73.9780, '{"patrol","k9"}'),
    ('c0000000-0000-0000-0000-000000000010', 'a0000000-0000-0000-0000-000000000003', 'SWAT 1', 'police', 'available', 40.7480, -73.9820, '{"tactical","hostage_rescue"}')
ON CONFLICT DO NOTHING;

-- Incidents
INSERT INTO incidents (id, org_id, title, description, severity, priority, status, incident_type, location_lat, location_lng) VALUES
    ('d0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Structure Fire - 123 Main St', 'Three-story residential fire, smoke visible from Block 4', 5, 1, 'open', 'structure_fire', 40.7135, -74.0065),
    ('d0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000002', 'Multi-Vehicle Accident - Highway 9', 'Four-car pileup with reported injuries, lane closures needed', 4, 2, 'open', 'traffic_accident', 40.7310, -73.9910),
    ('d0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'HazMat Spill - Industrial Park', 'Unknown chemical spill at Warehouse 7, area evacuated', 5, 1, 'acknowledged', 'hazmat_spill', 40.7190, -74.0045),
    ('d0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000003', 'Civil Disturbance - City Center', 'Large gathering blocking traffic, potential escalation', 3, 3, 'open', 'civil_disturbance', 40.7510, -73.9805),
    ('d0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000002', 'Medical Emergency - Office Building', 'Cardiac arrest reported on 5th floor', 5, 1, 'dispatched', 'medical_emergency', 40.7260, -73.9960)
ON CONFLICT DO NOTHING;

-- SLA Configurations
INSERT INTO sla_configs (org_id, severity, response_minutes, resolution_minutes) VALUES
    ('a0000000-0000-0000-0000-000000000001', 5, 5, 120),
    ('a0000000-0000-0000-0000-000000000001', 4, 10, 240),
    ('a0000000-0000-0000-0000-000000000001', 3, 20, 480),
    ('a0000000-0000-0000-0000-000000000001', 2, 60, 1440),
    ('a0000000-0000-0000-0000-000000000001', 1, 120, 2880),
    ('a0000000-0000-0000-0000-000000000002', 5, 4, 90),
    ('a0000000-0000-0000-0000-000000000002', 4, 8, 180),
    ('a0000000-0000-0000-0000-000000000002', 3, 15, 360),
    ('a0000000-0000-0000-0000-000000000002', 2, 45, 720),
    ('a0000000-0000-0000-0000-000000000002', 1, 90, 1440),
    ('a0000000-0000-0000-0000-000000000003', 5, 3, 60),
    ('a0000000-0000-0000-0000-000000000003', 4, 8, 120),
    ('a0000000-0000-0000-0000-000000000003', 3, 15, 360),
    ('a0000000-0000-0000-0000-000000000003', 2, 30, 720),
    ('a0000000-0000-0000-0000-000000000003', 1, 60, 1440)
ON CONFLICT (org_id, severity) DO NOTHING;

-- Feature Flags
INSERT INTO feature_flags (flag_name, is_enabled, rollout_percentage) VALUES
    ('enable_advanced_routing', true, 100),
    ('enable_kafka_events', true, 100),
    ('enable_compliance_reporting', true, 100),
    ('enable_analytics_pipeline', true, 50),
    ('enable_auto_dispatch', false, 0),
    ('enable_ml_prioritization', false, 0)
ON CONFLICT (flag_name) DO NOTHING;
