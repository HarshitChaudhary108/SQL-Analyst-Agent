"""
Minimal FastAPI wrapper around the LangGraph SQL analyst agent.

Run locally:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from typing import Optional

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field

from agent.sql_analyst import sql_analyst

app = FastAPI(
    title="SQL Analyst Agent API",
    description="Turns natural language questions into safe, read-only SQL queries and answers them.",
    version="0.1.0",
)


class QueryRequest(BaseModel):
    question: str = Field(..., examples="What is the email address of user with first name Joshua and last name Walker?")


class QueryResponse(BaseModel):
    final_answer: str
    generated_sql_query: Optional[str] = None
    is_safe: Optional[str] = None
    comments: Optional[str] = None


@app.get("/health")
def health() -> dict:
    """Simple liveness check used by load balancers / container orchestrators."""
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse )
def query(request: QueryRequest = Path(..., description="Write your query in Human Language", example="What is the email address of user with first name Joshua and last name Walker?")) -> QueryResponse:
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    initial_state = {
        "messages": [],
        "user_question": request.question,
        "curated_ques": "",
        "prompt_query": "",
        "is_safe": "",
        "generated_sql_query": "",
        "comments": "",
        "sql_execution_result": "",
        "final_answer": "",
    }

    try:
        final_state = sql_analyst.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}")

    return QueryResponse(
        final_answer=final_state.get("final_answer", ""),
        generated_sql_query=final_state.get("generated_sql_query", ""),
        is_safe=final_state.get("is_safe", ""),
        comments=final_state.get("comments", ""),
    )