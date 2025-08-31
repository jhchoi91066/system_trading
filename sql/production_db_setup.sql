-- Production Database Setup
-- 🚀 Phase 16: Final Production Deployment

-- Create production database with enhanced security
CREATE DATABASE trading_bot_prod 
    WITH 
    ENCODING = 'UTF8' 
    LC_COLLATE = 'en_US.UTF-8' 
    LC_CTYPE = 'en_US.UTF-8' 
    TEMPLATE template0;

-- Create dedicated user for production
CREATE USER tradingbot_prod WITH PASSWORD 'secure_production_password_here';

-- Grant appropriate permissions
GRANT CONNECT ON DATABASE trading_bot_prod TO tradingbot_prod;
GRANT USAGE ON SCHEMA public TO tradingbot_prod;
GRANT CREATE ON SCHEMA public TO tradingbot_prod;

-- Connect to production database
\c trading_bot_prod;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enhanced Trading Data Table with Partitioning
CREATE TABLE IF NOT EXISTS trading_data (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    strategy VARCHAR(50) NOT NULL,
    portfolio_id UUID,
    execution_time_ms INTEGER,
    fees DECIMAL(20, 8),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions for the next year
DO $$
BEGIN
    FOR i IN 0..12 LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS trading_data_%s PARTITION OF trading_data
            FOR VALUES FROM (%L) TO (%L)',
            to_char(CURRENT_DATE + (i || ' months')::interval, 'YYYY_MM'),
            CURRENT_DATE + (i || ' months')::interval,
            CURRENT_DATE + ((i + 1) || ' months')::interval
        );
    END LOOP;
END $$;

-- Enhanced Strategies Table
CREATE TABLE IF NOT EXISTS strategies (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    parameters JSONB NOT NULL,
    performance_metrics JSONB,
    risk_metrics JSONB,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'archived')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    version INTEGER DEFAULT 1
);

-- Portfolio Management Table
CREATE TABLE IF NOT EXISTS portfolios (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    total_value DECIMAL(20, 8) NOT NULL DEFAULT 0,
    available_balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    allocated_balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    risk_limit DECIMAL(5, 4) DEFAULT 0.02,
    max_drawdown DECIMAL(5, 4) DEFAULT 0.10,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance Metrics Table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(20, 8),
    metric_data JSONB,
    tags JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

-- Create daily partitions for performance metrics
DO $$
BEGIN
    FOR i IN 0..90 LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS performance_metrics_%s PARTITION OF performance_metrics
            FOR VALUES FROM (%L) TO (%L)',
            to_char(CURRENT_DATE + (i || ' days')::interval, 'YYYY_MM_DD'),
            CURRENT_DATE + (i || ' days')::interval,
            CURRENT_DATE + ((i + 1) || ' days')::interval
        );
    END LOOP;
END $$;

-- Audit Log Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    event_data JSONB,
    severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical')),
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions for audit logs
DO $$
BEGIN
    FOR i IN 0..12 LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS audit_logs_%s PARTITION OF audit_logs
            FOR VALUES FROM (%L) TO (%L)',
            to_char(CURRENT_DATE + (i || ' months')::interval, 'YYYY_MM'),
            CURRENT_DATE + (i || ' months')::interval,
            CURRENT_DATE + ((i + 1) || ' months')::interval
        );
    END LOOP;
END $$;

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_trading_data_timestamp ON trading_data (timestamp);
CREATE INDEX IF NOT EXISTS idx_trading_data_symbol ON trading_data (symbol);
CREATE INDEX IF NOT EXISTS idx_trading_data_strategy ON trading_data (strategy);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics (timestamp);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_type ON performance_metrics (metric_type, metric_name);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs (event_type);

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update triggers
CREATE TRIGGER update_strategies_updated_at BEFORE UPDATE ON strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_portfolios_updated_at BEFORE UPDATE ON portfolios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) for multi-tenant support
ALTER TABLE trading_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (adjust based on your authentication system)
CREATE POLICY trading_data_policy ON trading_data FOR ALL USING (true);
CREATE POLICY strategies_policy ON strategies FOR ALL USING (true);
CREATE POLICY portfolios_policy ON portfolios FOR ALL USING (true);

-- Grant permissions to production user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tradingbot_prod;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tradingbot_prod;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO tradingbot_prod;

-- Create backup user with read-only access
CREATE USER backup_user WITH PASSWORD 'backup_password_here';
GRANT CONNECT ON DATABASE trading_bot_prod TO backup_user;
GRANT USAGE ON SCHEMA public TO backup_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_user;

-- Insert initial data
INSERT INTO strategies (name, description, parameters) VALUES
('CCI_Strategy', 'Commodity Channel Index based trading strategy', '{"period": 20, "overbought": 100, "oversold": -100}'),
('RSI_MACD_Strategy', 'Combined RSI and MACD strategy', '{"rsi_period": 14, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9}'),
('Bollinger_Bands_Strategy', 'Bollinger Bands mean reversion strategy', '{"period": 20, "std_dev": 2, "squeeze_threshold": 0.1}')
ON CONFLICT (name) DO NOTHING;

INSERT INTO portfolios (name, total_value, available_balance) VALUES
('Main Portfolio', 10000.0, 10000.0)
ON CONFLICT DO NOTHING;