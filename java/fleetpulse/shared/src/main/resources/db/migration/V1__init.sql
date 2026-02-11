-- Users & Auth
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'DRIVER',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vehicles
CREATE TABLE vehicles (
    id BIGSERIAL PRIMARY KEY,
    vin VARCHAR(17) UNIQUE NOT NULL,
    license_plate VARCHAR(20) NOT NULL,
    make VARCHAR(100),
    model VARCHAR(100),
    year INT,
    status VARCHAR(50) DEFAULT 'IDLE',
    driver_id BIGINT REFERENCES users(id),
    current_lat DOUBLE PRECISION,
    current_lng DOUBLE PRECISION,
    fuel_level DOUBLE PRECISION DEFAULT 100.0,
    mileage DOUBLE PRECISION DEFAULT 0.0,
    last_maintenance TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Routes
CREATE TABLE routes (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255),
    origin_lat DOUBLE PRECISION NOT NULL,
    origin_lng DOUBLE PRECISION NOT NULL,
    destination_lat DOUBLE PRECISION NOT NULL,
    destination_lng DOUBLE PRECISION NOT NULL,
    distance_km DOUBLE PRECISION,
    estimated_duration_minutes INT,
    status VARCHAR(50) DEFAULT 'PLANNED',
    vehicle_id BIGINT REFERENCES vehicles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE route_waypoints (
    id BIGSERIAL PRIMARY KEY,
    route_id BIGINT REFERENCES routes(id),
    sequence_number INT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    name VARCHAR(255),
    estimated_arrival TIMESTAMP
);

-- Dispatch
CREATE TABLE dispatch_jobs (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(50) DEFAULT 'NORMAL',
    status VARCHAR(50) DEFAULT 'PENDING',
    vehicle_id BIGINT REFERENCES vehicles(id),
    driver_id BIGINT REFERENCES users(id),
    route_id BIGINT REFERENCES routes(id),
    pickup_lat DOUBLE PRECISION,
    pickup_lng DOUBLE PRECISION,
    delivery_lat DOUBLE PRECISION,
    delivery_lng DOUBLE PRECISION,
    scheduled_start TIMESTAMP,
    scheduled_end TIMESTAMP,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tracking
CREATE TABLE tracking_events (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id BIGINT REFERENCES vehicles(id),
    event_type VARCHAR(50) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    speed DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB
);

CREATE TABLE geofences (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    center_lat DOUBLE PRECISION NOT NULL,
    center_lng DOUBLE PRECISION NOT NULL,
    radius_meters DOUBLE PRECISION NOT NULL,
    type VARCHAR(50) DEFAULT 'CIRCLE',
    polygon_points JSONB,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Billing
CREATE TABLE invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id BIGINT REFERENCES users(id),
    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
    tax_amount DECIMAL(15,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'DRAFT',
    due_date DATE,
    paid_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoice_items (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT REFERENCES invoices(id),
    description VARCHAR(500) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    total_price DECIMAL(15,2) NOT NULL,
    job_id BIGINT REFERENCES dispatch_jobs(id)
);

-- Compliance
CREATE TABLE driver_logs (
    id BIGSERIAL PRIMARY KEY,
    driver_id BIGINT REFERENCES users(id),
    log_date DATE NOT NULL,
    driving_hours DECIMAL(5,2) DEFAULT 0,
    on_duty_hours DECIMAL(5,2) DEFAULT 0,
    off_duty_hours DECIMAL(5,2) DEFAULT 0,
    sleeper_hours DECIMAL(5,2) DEFAULT 0,
    violations TEXT,
    status VARCHAR(50) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Analytics
CREATE TABLE analytics_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    service_name VARCHAR(100),
    data JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notifications
CREATE TABLE notification_templates (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    subject VARCHAR(255),
    body TEXT NOT NULL,
    type VARCHAR(50) DEFAULT 'EMAIL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    template_id BIGINT REFERENCES notification_templates(id),
    channel VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    content TEXT,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_vehicles_driver ON vehicles(driver_id);
CREATE INDEX idx_vehicles_status ON vehicles(status);
CREATE INDEX idx_routes_vehicle ON routes(vehicle_id);
CREATE INDEX idx_dispatch_vehicle ON dispatch_jobs(vehicle_id);
CREATE INDEX idx_dispatch_status ON dispatch_jobs(status);
CREATE INDEX idx_tracking_vehicle ON tracking_events(vehicle_id);
CREATE INDEX idx_tracking_timestamp ON tracking_events(timestamp);
CREATE INDEX idx_invoices_customer ON invoices(customer_id);
CREATE INDEX idx_driver_logs_driver ON driver_logs(driver_id);
CREATE INDEX idx_notifications_user ON notifications(user_id);
