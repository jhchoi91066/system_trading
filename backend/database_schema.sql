-- Bitcoin Trading Bot Database Schema
-- This file contains the SQL commands to create all necessary tables in Supabase

-- 1. Active Strategies Table
-- Stores information about strategies that are currently active for real-time trading
CREATE TABLE IF NOT EXISTS active_strategies (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    strategy_id INTEGER NOT NULL,
    exchange_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    allocated_capital DECIMAL(15,2) NOT NULL,
    stop_loss_percentage DECIMAL(5,2) DEFAULT 5.0,
    take_profit_percentage DECIMAL(5,2) DEFAULT 10.0,
    max_position_size DECIMAL(5,4) DEFAULT 0.1,
    risk_per_trade DECIMAL(5,2) DEFAULT 2.0,
    daily_loss_limit DECIMAL(5,2) DEFAULT 5.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deactivated_at TIMESTAMP WITH TIME ZONE,
    
    -- Add foreign key constraint to strategies table
    CONSTRAINT fk_active_strategies_strategy 
        FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
);

-- 2. Trades Table
-- Stores all executed trades (both manual and automated)
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    strategy_id INTEGER,
    exchange_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    order_type TEXT NOT NULL CHECK (order_type IN ('buy', 'sell')),
    amount DECIMAL(20,8) NOT NULL,
    price DECIMAL(20,8),
    order_id TEXT,
    status TEXT DEFAULT 'pending',
    executed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Add foreign key constraint to strategies table (optional for manual trades)
    CONSTRAINT fk_trades_strategy 
        FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE SET NULL
);

-- 3. Portfolio Table
-- Tracks user's portfolio performance over time
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    exchange_name TEXT NOT NULL,
    total_balance DECIMAL(20,8) NOT NULL,
    available_balance DECIMAL(20,8) NOT NULL,
    in_orders DECIMAL(20,8) DEFAULT 0,
    snapshot_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Strategy Performance Table
-- Tracks performance metrics for each active strategy
CREATE TABLE IF NOT EXISTS strategy_performance (
    id SERIAL PRIMARY KEY,
    active_strategy_id INTEGER NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    total_profit_loss DECIMAL(20,8) DEFAULT 0,
    max_drawdown DECIMAL(5,2) DEFAULT 0,
    current_position TEXT DEFAULT 'none', -- 'long', 'short', 'none'
    position_size DECIMAL(20,8) DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT fk_strategy_performance_active_strategy 
        FOREIGN KEY (active_strategy_id) REFERENCES active_strategies(id) ON DELETE CASCADE
);

-- 5. Update existing API Keys table structure if needed
-- Add indexes for better performance on frequently queried columns
CREATE INDEX IF NOT EXISTS idx_active_strategies_user_id ON active_strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_active_strategies_status ON active_strategies(is_active);
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy_id ON trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_user_id ON portfolio_snapshots(user_id);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_active_strategy_id ON strategy_performance(active_strategy_id);

-- Insert some sample data for testing
-- Note: Only run this section if you want sample data

-- Add enhanced strategies table structure
-- Strategies table (enhanced with new fields)
CREATE TABLE IF NOT EXISTS strategies (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    script TEXT NOT NULL,
    description TEXT,
    strategy_type TEXT DEFAULT 'custom',
    parameters JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sample strategy (assuming strategies table exists)
INSERT INTO strategies (name, script, description, strategy_type, parameters, created_at) 
VALUES (
    'CCI Strategy', 
    'def strategy(): return "CCI based trading"', 
    'Commodity Channel Index based trading strategy',
    'cci',
    '{"indicator": "CCI", "window": 20, "buy_threshold": -100, "sell_threshold": 100, "timeframe": "1h"}',
    NOW()
)
ON CONFLICT DO NOTHING;

-- Row Level Security (RLS) Policies
-- Enable RLS on tables
ALTER TABLE active_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_performance ENABLE ROW LEVEL SECURITY;

-- Create policies for user data isolation
-- Active Strategies policies
CREATE POLICY "Users can view their own active strategies" ON active_strategies
    FOR SELECT USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text);

CREATE POLICY "Users can insert their own active strategies" ON active_strategies
    FOR INSERT WITH CHECK (user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text);

CREATE POLICY "Users can update their own active strategies" ON active_strategies
    FOR UPDATE USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text);

-- Trades policies
CREATE POLICY "Users can view their own trades" ON trades
    FOR SELECT USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text);

CREATE POLICY "Users can insert their own trades" ON trades
    FOR INSERT WITH CHECK (user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text);

-- Portfolio snapshots policies
CREATE POLICY "Users can view their own portfolio snapshots" ON portfolio_snapshots
    FOR SELECT USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text);

CREATE POLICY "Users can insert their own portfolio snapshots" ON portfolio_snapshots
    FOR INSERT WITH CHECK (user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text);

-- Strategy performance policies
CREATE POLICY "Users can view strategy performance" ON strategy_performance
    FOR SELECT USING (
        active_strategy_id IN (
            SELECT id FROM active_strategies 
            WHERE user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text
        )
    );

CREATE POLICY "Users can insert strategy performance" ON strategy_performance
    FOR INSERT WITH CHECK (
        active_strategy_id IN (
            SELECT id FROM active_strategies 
            WHERE user_id = current_setting('request.jwt.claims', true)::json->>'sub'::text
        )
    );

-- Temporarily disable RLS for development (REMOVE IN PRODUCTION)
-- ALTER TABLE active_strategies DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE trades DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE portfolio_snapshots DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE strategy_performance DISABLE ROW LEVEL SECURITY;