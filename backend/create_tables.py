#!/usr/bin/env python3
"""
Script to create necessary database tables in Supabase
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def create_tables():
    # Initialize Supabase client
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)
    
    print("Creating database tables...")
    
    # Create active_strategies table
    active_strategies_sql = """
    CREATE TABLE IF NOT EXISTS active_strategies (
        id SERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        strategy_id INTEGER NOT NULL,
        exchange_name TEXT NOT NULL,
        symbol TEXT NOT NULL,
        allocated_capital DECIMAL(15,2) NOT NULL,
        stop_loss_percentage DECIMAL(5,2) DEFAULT 5.0,
        take_profit_percentage DECIMAL(5,2) DEFAULT 10.0,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        deactivated_at TIMESTAMP WITH TIME ZONE
    );
    """
    
    try:
        result = supabase.rpc('exec_sql', {'sql': active_strategies_sql}).execute()
        print("✅ active_strategies table created successfully")
    except Exception as e:
        print(f"❌ Error creating active_strategies table: {e}")
    
    # Create trades table
    trades_sql = """
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
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """
    
    try:
        result = supabase.rpc('exec_sql', {'sql': trades_sql}).execute()
        print("✅ trades table created successfully")
    except Exception as e:
        print(f"❌ Error creating trades table: {e}")
    
    # Create indexes
    indexes_sql = """
    CREATE INDEX IF NOT EXISTS idx_active_strategies_user_id ON active_strategies(user_id);
    CREATE INDEX IF NOT EXISTS idx_active_strategies_status ON active_strategies(is_active);
    CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);
    CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC);
    """
    
    try:
        result = supabase.rpc('exec_sql', {'sql': indexes_sql}).execute()
        print("✅ Database indexes created successfully")
    except Exception as e:
        print(f"❌ Error creating indexes: {e}")
    
    # Disable RLS for development (CAUTION: Only for development)
    disable_rls_sql = """
    ALTER TABLE active_strategies DISABLE ROW LEVEL SECURITY;
    ALTER TABLE trades DISABLE ROW LEVEL SECURITY;
    """
    
    try:
        result = supabase.rpc('exec_sql', {'sql': disable_rls_sql}).execute()
        print("⚠️  RLS disabled for development (Remember to enable in production)")
    except Exception as e:
        print(f"❌ Error disabling RLS: {e}")
    
    print("\n🎉 Database setup completed!")
    print("You can now use the real-time trading features.")

if __name__ == "__main__":
    create_tables()