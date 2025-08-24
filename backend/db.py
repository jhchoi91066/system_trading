import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Create supabase client with timeout handling
try:
    if not url or not key:
        logger.warning("Supabase credentials not configured, database operations will use local storage")
        supabase: Client = None
    else:
        supabase: Client = create_client(url, key, options={
            "rest": {"timeout": 5}  # 5 second timeout
        })
        # Test connection
        test_response = supabase.table("strategies").select("count", count="exact").execute()
        logger.info(f"✅ Supabase connection established. Found {test_response.count} strategies.")
except Exception as e:
    logger.error(f"❌ Supabase connection failed: {e}")
    logger.info("Database operations will fallback to local storage")
    supabase: Client = None
