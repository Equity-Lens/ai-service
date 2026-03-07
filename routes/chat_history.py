from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List
from models.chat import ChatModel
from jose import JWTError, jwt
from config import settings

router = APIRouter(prefix="/v1/ai/sessions", tags=["Chat History"])


# ============================================
# JWT DEPENDENCY
# ============================================

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        if settings.DEBUG:
            return {"userId": 3, "email": "test@example.com"}
        raise HTTPException(status_code=401, detail="Authorization header missing")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        user_id = payload.get("userId") or payload.get("user_id") or payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        return {"userId": int(user_id), "email": payload.get("email")}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ============================================
# REQUEST / RESPONSE MODELS
# ============================================

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"


class UpdateTitleRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    user_id: int
    title: str
    created_at: str
    updated_at: str


class SessionWithMessagesResponse(BaseModel):
    id: str
    user_id: int
    title: str
    messages: list
    created_at: str
    updated_at: str


class ChatInSessionRequest(BaseModel):
    query: str


class ConversationMessage(BaseModel):
    role: str
    content: str


class GuestChatRequest(BaseModel):
    message: str
    conversation_history: List[ConversationMessage] = []


# ============================================
# GUEST CHAT (No Auth)
# ============================================

@router.post("/chat/guest")
async def guest_chat(request: GuestChatRequest):
    """
    Stateless chat for unauthenticated users.
    - No session persistence
    - Conversation history passed from frontend
    - Limited tool access (no portfolio/personal data tools)
    """
    from server import create_guest_agent
    import asyncio

    try:
        chat_history = []
        for msg in request.conversation_history[-10:]:
            if msg.role == "user":
                from langchain_core.messages import HumanMessage
                chat_history.append(HumanMessage(content=msg.content))
            else:
                from langchain_core.messages import AIMessage
                chat_history.append(AIMessage(content=msg.content))

        agent_executor = create_guest_agent()

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: agent_executor.invoke({
                "input": request.message,
                "chat_history": chat_history
            })
        )

        answer = result.get("output", "I couldn't generate a response.")

        tools_used = []
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if len(step) >= 1 and hasattr(step[0], "tool"):
                    tools_used.append(step[0].tool)

        return {
            "success": True,
            "data": {
                "answer": answer,
                "tools_used": list(set(tools_used))
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# AUTHENTICATED USER CHAT SESSIONS
# ============================================

@router.get("")
async def get_all_sessions(current_user: dict = Depends(get_current_user)):
    """Get all chat sessions for the current user."""
    user_id = current_user["userId"]
    sessions = await ChatModel.get_user_sessions(user_id)

    return {
        "success": True,
        "data": {
            "sessions": [
                {
                    "id": s["_id"],
                    "title": s["title"],
                    "created_at": s["created_at"].isoformat(),
                    "updated_at": s["updated_at"].isoformat()
                }
                for s in sessions
            ],
            "count": len(sessions)
        }
    }


@router.post("")
async def create_session(request: CreateSessionRequest, current_user: dict = Depends(get_current_user)):
    """Create a new chat session."""
    user_id = current_user["userId"]
    session = await ChatModel.create_session(
        user_id=user_id,
        title=request.title
    )

    return {
        "success": True,
        "data": {
            "id": str(session["_id"]),
            "title": session["title"],
            "created_at": session["created_at"].isoformat(),
            "updated_at": session["updated_at"].isoformat()
        }
    }


@router.get("/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific chat session with all messages."""
    user_id = current_user["userId"]
    session = await ChatModel.get_session(session_id, user_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "success": True,
        "data": {
            "id": session["_id"],
            "title": session["title"],
            "messages": [
                {
                    "role": m["role"],
                    "content": m["content"],
                    "timestamp": m["timestamp"].isoformat()
                }
                for m in session.get("messages", [])
            ],
            "created_at": session["created_at"].isoformat(),
            "updated_at": session["updated_at"].isoformat()
        }
    }


@router.patch("/{session_id}")
async def update_session_title(session_id: str, request: UpdateTitleRequest, current_user: dict = Depends(get_current_user)):
    """Update a session's title."""
    success = await ChatModel.update_title(session_id, request.title)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "success": True,
        "message": "Title updated"
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a chat session."""
    user_id = current_user["userId"]
    success = await ChatModel.delete_session(session_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "success": True,
        "message": "Session deleted"
    }


@router.post("/{session_id}/chat")
async def chat_in_session(session_id: str, request: ChatInSessionRequest, current_user: dict = Depends(get_current_user)):
    """Send a message in a chat session and get AI response."""
    from server import create_agent
    import asyncio

    user_id = current_user["userId"]

    # Verify session exists and belongs to this user
    session = await ChatModel.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message
    await ChatModel.add_message(session_id, "user", request.query)

    # Update title if first message
    if len(session.get("messages", [])) == 0:
        title = await ChatModel.generate_title(request.query)
        await ChatModel.update_title(session_id, title)

    # Build chat history for context
    chat_history = []
    for msg in session.get("messages", [])[-10:]:
        if msg["role"] == "user":
            from langchain_core.messages import HumanMessage
            chat_history.append(HumanMessage(content=msg["content"]))
        else:
            from langchain_core.messages import AIMessage
            chat_history.append(AIMessage(content=msg["content"]))

    # Get AI response
    agent_executor = create_agent(user_id)

    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: agent_executor.invoke({
            "input": request.query,
            "chat_history": chat_history
        })
    )

    answer = result.get("output", "I couldn't generate a response.")

    # Save assistant response
    await ChatModel.add_message(session_id, "assistant", answer)

    # Get tools used
    tools_used = []
    if "intermediate_steps" in result:
        for step in result["intermediate_steps"]:
            if len(step) >= 1 and hasattr(step[0], "tool"):
                tools_used.append(step[0].tool)

    return {
        "success": True,
        "data": {
            "session_id": session_id,
            "query": request.query,
            "answer": answer,
            "tools_used": list(set(tools_used))
        }
    }