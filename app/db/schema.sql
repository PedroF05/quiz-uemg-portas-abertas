PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    mode TEXT NOT NULL,
    answer_mode TEXT NOT NULL,
    theme TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    score INTEGER NOT NULL,
    position INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_match_teams_score ON match_teams(score DESC);

CREATE TABLE IF NOT EXISTS match_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES match_teams(id) ON DELETE CASCADE,
    nickname TEXT NOT NULL,
    answers_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_match_players_match_id ON match_players(match_id);
CREATE INDEX IF NOT EXISTS idx_match_players_team_id ON match_players(team_id);

CREATE TABLE IF NOT EXISTS questions_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_norm TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    n INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(theme_norm, provider, model, n)
);
