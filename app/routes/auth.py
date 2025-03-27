from fastapi import APIRouter, Request, Depends
from typing import Dict

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

@router.get("/public", operation_id="public_route")
async def public_route() -> Dict:
    """Public endpoint that doesn't require authentication"""
    return {"message": "This is a public endpoint accessible without authentication."}

@router.get("/protected", operation_id="protected_route")
async def protected_route(request: Request) -> Dict:
    """Protected endpoint that requires authentication"""
    return {
        "message": f"Welcome, authenticated user {request.state.user_id}!",
        "user_id": request.state.user_id
    } 