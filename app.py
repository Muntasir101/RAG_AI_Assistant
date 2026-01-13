"""
FastAPI backend for RAG AI Decision Assistant
Provides REST API endpoints for question-answering with session management
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from retriever import get_answer
from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG AI Decision Assistant API",
    description="AI decision assistant for volleyball athletes using RAG",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage (for MVP - use Redis in production)
sessions: Dict[str, Dict] = {}


class QueryRequest(BaseModel):
    """Request model for asking questions"""
    user_id: Optional[str] = Field(None, description="User identifier")
    question: str = Field(..., min_length=1, max_length=1000, description="User's question")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation tracking")


class QueryResponse(BaseModel):
    """Response model for answers"""
    answer: str
    session_id: str
    sources: list
    confidence: float
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str
    timestamp: str


def get_or_create_session(session_id: Optional[str] = None) -> str:
    """
    Get existing session or create a new one
    
    Args:
        session_id: Optional existing session ID
        
    Returns:
        Session ID string
    """
    if session_id and session_id in sessions:
        return session_id
    
    new_session_id = str(uuid.uuid4())
    sessions[new_session_id] = {
        "created_at": datetime.utcnow().isoformat(),
        "messages": []
    }
    return new_session_id


@app.get("/")
async def home():
    """Serve the web UI"""
    return FileResponse("templates/index.html")

@app.get("/api/health", response_model=HealthResponse)
async def health_check_api():
    """Health check endpoint (API)"""
    return {
        "status": "healthy",
        "message": "RAG AI Decision Assistant API is running ✅",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check endpoint"""
    try:
        # Try to load the vector store to verify system is ready
        from retriever import load_vector_store
        load_vector_store()
        
        return {
            "status": "healthy",
            "message": "System is operational and knowledge base is loaded",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"System not ready: {str(e)}"
        )


@app.post("/ask", response_model=QueryResponse)
async def ask(query: QueryRequest):
    """
    Main endpoint for asking questions
    
    Args:
        query: Query request with question and optional session info
        
    Returns:
        QueryResponse with answer, sources, and metadata
        
    Raises:
        HTTPException: If processing fails
    """
    try:
        # Validate question
        if not query.question or not query.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty"
            )
        
        # Get or create session
        session_id = get_or_create_session(query.session_id)
        
        # Get answer from RAG system
        logger.info(f"Processing question for session {session_id}")
        result = get_answer(query.question, user_id=query.user_id or session_id)
        
        # Store in session history
        sessions[session_id]["messages"].append({
            "question": query.question,
            "answer": result["answer"],
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Return structured response
        return QueryResponse(
            answer=result["answer"],
            session_id=session_id,
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.0),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing question: {str(e)}"
        )


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session history"""
    if session_id not in sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return sessions[session_id]


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_id in sessions:
        del sessions[session_id]
        return {"message": "Session deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
