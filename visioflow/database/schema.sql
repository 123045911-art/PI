-- VisioFlow backend contract v1 (PostgreSQL 15+)
-- Greenfield schema: use migrations when upgrading an existing installation.
-- Canonical rules:
--   * all instants are UTC TIMESTAMPTZ;
--   * world coordinates are DOUBLE PRECISION meters in world_ground;
--   * image coordinates are DOUBLE PRECISION pixels and never replace world coordinates;
--   * public IDs (external_id) are stable strings shared by vision and frontend;
--   * tracker IDs are temporary and unique only inside a tracking session;
--   * video and images are not persisted by this schema.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id VARCHAR(80) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  timezone VARCHAR(80) NOT NULL DEFAULT 'UTC',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (external_id ~ '^[a-z0-9][a-z0-9_-]{0,79}$')
);

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(80) NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name VARCHAR(120) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS site_memberships (
  site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(30) NOT NULL CHECK (role IN ('viewer', 'operator', 'admin')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (site_id, user_id)
);

CREATE TABLE IF NOT EXISTS cameras (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  external_id VARCHAR(80) NOT NULL,
  name VARCHAR(120) NOT NULL,
  sensor_mode VARCHAR(20) NOT NULL CHECK (sensor_mode IN ('rgbd', 'stereo', 'monocular')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (site_id, external_id),
  CHECK (external_id ~ '^[a-z0-9][a-z0-9_-]{0,79}$')
);

CREATE TABLE IF NOT EXISTS camera_calibrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
  version INTEGER NOT NULL CHECK (version > 0),
  image_width INTEGER NOT NULL CHECK (image_width > 0),
  image_height INTEGER NOT NULL CHECK (image_height > 0),
  camera_matrix JSONB NOT NULL,
  distortion_coefficients JSONB NOT NULL DEFAULT '[]'::jsonb,
  rotation_matrix JSONB,
  translation_vector_meters JSONB,
  image_to_ground_homography JSONB,
  ground_to_image_homography JSONB,
  camera_height_meters DOUBLE PRECISION CHECK (camera_height_meters > 0),
  reprojection_error_px DOUBLE PRECISION CHECK (reprojection_error_px >= 0),
  validation_error_meters DOUBLE PRECISION CHECK (validation_error_meters >= 0),
  valid BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (camera_id, version)
);

CREATE TABLE IF NOT EXISTS scenes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
  version INTEGER NOT NULL CHECK (version > 0),
  calibration_version INTEGER NOT NULL CHECK (calibration_version > 0),
  coordinate_system JSONB NOT NULL,
  field_of_view_polygon JSONB NOT NULL DEFAULT '[]'::jsonb,
  fixed_point_resolution_meters DOUBLE PRECISION CHECK (fixed_point_resolution_meters > 0),
  created_at TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (camera_id, version),
  FOREIGN KEY (camera_id, calibration_version)
    REFERENCES camera_calibrations(camera_id, version) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS areas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  external_id VARCHAR(80) NOT NULL,
  name VARCHAR(120) NOT NULL,
  kind VARCHAR(30) NOT NULL CHECK (kind IN ('access', 'interaction', 'transit', 'service')),
  coordinate_system VARCHAR(40) NOT NULL DEFAULT 'world_ground' CHECK (coordinate_system = 'world_ground'),
  polygon JSONB NOT NULL,
  x_meters DOUBLE PRECISION NOT NULL,
  y_meters DOUBLE PRECISION NOT NULL,
  width_meters DOUBLE PRECISION NOT NULL CHECK (width_meters > 0),
  height_meters DOUBLE PRECISION NOT NULL CHECK (height_meters > 0),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (site_id, external_id),
  CHECK (external_id ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),
  CHECK (jsonb_typeof(polygon) = 'array')
);

CREATE TABLE IF NOT EXISTS scene_areas (
  scene_id UUID NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  area_id UUID NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
  PRIMARY KEY (scene_id, area_id)
);

CREATE TABLE IF NOT EXISTS static_objects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scene_id UUID NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  external_id VARCHAR(100) NOT NULL,
  name VARCHAR(120) NOT NULL,
  object_type VARCHAR(30) NOT NULL CHECK (object_type IN ('wall', 'table', 'shelf', 'rack', 'display', 'checkout', 'bench', 'column', 'other')),
  footprint JSONB NOT NULL,
  center JSONB,
  width_meters DOUBLE PRECISION CHECK (width_meters >= 0),
  depth_meters DOUBLE PRECISION CHECK (depth_meters >= 0),
  height_meters DOUBLE PRECISION CHECK (height_meters >= 0),
  depth_method VARCHAR(30) NOT NULL CHECK (depth_method IN ('rgbd', 'stereo', 'ground_plane', 'manual')),
  approximate BOOLEAN NOT NULL DEFAULT FALSE,
  confidence DOUBLE PRECISION CHECK (confidence BETWEEN 0 AND 1),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (scene_id, external_id),
  CHECK (jsonb_typeof(footprint) = 'array')
);

CREATE TABLE IF NOT EXISTS tracking_sessions (
  id UUID PRIMARY KEY,
  camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE RESTRICT,
  started_at TIMESTAMPTZ NOT NULL,
  ended_at TIMESTAMPTZ,
  detector VARCHAR(80),
  tracker VARCHAR(80),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (id, camera_id),
  CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE IF NOT EXISTS ingestion_batches (
  id UUID PRIMARY KEY,
  camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE RESTRICT,
  tracking_session_id UUID NOT NULL REFERENCES tracking_sessions(id) ON DELETE RESTRICT,
  payload_type VARCHAR(30) NOT NULL CHECK (payload_type IN ('track_points', 'area_events')),
  first_captured_at TIMESTAMPTZ NOT NULL,
  last_captured_at TIMESTAMPTZ NOT NULL,
  item_count INTEGER NOT NULL CHECK (item_count >= 0),
  accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
  rejected_count INTEGER NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
  received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (tracking_session_id, camera_id)
    REFERENCES tracking_sessions(id, camera_id) ON DELETE RESTRICT,
  CHECK (last_captured_at >= first_captured_at),
  CHECK (accepted_count + rejected_count <= item_count)
);

CREATE TABLE IF NOT EXISTS track_points (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE RESTRICT,
  tracking_session_id UUID NOT NULL REFERENCES tracking_sessions(id) ON DELETE RESTRICT,
  batch_id UUID REFERENCES ingestion_batches(id) ON DELETE SET NULL,
  frame_id BIGINT NOT NULL CHECK (frame_id >= 0),
  track_id BIGINT NOT NULL CHECK (track_id >= 0),
  captured_at TIMESTAMPTZ NOT NULL,
  image_u DOUBLE PRECISION,
  image_v DOUBLE PRECISION,
  x_meters DOUBLE PRECISION,
  y_meters DOUBLE PRECISION,
  z_meters DOUBLE PRECISION,
  confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  position_valid BOOLEAN NOT NULL,
  area_id UUID REFERENCES areas(id) ON DELETE SET NULL,
  calibration_version INTEGER NOT NULL CHECK (calibration_version >= 0),
  scene_version INTEGER NOT NULL CHECK (scene_version >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (camera_id, tracking_session_id, frame_id, track_id),
  FOREIGN KEY (tracking_session_id, camera_id)
    REFERENCES tracking_sessions(id, camera_id) ON DELETE RESTRICT,
  CHECK (
    (position_valid AND x_meters IS NOT NULL AND y_meters IS NOT NULL AND z_meters IS NOT NULL AND calibration_version > 0)
    OR
    (NOT position_valid)
  )
);

CREATE TABLE IF NOT EXISTS area_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  external_event_id UUID NOT NULL UNIQUE,
  camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE RESTRICT,
  tracking_session_id UUID NOT NULL REFERENCES tracking_sessions(id) ON DELETE RESTRICT,
  batch_id UUID REFERENCES ingestion_batches(id) ON DELETE SET NULL,
  area_id UUID NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
  track_id BIGINT NOT NULL CHECK (track_id >= 0),
  event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('enter', 'exit')),
  captured_at TIMESTAMPTZ NOT NULL,
  dwell_seconds DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (dwell_seconds >= 0),
  calibration_version INTEGER NOT NULL CHECK (calibration_version > 0),
  scene_version INTEGER NOT NULL CHECK (scene_version > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (tracking_session_id, camera_id)
    REFERENCES tracking_sessions(id, camera_id) ON DELETE RESTRICT,
  CHECK ((event_type = 'enter' AND dwell_seconds = 0) OR event_type = 'exit')
);

-- Server-derived snapshot. Producers upload points/events; they do not author this table.
CREATE TABLE IF NOT EXISTS area_state (
  camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
  area_id UUID NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
  people_count INTEGER NOT NULL DEFAULT 0 CHECK (people_count >= 0),
  last_frame_id BIGINT CHECK (last_frame_id >= 0),
  observed_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (camera_id, area_id)
);

CREATE TABLE IF NOT EXISTS area_hourly_metrics (
  site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  area_id UUID NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
  bucket_start TIMESTAMPTZ NOT NULL,
  unique_tracks INTEGER NOT NULL DEFAULT 0 CHECK (unique_tracks >= 0),
  visits INTEGER NOT NULL DEFAULT 0 CHECK (visits >= 0),
  median_dwell_seconds DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (median_dwell_seconds >= 0),
  stopped_visits INTEGER NOT NULL DEFAULT 0 CHECK (stopped_visits >= 0),
  median_stopped_seconds DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (median_stopped_seconds >= 0),
  peak_concurrent INTEGER NOT NULL DEFAULT 0 CHECK (peak_concurrent >= 0),
  computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (site_id, area_id, bucket_start)
);

CREATE TABLE IF NOT EXISTS alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  area_id UUID NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
  type VARCHAR(30) NOT NULL CHECK (type IN ('crowding', 'low_flow', 'unusual_dwell', 'blocked_access', 'manual')),
  reason VARCHAR(300) NOT NULL CHECK (char_length(reason) BETWEEN 10 AND 300),
  status VARCHAR(20) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'watching', 'triggered', 'acknowledged', 'resolved')),
  threshold_people INTEGER CHECK (threshold_people IS NULL OR threshold_people BETWEEN 1 AND 120),
  schedule_mode VARCHAR(20) NOT NULL CHECK (schedule_mode IN ('immediate', 'all_days', 'weekly', 'date')),
  schedule_day SMALLINT CHECK (schedule_day IS NULL OR schedule_day BETWEEN 0 AND 6),
  schedule_date DATE,
  people_count_snapshot INTEGER NOT NULL DEFAULT 0 CHECK (people_count_snapshot >= 0),
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (
    (schedule_mode = 'weekly' AND schedule_day IS NOT NULL AND schedule_date IS NULL)
    OR (schedule_mode = 'date' AND schedule_date IS NOT NULL AND schedule_day IS NULL)
    OR (schedule_mode IN ('immediate', 'all_days') AND schedule_day IS NULL AND schedule_date IS NULL)
  ),
  CHECK (
    (type IN ('crowding', 'low_flow') AND threshold_people IS NOT NULL AND schedule_mode IN ('all_days', 'weekly', 'date'))
    OR (type IN ('unusual_dwell', 'blocked_access', 'manual') AND threshold_people IS NULL AND schedule_mode = 'immediate')
  )
);

CREATE INDEX IF NOT EXISTS idx_track_points_camera_time ON track_points(camera_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_track_points_area_time ON track_points(area_id, captured_at DESC) WHERE area_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_track_points_session_track_time ON track_points(tracking_session_id, track_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_track_points_time_brin ON track_points USING BRIN(captured_at);
CREATE INDEX IF NOT EXISTS idx_area_events_area_time ON area_events(area_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_area_events_session_track_time ON area_events(tracking_session_id, track_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_area_events_time_brin ON area_events USING BRIN(captured_at);
CREATE INDEX IF NOT EXISTS idx_hourly_metrics_site_time ON area_hourly_metrics(site_id, bucket_start DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_site_area_status ON alerts(site_id, area_id, status);
CREATE INDEX IF NOT EXISTS idx_alerts_site_type ON alerts(site_id, type);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);

COMMENT ON COLUMN areas.external_id IS 'Stable frontend/vision ID, for example central or access.';
COMMENT ON COLUMN tracking_sessions.id IS 'Producer-generated UUID; tracker IDs may be reused in another session.';
COMMENT ON COLUMN track_points.track_id IS 'Temporary tracker identifier, never a real-world identity.';
COMMENT ON COLUMN track_points.x_meters IS 'World-ground X in meters; never an image pixel coordinate.';
COMMENT ON TABLE area_state IS 'Current state derived by the server from accepted observations.';
COMMENT ON TABLE alerts IS 'Unified frontend alert resource; API names map to snake_case columns.';
COMMENT ON COLUMN alerts.schedule_day IS 'Frontend scheduleDay: 0=Monday through 6=Sunday.';
