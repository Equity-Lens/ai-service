from datetime import datetime
from typing import Optional
from bson import ObjectId
from database.mongodb import get_database


class ChatModel:
    """Handles all chat session database operations."""
    
    @staticmethod
    def get_collection():
        """Get the chat_sessions collection."""
        db = get_database()
        return db.chat_sessions
    
    @staticmethod
    async def create_session(user_id: int, title: str = "New Chat") -> dict:
        """
        Create a new chat session.
        
        Args:
            user_id: The user's ID
            title: Session title (auto-generated from first message later)
            
        Returns:
            The created session document
        """
        collection = ChatModel.get_collection()
        
        session = {
            "user_id": user_id,
            "title": title,
            "messages": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await collection.insert_one(session)
        session["_id"] = result.inserted_id
        
        return session
    
    @staticmethod
    async def get_user_sessions(user_id: int, limit: int = 50) -> list:
        """
        Get all chat sessions for a user, sorted by most recent.
        
        Args:
            user_id: The user's ID
            limit: Maximum number of sessions to return
            
        Returns:
            List of session documents
        """
        collection = ChatModel.get_collection()
        
        cursor = collection.find(
            {"user_id": user_id},
            {"messages": 0}  # Exclude messages for list view
        ).sort("updated_at", -1).limit(limit)
        
        sessions = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string for JSON serialization
        for session in sessions:
            session["_id"] = str(session["_id"])
        
        return sessions
    
    @staticmethod
    async def get_session(session_id: str, user_id: int) -> Optional[dict]:
        """
        Get a specific chat session with all messages.
        
        Args:
            session_id: The session's ObjectId as string
            user_id: The user's ID (for authorization)
            
        Returns:
            The session document or None
        """
        collection = ChatModel.get_collection()
        
        try:
            session = await collection.find_one({
                "_id": ObjectId(session_id),
                "user_id": user_id
            })
            
            if session:
                session["_id"] = str(session["_id"])
            
            return session
        except:
            return None
    
    @staticmethod
    async def add_message(session_id: str, role: str, content: str) -> bool:
        """
        Add a message to a chat session.
        
        Args:
            session_id: The session's ObjectId as string
            role: "user" or "assistant"
            content: The message content
            
        Returns:
            True if successful
        """
        collection = ChatModel.get_collection()
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow()
        }
        
        result = await collection.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def update_title(session_id: str, title: str) -> bool:
        """
        Update the session title.
        
        Args:
            session_id: The session's ObjectId as string
            title: New title
            
        Returns:
            True if successful
        """
        collection = ChatModel.get_collection()
        
        result = await collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"title": title, "updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def delete_session(session_id: str, user_id: int) -> bool:
        """
        Delete a chat session.
        
        Args:
            session_id: The session's ObjectId as string
            user_id: The user's ID (for authorization)
            
        Returns:
            True if successful
        """
        collection = ChatModel.get_collection()
        
        result = await collection.delete_one({
            "_id": ObjectId(session_id),
            "user_id": user_id
        })
        
        return result.deleted_count > 0
    
    @staticmethod
    async def generate_title(first_message: str) -> str:
        """
        Generate a title from the first message.
        Truncates to 50 characters.
        
        Args:
            first_message: The user's first message
            
        Returns:
            A short title
        """
        # Clean and truncate
        title = first_message.strip()
        
        if len(title) > 50:
            title = title[:47] + "..."
        
        return title