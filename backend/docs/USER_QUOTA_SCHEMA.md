# User Quota and Usage Tracking Database Schema

**Version**: 1.0
**Created**: 2025-10-29
**Purpose**: Cost control, abuse prevention, and fair usage policies

---

## Overview

This document defines the database schema for tracking user quotas, token usage, and enforcing usage limits to prevent abuse and control costs.

---

## Database Tables

### 1. `users` Table Extensions

Add these columns to the existing `users` table (or create if it doesn't exist):

```sql
CREATE TABLE IF NOT EXISTS users (
    -- Core identity
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,

    -- Authentication
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,

    -- User tier and limits
    tier VARCHAR(50) DEFAULT 'free',  -- free, basic, professional, enterprise
    tier_updated_at TIMESTAMP DEFAULT NOW(),

    -- Status
    is_blocked BOOLEAN DEFAULT FALSE,
    blocked_reason TEXT,
    blocked_until TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,

    -- Admin overrides
    custom_quotas JSONB,  -- Allow admin to set custom limits
    is_whitelisted BOOLEAN DEFAULT FALSE,  -- Bypass all limits

    -- Indexes
    INDEX idx_users_email (email),
    INDEX idx_users_tier (tier),
    INDEX idx_users_is_active (is_active)
);
```

---

### 2. `user_quotas` Table

Track current usage against limits for each user.

```sql
CREATE TABLE user_quotas (
    quota_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Daily usage counters
    guides_created_today INTEGER DEFAULT 0,
    steps_completed_today INTEGER DEFAULT 0,
    adaptations_requested_today INTEGER DEFAULT 0,

    -- Token usage counters
    tokens_used_today INTEGER DEFAULT 0,
    tokens_used_this_month INTEGER DEFAULT 0,
    total_tokens_lifetime BIGINT DEFAULT 0,

    -- Request counters
    requests_this_minute INTEGER DEFAULT 0,
    requests_this_hour INTEGER DEFAULT 0,

    -- Reset timestamps
    daily_reset_at TIMESTAMP DEFAULT NOW(),
    monthly_reset_at TIMESTAMP DEFAULT NOW(),
    minute_reset_at TIMESTAMP DEFAULT NOW(),
    hour_reset_at TIMESTAMP DEFAULT NOW(),

    -- Cost tracking
    estimated_cost_today DECIMAL(10, 4) DEFAULT 0.0,
    estimated_cost_this_month DECIMAL(10, 4) DEFAULT 0.0,
    total_cost_lifetime DECIMAL(12, 4) DEFAULT 0.0,

    -- Metadata
    last_updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(user_id),

    -- Indexes
    INDEX idx_user_quotas_user_id (user_id),
    INDEX idx_user_quotas_daily_reset (daily_reset_at),
    INDEX idx_user_quotas_monthly_reset (monthly_reset_at)
);
```

---

### 3. `usage_events` Table

Detailed log of all usage events for analytics and billing.

```sql
CREATE TABLE usage_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Event details
    event_type VARCHAR(50) NOT NULL,  -- 'guide_generation', 'step_completion', 'adaptation'
    event_timestamp TIMESTAMP DEFAULT NOW(),

    -- Resource identifiers
    guide_id UUID,
    session_id UUID,
    step_identifier VARCHAR(20),

    -- Token usage
    tokens_input INTEGER,
    tokens_output INTEGER,
    tokens_total INTEGER,

    -- Cost
    estimated_cost DECIMAL(10, 6),

    -- Request metadata
    request_duration_ms INTEGER,
    status VARCHAR(20),  -- 'success', 'failed', 'rate_limited', 'quota_exceeded'
    error_message TEXT,

    -- Client information
    ip_address INET,
    user_agent TEXT,
    client_type VARCHAR(20),  -- 'web', 'mobile', 'api'

    -- Indexes
    INDEX idx_usage_events_user_id (user_id),
    INDEX idx_usage_events_timestamp (event_timestamp),
    INDEX idx_usage_events_event_type (event_type),
    INDEX idx_usage_events_status (status)
);

-- Partition by month for better performance
CREATE TABLE usage_events_y2025m10 PARTITION OF usage_events
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
```

---

### 4. `rate_limit_violations` Table

Track rate limit violations and abuse patterns.

```sql
CREATE TABLE rate_limit_violations (
    violation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Violation details
    violation_type VARCHAR(50) NOT NULL,  -- 'rate_limit', 'quota_exceeded', 'abuse_detected'
    violation_timestamp TIMESTAMP DEFAULT NOW(),

    -- Context
    endpoint VARCHAR(255),
    request_count INTEGER,
    time_window_seconds INTEGER,

    -- Action taken
    action_taken VARCHAR(50),  -- 'throttled', 'blocked', 'warned', 'none'
    throttle_duration_seconds INTEGER,

    -- Metadata
    ip_address INET,
    user_agent TEXT,
    details JSONB,

    -- Indexes
    INDEX idx_violations_user_id (user_id),
    INDEX idx_violations_timestamp (violation_timestamp),
    INDEX idx_violations_type (violation_type)
);
```

---

### 5. `quota_warnings` Table

Track when warnings were sent to users.

```sql
CREATE TABLE quota_warnings (
    warning_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Warning details
    warning_type VARCHAR(50) NOT NULL,  -- 'approaching_limit', 'quota_exceeded', 'cost_alert'
    warning_level VARCHAR(20) NOT NULL,  -- 'info', 'warning', 'critical'
    warning_timestamp TIMESTAMP DEFAULT NOW(),

    -- Usage context
    current_usage INTEGER,
    quota_limit INTEGER,
    usage_percentage INTEGER,

    -- Notification status
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_method VARCHAR(50),  -- 'email', 'in_app', 'both'
    notification_sent_at TIMESTAMP,

    -- Message
    message TEXT,

    -- Indexes
    INDEX idx_warnings_user_id (user_id),
    INDEX idx_warnings_timestamp (warning_timestamp),
    INDEX idx_warnings_type (warning_type)
);
```

---

## Database Triggers

### Auto-update `updated_at` timestamp

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_quotas_last_updated
    BEFORE UPDATE ON user_quotas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### Auto-reset daily quotas

```sql
CREATE OR REPLACE FUNCTION reset_daily_quotas_if_needed()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if daily reset is needed
    IF NEW.daily_reset_at < NOW() - INTERVAL '1 day' THEN
        NEW.guides_created_today = 0;
        NEW.steps_completed_today = 0;
        NEW.adaptations_requested_today = 0;
        NEW.tokens_used_today = 0;
        NEW.estimated_cost_today = 0.0;
        NEW.daily_reset_at = NOW();
    END IF;

    -- Check if monthly reset is needed
    IF NEW.monthly_reset_at < NOW() - INTERVAL '1 month' THEN
        NEW.tokens_used_this_month = 0;
        NEW.estimated_cost_this_month = 0.0;
        NEW.monthly_reset_at = NOW();
    END IF;

    -- Reset minute counter
    IF NEW.minute_reset_at < NOW() - INTERVAL '1 minute' THEN
        NEW.requests_this_minute = 0;
        NEW.minute_reset_at = NOW();
    END IF;

    -- Reset hour counter
    IF NEW.hour_reset_at < NOW() - INTERVAL '1 hour' THEN
        NEW.requests_this_hour = 0;
        NEW.hour_reset_at = NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_reset_quotas
    BEFORE UPDATE ON user_quotas
    FOR EACH ROW
    EXECUTE FUNCTION reset_daily_quotas_if_needed();
```

---

## Views

### User Usage Summary View

```sql
CREATE OR REPLACE VIEW v_user_usage_summary AS
SELECT
    u.user_id,
    u.email,
    u.username,
    u.tier,
    u.is_active,
    u.is_blocked,

    -- Current usage
    uq.guides_created_today,
    uq.steps_completed_today,
    uq.tokens_used_today,
    uq.tokens_used_this_month,
    uq.total_tokens_lifetime,

    -- Costs
    uq.estimated_cost_today,
    uq.estimated_cost_this_month,
    uq.total_cost_lifetime,

    -- Rate limiting
    uq.requests_this_minute,
    uq.requests_this_hour,

    -- Reset times
    uq.daily_reset_at,
    uq.monthly_reset_at,

    -- Last activity
    u.last_login_at,
    uq.last_updated_at

FROM users u
LEFT JOIN user_quotas uq ON u.user_id = uq.user_id;
```

---

## Indexes for Performance

```sql
-- Composite indexes for common queries
CREATE INDEX idx_usage_events_user_date ON usage_events(user_id, event_timestamp DESC);
CREATE INDEX idx_usage_events_cost ON usage_events(estimated_cost DESC) WHERE estimated_cost > 0;
CREATE INDEX idx_violations_user_recent ON rate_limit_violations(user_id, violation_timestamp DESC);

-- Partial indexes for active users
CREATE INDEX idx_active_users ON users(user_id) WHERE is_active = TRUE AND is_blocked = FALSE;
```

---

## Migration Script

```sql
-- Migration: Add user quota system
-- Version: 003_add_user_quotas
-- Date: 2025-10-29

BEGIN;

-- 1. Create/extend users table
-- (Add columns if table exists, create if not)

-- 2. Create user_quotas table
-- (As defined above)

-- 3. Create usage_events table
-- (As defined above)

-- 4. Create rate_limit_violations table
-- (As defined above)

-- 5. Create quota_warnings table
-- (As defined above)

-- 6. Create triggers
-- (As defined above)

-- 7. Create views
-- (As defined above)

-- 8. Create indexes
-- (As defined above)

-- 9. Initialize quotas for existing users
INSERT INTO user_quotas (user_id)
SELECT user_id FROM users
ON CONFLICT (user_id) DO NOTHING;

COMMIT;
```

---

## Sample Queries

### Check user's current usage

```sql
SELECT * FROM v_user_usage_summary
WHERE user_id = 'USER_UUID_HERE';
```

### Get users approaching their limits

```sql
SELECT
    u.user_id,
    u.email,
    u.tier,
    uq.tokens_used_today,
    (uq.tokens_used_today::FLOAT /
     CASE u.tier
       WHEN 'free' THEN 10000
       WHEN 'basic' THEN 50000
       WHEN 'professional' THEN 200000
       ELSE 1000000
     END * 100) as usage_percentage
FROM users u
JOIN user_quotas uq ON u.user_id = uq.user_id
WHERE uq.tokens_used_today::FLOAT /
      CASE u.tier
        WHEN 'free' THEN 10000
        WHEN 'basic' THEN 50000
        WHEN 'professional' THEN 200000
        ELSE 1000000
      END > 0.8;
```

### Get cost summary by user tier

```sql
SELECT
    u.tier,
    COUNT(DISTINCT u.user_id) as user_count,
    SUM(uq.tokens_used_this_month) as total_tokens,
    SUM(uq.estimated_cost_this_month) as total_cost,
    AVG(uq.estimated_cost_this_month) as avg_cost_per_user
FROM users u
JOIN user_quotas uq ON u.user_id = uq.user_id
WHERE u.is_active = TRUE
GROUP BY u.tier
ORDER BY total_cost DESC;
```

---

## Cleanup and Maintenance

### Archive old usage events

```sql
-- Archive events older than 90 days to separate table
CREATE TABLE usage_events_archive AS
SELECT * FROM usage_events
WHERE event_timestamp < NOW() - INTERVAL '90 days';

DELETE FROM usage_events
WHERE event_timestamp < NOW() - INTERVAL '90 days';
```

### Clean up old violations

```sql
-- Delete violations older than 180 days
DELETE FROM rate_limit_violations
WHERE violation_timestamp < NOW() - INTERVAL '180 days';
```

---

## Next Steps

1. Create Alembic migration: `003_add_user_quota_system.py`
2. Implement quota enforcement middleware
3. Create admin UI for quota management
4. Add usage dashboard to frontend
5. Set up automated alerts for high-cost users
