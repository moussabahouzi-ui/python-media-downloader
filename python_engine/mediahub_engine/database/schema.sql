-- MediaHub persistence schema.
-- Phase 3: download_tasks. Phase 4: media_items, history, favorites,
-- collections, collection_items.

-- ---------------------------------------------------------------------------
-- Phase 3: download tasks (mirrors DownloadTask)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS download_tasks (
    task_id      TEXT    PRIMARY KEY,
    url          TEXT    NOT NULL,
    priority     INTEGER NOT NULL,
    state        TEXT    NOT NULL,
    dest_dir     TEXT    NOT NULL DEFAULT '',
    options      TEXT    NOT NULL DEFAULT '{}',
    created_at   REAL    NOT NULL,
    started_at   REAL,
    finished_at  REAL,
    bytes_done   INTEGER NOT NULL DEFAULT 0,
    total_bytes  INTEGER,
    error        TEXT,
    last_error   TEXT,
    output_path  TEXT,
    output_paths TEXT    NOT NULL DEFAULT '[]',
    provider     TEXT,
    engine       TEXT,
    metadata     TEXT,
    retries      INTEGER NOT NULL DEFAULT 0,
    retry_after  REAL
);

CREATE INDEX IF NOT EXISTS idx_download_tasks_state ON download_tasks(state);
CREATE INDEX IF NOT EXISTS idx_download_tasks_created ON download_tasks(created_at);

-- ---------------------------------------------------------------------------
-- Phase 4: media items (indexed files from completed downloads)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS media_items (
    item_id      TEXT    PRIMARY KEY,
    path         TEXT    NOT NULL UNIQUE,
    name         TEXT    NOT NULL,
    category     TEXT    NOT NULL,           -- video | audio | image | other
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    mime_type    TEXT,
    duration_ms  INTEGER,                    -- video/audio only
    width        INTEGER,                    -- video/image only
    height       INTEGER,                    -- video/image only
    provider     TEXT,                       -- source platform
    url          TEXT,                       -- source URL
    task_id      TEXT,                       -- originating download task
    title        TEXT,
    uploader     TEXT,
    thumbnail_path TEXT,
    tags         TEXT    NOT NULL DEFAULT '[]',
    favorite     INTEGER NOT NULL DEFAULT 0, -- 0/1 boolean
    recycled     INTEGER NOT NULL DEFAULT 0, -- 0/1: in recycle bin
    created_at   REAL    NOT NULL,
    added_at     REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_media_items_category ON media_items(category);
CREATE INDEX IF NOT EXISTS idx_media_items_favorite ON media_items(favorite);
CREATE INDEX IF NOT EXISTS idx_media_items_recycled ON media_items(recycled);
CREATE INDEX IF NOT EXISTS idx_media_items_added ON media_items(added_at);
CREATE INDEX IF NOT EXISTS idx_media_items_name ON media_items(name);

-- ---------------------------------------------------------------------------
-- Phase 4: download history (append-only log of completed/failed downloads)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS download_history (
    history_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT    NOT NULL,
    url          TEXT    NOT NULL,
    provider     TEXT,
    engine       TEXT,
    state        TEXT    NOT NULL,           -- completed | failed | cancelled
    bytes_done   INTEGER NOT NULL DEFAULT 0,
    output_paths TEXT    NOT NULL DEFAULT '[]',
    error        TEXT,
    metadata     TEXT,
    started_at   REAL,
    finished_at  REAL,
    recorded_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_recorded ON download_history(recorded_at);
CREATE INDEX IF NOT EXISTS idx_history_provider ON download_history(provider);
CREATE INDEX IF NOT EXISTS idx_history_state ON download_history(state);

-- ---------------------------------------------------------------------------
-- Phase 4: collections (user-defined groups of media items)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS collections (
    collection_id TEXT    PRIMARY KEY,
    name          TEXT    NOT NULL,
    description   TEXT    NOT NULL DEFAULT '',
    color         TEXT,                      -- optional hex color
    icon          TEXT,                      -- optional icon name
    item_count    INTEGER NOT NULL DEFAULT 0,
    created_at    REAL    NOT NULL,
    updated_at    REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_collections_updated ON collections(updated_at);

CREATE TABLE IF NOT EXISTS collection_items (
    collection_id TEXT    NOT NULL,
    item_id       TEXT    NOT NULL,
    added_at      REAL    NOT NULL,
    PRIMARY KEY (collection_id, item_id),
    FOREIGN KEY (collection_id) REFERENCES collections(collection_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES media_items(item_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_collection_items_item ON collection_items(item_id);

-- ---------------------------------------------------------------------------
-- Phase 5: playlists (ordered playback queues)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS playlists (
    playlist_id  TEXT    PRIMARY KEY,
    name         TEXT    NOT NULL,
    description  TEXT    NOT NULL DEFAULT '',
    item_count   INTEGER NOT NULL DEFAULT 0,
    shuffle      INTEGER NOT NULL DEFAULT 0,
    repeat_mode  TEXT    NOT NULL DEFAULT 'off',  -- off | all | one
    created_at   REAL    NOT NULL,
    updated_at   REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_playlists_updated ON playlists(updated_at);

CREATE TABLE IF NOT EXISTS playlist_items (
    playlist_id  TEXT    NOT NULL,
    item_id      TEXT    NOT NULL,
    position     INTEGER NOT NULL,
    added_at     REAL    NOT NULL,
    PRIMARY KEY (playlist_id, item_id),
    FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES media_items(item_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_playlist_items_position ON playlist_items(playlist_id, position);

-- ---------------------------------------------------------------------------
-- Phase 6: app settings (key-value)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_settings (
    key          TEXT    PRIMARY KEY,
    value        TEXT    NOT NULL,
    updated_at   REAL    NOT NULL
);

-- ---------------------------------------------------------------------------
-- Phase 6: scheduled downloads
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    schedule_id  TEXT    PRIMARY KEY,
    url          TEXT    NOT NULL,
    schedule_type TEXT   NOT NULL,    -- one_time | interval | daily | weekly
    scheduled_at REAL,                 -- epoch seconds for one_time
    interval_seconds INTEGER,          -- for interval
    hour         INTEGER,              -- for daily (0-23)
    minute       INTEGER,              -- for daily (0-59)
    day_of_week  INTEGER,              -- for weekly (0=Sunday..6=Saturday)
    priority     INTEGER NOT NULL DEFAULT 5,
    options      TEXT    NOT NULL DEFAULT '{}',
    enabled      INTEGER NOT NULL DEFAULT 1,
    last_run_at  REAL,
    next_run_at  REAL,
    run_count    INTEGER NOT NULL DEFAULT 0,
    created_at   REAL    NOT NULL,
    updated_at   REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scheduled_enabled ON scheduled_tasks(enabled);
CREATE INDEX IF NOT EXISTS idx_scheduled_next_run ON scheduled_tasks(next_run_at);

-- ---------------------------------------------------------------------------
-- Phase 6: encrypted provider credentials
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS credentials (
    provider     TEXT    PRIMARY KEY,
    username     TEXT,
    password     TEXT,                 -- encrypted blob (base64)
    cookies_path TEXT,
    session_path TEXT,
    token        TEXT,                 -- encrypted blob (base64)
    extra        TEXT    NOT NULL DEFAULT '{}',
    updated_at   REAL    NOT NULL
);
