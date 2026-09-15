CREATE TABLE local_directory_grants (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    path TEXT NOT NULL,
    file_extensions JSON NOT NULL,
    created_at TIMESTAMP NOT NULL
);
CREATE INDEX idx_local_directory_grants_user ON local_directory_grants (user_id);
