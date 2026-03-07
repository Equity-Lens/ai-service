import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

# MongoDB client instance
client = None
db = None


async def connect_to_mongodb():
    """Connect to MongoDB Atlas."""
    global client, db
    
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI not found in environment variables")
    
    try:
        # Create client
        client = AsyncIOMotorClient(MONGODB_URI, server_api=ServerApi('1'))
        
        # Get database (creates if doesn't exist)
        db = client.marketaxis
        
        # Test connection
        await client.admin.command('ping')
        print(" Connected to MongoDB Atlas!")
        
        # Create indexes for better performance
        await create_indexes()
        
        return db
        
    except Exception as e:
        print(f" MongoDB connection failed: {e}")
        raise e


async def create_indexes():
    """Create indexes for better query performance."""
    global db
    
    # Index on user_id for fast session lookups
    await db.chat_sessions.create_index("user_id")
    
    # Index on updated_at for sorting recent chats
    await db.chat_sessions.create_index("updated_at")
    
    # Compound index for user's recent chats
    await db.chat_sessions.create_index([("user_id", 1), ("updated_at", -1)])
    
    print(" MongoDB indexes created!")


async def close_mongodb_connection():
    """Close MongoDB connection."""
    global client
    
    if client:
        client.close()
        print(" MongoDB connection closed!")


def get_database():
    """Get database instance."""
    global db
    return db