CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'USER',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    content_type VARCHAR(100),
    file_path VARCHAR(1000),
    file_size BIGINT,
    owner_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version_number INT NOT NULL DEFAULT 1,
    checksum VARCHAR(64),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE document_versions (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id),
    version_number INT NOT NULL,
    file_path VARCHAR(1000),
    file_size BIGINT,
    checksum VARCHAR(64),
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    change_summary TEXT
);

CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id),
    user_id BIGINT NOT NULL REFERENCES users(id),
    permission_type VARCHAR(50) NOT NULL,
    granted_by BIGINT REFERENCES users(id),
    granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    UNIQUE(document_id, user_id, permission_type)
);

CREATE TABLE tags (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE document_tags (
    document_id BIGINT NOT NULL REFERENCES documents(id),
    tag_id BIGINT NOT NULL REFERENCES tags(id),
    PRIMARY KEY (document_id, tag_id)
);

CREATE INDEX idx_documents_owner ON documents(owner_id);
CREATE INDEX idx_documents_name ON documents(name);
CREATE INDEX idx_document_versions_doc ON document_versions(document_id);
CREATE INDEX idx_permissions_document ON permissions(document_id);
CREATE INDEX idx_permissions_user ON permissions(user_id);
