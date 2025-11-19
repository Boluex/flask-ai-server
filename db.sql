-- ============================================
-- SUPABASE SCHEMA FOR TECHFIX AI
-- Copy and paste this into Supabase SQL Editor
-- ============================================

-- 1. SESSIONS TABLE (Primary table for user sessions)
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    token VARCHAR(9) UNIQUE NOT NULL,  -- Format: ABCD-EFGH
    email VARCHAR(255) NOT NULL,
    issue TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    plan_type VARCHAR(50) DEFAULT 'basic',  -- 'basic', 'bundle', 'pro'
    transaction_ref VARCHAR(100),  -- Flutterwave transaction reference
    plan JSONB  -- Stores the full repair plan from AI
);

-- Indexes for performance
CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_email ON sessions(email);
CREATE INDEX idx_sessions_active ON sessions(active);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_sessions_created_at ON sessions(created_at);

-- 2. NOTIFICATIONS TABLE (For frontend banner notifications)
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert a sample notification
INSERT INTO notifications (title, message, created_at)
VALUES (
    'Welcome to TechFix AI',
    'Our AI-powered repair system is ready to help you fix your tech issues!',
    NOW()
);

-- 3. ANALYTICS TABLE (For tracking events - needed for dashboard)
CREATE TABLE IF NOT EXISTS analytics (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,  -- 'token_generated', 'ai_request', 'agent_download', 'ai_error', 'human_help_request'
    email VARCHAR(255),
    token VARCHAR(9),
    issue TEXT,
    error TEXT,  -- For AI errors
    metadata JSONB,  -- Additional context
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for analytics queries
CREATE INDEX idx_analytics_event_type ON analytics(event_type);
CREATE INDEX idx_analytics_created_at ON analytics(created_at);
CREATE INDEX idx_analytics_token ON analytics(token);
CREATE INDEX idx_analytics_email ON analytics(email);

-- ============================================
-- ROW LEVEL SECURITY (RLS) - OPTIONAL
-- Disable if you want backend to have full access
-- ============================================

-- For sessions table
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read access for all users" 
ON sessions FOR SELECT 
USING (true);

CREATE POLICY "Enable insert for authenticated users" 
ON sessions FOR INSERT 
WITH CHECK (true);

CREATE POLICY "Enable update for authenticated users" 
ON sessions FOR UPDATE 
USING (true);

-- For notifications table
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read access for all users" 
ON notifications FOR SELECT 
USING (true);

-- For analytics table
ALTER TABLE analytics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable insert for authenticated users" 
ON analytics FOR INSERT 
WITH CHECK (true);

CREATE POLICY "Enable read access for all users" 
ON analytics FOR SELECT 
USING (true);

-- ============================================
-- CLEANUP FUNCTION (Auto-delete old sessions)
-- ============================================

-- Function to delete inactive sessions older than 7 days
CREATE OR REPLACE FUNCTION cleanup_old_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM sessions 
    WHERE active = FALSE 
    AND created_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Optional: Create a cron job to run cleanup daily
-- (Requires pg_cron extension - enable in Supabase dashboard)
-- SELECT cron.schedule('cleanup-sessions', '0 2 * * *', 'SELECT cleanup_old_sessions()');

-- ============================================
-- SAMPLE DATA (For testing)
-- ============================================

-- Sample session
INSERT INTO sessions (token, email, issue, expires_at, active, plan_type)
VALUES (
    'TEST-1234',
    'test@example.com',
    'Windows update error',
    NOW() + INTERVAL '24 hours',
    TRUE,
    'basic'
);

-- Sample analytics events
INSERT INTO analytics (event_type, email, token, issue)
VALUES 
    ('token_generated', 'test@example.com', 'TEST-1234', 'Windows update error'),
    ('ai_request', 'test@example.com', 'TEST-1234', 'Windows update error'),
    ('agent_download', 'test@example.com', NULL, NULL);

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- Check if tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('sessions', 'notifications', 'analytics');

-- Check sample data
SELECT COUNT(*) as total_sessions FROM sessions;
SELECT COUNT(*) as total_notifications FROM notifications;
SELECT COUNT(*) as total_analytics FROM analytics;

-- Check indexes
SELECT indexname, tablename 
FROM pg_indexes 
WHERE schemaname = 'public' 
AND tablename IN ('sessions', 'notifications', 'analytics');
