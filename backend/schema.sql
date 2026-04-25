-- Target persistence shape for the privacy-first swing architecture.
-- The current prototype uses backend/storage.py as an in-memory repository with
-- the same separation so a real database can be introduced without changing API
-- payloads.

CREATE TABLE IF NOT EXISTS swings (
  swing_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('on_device', 'server')),
  video_metadata_json JSON NOT NULL,
  raw_video_uploaded BOOLEAN NOT NULL DEFAULT FALSE,
  user_consented_to_upload BOOLEAN NOT NULL DEFAULT FALSE,
  video_url TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_results (
  swing_id TEXT PRIMARY KEY REFERENCES swings(swing_id),
  phases_json JSON NOT NULL,
  metrics_json JSON NOT NULL,
  pose_json JSON NOT NULL,
  estimates_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
