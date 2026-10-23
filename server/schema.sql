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

-- Each sync's step total for today, with the time it arrived. Only used to tell
-- whether someone has been sitting still (the stand-up reminder). Kept for 2 days.
CREATE TABLE IF NOT EXISTS step_samples (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  total INTEGER NOT NULL,
  at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_samples_user ON step_samples(user_id, date, at);

-- EXP: the in-app currency. Every gain (+) and spend (-) is one row, so the balance
-- is always the sum and nothing is ever lost or invented.
CREATE TABLE IF NOT EXISTS exp_ledger (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL CHECK (amount <> 0),
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exp_user ON exp_ledger(user_id);

-- Avatar items someone has bought (free items are owned by everyone, so not stored).
CREATE TABLE IF NOT EXISTS avatar_owned (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  item_key TEXT NOT NULL,
  bought_at TEXT NOT NULL,
  PRIMARY KEY (user_id, item_key)
);

-- What each person is wearing, one item per slot (missing slots use the defaults).
CREATE TABLE IF NOT EXISTS avatar_equipped (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  slot TEXT NOT NULL,
  item_key TEXT NOT NULL,
  PRIMARY KEY (user_id, slot)
);

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
-- (moods already has UNIQUE (user_id, date), which works as an index: no second copy needed)
DROP INDEX IF EXISTS idx_moods_user_date;

-- Mini challenges: one row per attempt. status: active, done or quit.
-- base_steps is today's step total when a walk started (walks finish on new steps).
CREATE TABLE IF NOT EXISTS mini_runs (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','done','quit')),
  base_steps INTEGER NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL,
  finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_mini_user ON mini_runs(user_id, date, status);

-- Sign-ups waiting for their email code. The email address is only kept here until the
-- account is made (then only a fingerprint of it stays on the user, never the address).
CREATE TABLE IF NOT EXISTS pending_signups (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL,
  email_hash TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  details TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  sends INTEGER NOT NULL DEFAULT 1,
  sent_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pending_email ON pending_signups(email_hash);

-- Email codes for logged-in people adding a recovery email ('link') and for
-- "Forgot your PIN?" ('reset'). Rows are deleted once used; addresses aren't kept.
CREATE TABLE IF NOT EXISTS email_codes (
  id INTEGER PRIMARY KEY,
  purpose TEXT NOT NULL CHECK (purpose IN ('link','reset')),
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  email_hash TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  sends INTEGER NOT NULL DEFAULT 1,
  sent_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- Emails of deleted accounts (as fingerprints) that may not sign up or be added again.
CREATE TABLE IF NOT EXISTS blocked_emails (
  email_hash TEXT PRIMARY KEY,
  blocked_at TEXT NOT NULL
);

-- Daily login rewards: one claim per person per Dubai day. `day` is the place on that tier's
-- 28-day reward calendar; `cycle` counts how many times they have started the calendar.
CREATE TABLE IF NOT EXISTS daily_rewards (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  cycle INTEGER NOT NULL,
  day INTEGER NOT NULL,
  tier TEXT NOT NULL,
  reward TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, date)
);
