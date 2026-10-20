-- StrideBoard database tables.
-- Safe to run many times: it only creates what is missing and never deletes data.

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  pin_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('student','teacher','admin')),
  department TEXT,                 -- teachers: subject (Science, Math, PE...). students: class (Grade 10A...)
  age_band TEXT NOT NULL DEFAULT 'adult_18_39'
    CHECK (age_band IN ('under_13','teen_13_17','adult_18_39','adult_40_59','senior_60_plus')),
  api_token TEXT UNIQUE NOT NULL,
  daily_goal INTEGER NOT NULL,
  goal_is_custom INTEGER NOT NULL DEFAULT 0 CHECK (goal_is_custom IN (0, 1)),
  created_at TEXT NOT NULL,        -- ISO time in Dubai, e.g. 2026-10-14T21:30:00+04:00
  avatar TEXT,                     -- key from config.AVATARS (NULL = show the first letter)
  avatar_color TEXT                -- key from config.AVATAR_COLORS
);

CREATE TABLE IF NOT EXISTS steps (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,              -- YYYY-MM-DD, Dubai date
  steps INTEGER NOT NULL CHECK (steps >= 0 AND steps <= 100000),
  source TEXT NOT NULL CHECK (source IN ('manual','ios_shortcut','android_app','other')),
  updated_at TEXT NOT NULL,
  UNIQUE (user_id, date)           -- one row per user per day; new uploads overwrite
);

CREATE TABLE IF NOT EXISTS moods (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  mood INTEGER NOT NULL CHECK (mood BETWEEN 1 AND 5),
  UNIQUE (user_id, date)
);

CREATE TABLE IF NOT EXISTS activities (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('walk','gym','sport','yoga','stretch','other')),
  minutes INTEGER NOT NULL CHECK (minutes BETWEEN 1 AND 600)
);

-- Exercises the user types in (one row per set). Personal badges only: never used
-- for leaderboards, tiers or challenges. Planks are stored in seconds.
CREATE TABLE IF NOT EXISTS exercises (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('pushups','squats','planks','jumping_jacks')),
  amount INTEGER NOT NULL CHECK (amount BETWEEN 1 AND 5000),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exercises_user ON exercises(user_id, type, date);

CREATE TABLE IF NOT EXISTS water (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  glasses INTEGER NOT NULL DEFAULT 0 CHECK (glasses >= 0),
  UNIQUE (user_id, date)
);

CREATE TABLE IF NOT EXISTS challenges (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  kind TEXT NOT NULL CHECK (kind IN ('department','school_distance')),
  target_steps INTEGER,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS badges (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  badge_key TEXT NOT NULL,
  earned_on TEXT NOT NULL,
  UNIQUE (user_id, badge_key)
);

-- Small key/value notes for the app itself (e.g. the week goals were last updated).
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- Indexes make the weekly leaderboard queries fast.
CREATE INDEX IF NOT EXISTS idx_steps_date ON steps(date);
CREATE INDEX IF NOT EXISTS idx_moods_user_date ON moods(user_id, date);
