#!/usr/bin/env python3
"""
Simple database setup script using direct table creation
"""

from db import supabase

def setup_database():
    print("Setting up database tables...")
    
    # Test connection first
    try:
        test = supabase.table("strategies").select("count", count="exact").execute()
        print(f"✅ Database connection successful. Found {test.count} strategies.")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Create active_strategies table by inserting a dummy record and then deleting it
    # This will create the table structure automatically in Supabase
    try:
        # Insert dummy record to create table structure
        dummy_active_strategy = {
            "user_id": "setup_user",
            "strategy_id": 1,
            "exchange_name": "test_exchange",
            "symbol": "BTC/USDT",
            "allocated_capital": 1000.0,
            "stop_loss_percentage": 5.0,
            "take_profit_percentage": 10.0,
            "is_active": False
        }
        
        result = supabase.table("active_strategies").insert(dummy_active_strategy).execute()
        if result.data:
            # Delete the dummy record
            supabase.table("active_strategies").delete().eq("user_id", "setup_user").execute()
            print("✅ active_strategies table structure created")
    except Exception as e:
        print(f"ℹ️  active_strategies table may already exist or need manual creation: {e}")
    
    # Create trades table
    try:
        dummy_trade = {
            "user_id": "setup_user",
            "strategy_id": 1,
            "exchange_name": "test_exchange",
            "symbol": "BTC/USDT",
            "order_type": "buy",
            "amount": 0.001,
            "price": 50000.0,
            "status": "test"
        }
        
        result = supabase.table("trades").insert(dummy_trade).execute()
        if result.data:
            # Delete the dummy record
            supabase.table("trades").delete().eq("user_id", "setup_user").execute()
            print("✅ trades table structure created")
    except Exception as e:
        print(f"ℹ️  trades table may already exist or need manual creation: {e}")
    
    print("\n🎯 Database setup complete!")
    print("Note: If tables don't exist, please create them manually in Supabase SQL editor.")
    
    # Show manual SQL for reference
    print("\n📝 Manual SQL commands (if needed):")
    print("""
    -- Run this in Supabase SQL Editor if tables don't exist:
    
    CREATE TABLE active_strategies (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        strategy_id BIGINT NOT NULL,
        exchange_name TEXT NOT NULL,
        symbol TEXT NOT NULL,
        allocated_capital DECIMAL(15,2) NOT NULL,
        stop_loss_percentage DECIMAL(5,2) DEFAULT 5.0,
        take_profit_percentage DECIMAL(5,2) DEFAULT 10.0,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        deactivated_at TIMESTAMP WITH TIME ZONE
    );
    
    CREATE TABLE trades (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        strategy_id BIGINT,
        exchange_name TEXT NOT NULL,
        symbol TEXT NOT NULL,
        order_type TEXT NOT NULL,
        amount DECIMAL(20,8) NOT NULL,
        price DECIMAL(20,8),
        order_id TEXT,
        status TEXT DEFAULT 'pending',
        executed_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """)

if __name__ == "__main__":
    setup_database()