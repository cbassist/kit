-- 01 Lab Schema — replaces JSON file persistence
-- Tables mirror the existing JSON structures for drop-in migration

CREATE TABLE IF NOT EXISTS episodic (
    id SERIAL PRIMARY KEY,
    cycle_id TEXT NOT NULL UNIQUE,
    goal TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,  -- 'success' | 'failure' | 'partial'
    score_before DOUBLE PRECISION,
    score_after DOUBLE PRECISION,
    score_delta DOUBLE PRECISION,
    kept BOOLEAN,  -- true=kept, false=reverted, null=no git discipline
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS heuristics (
    id SERIAL PRIMARY KEY,
    metric TEXT NOT NULL,
    action TEXT NOT NULL,
    score_before DOUBLE PRECISION NOT NULL,
    score_after DOUBLE PRECISION NOT NULL,
    score_delta DOUBLE PRECISION NOT NULL,
    template_id TEXT,
    files_changed TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    context TEXT DEFAULT '',
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS state_checkpoints (
    id SERIAL PRIMARY KEY,
    goal TEXT NOT NULL,
    state_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued | running | done | failed
    priority INTEGER DEFAULT 50,
    source TEXT DEFAULT 'cli',  -- cli | telegram | slack | web | cron
    result JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Index for goal queue polling
CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_episodic_goal ON episodic(goal);
CREATE INDEX IF NOT EXISTS idx_heuristics_metric ON heuristics(metric);
