from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from app.services.auth_service import verify_password, get_password_hash, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from app.db.repository import get_user_by_username, create_user
from datetime import timedelta

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class UserAuthRequest(BaseModel):
    username: str
    password: str

@router.post("/register")
async def register(request: UserAuthRequest, response: Response):
    user = await get_user_by_username(request.username)
    if user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(request.password)
    user_data = {
        "username": request.username,
        "password": hashed_password
    }
    await create_user(user_data)
    
    # Auto login after creating
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": request.username}, expires_delta=access_token_expires)
    refresh_token = create_access_token(data={"sub": request.username}, expires_delta=timedelta(days=7))
    
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True, 
        max_age=7 * 24 * 60 * 60,
        samesite="lax",
        secure=False 
    )
    return {"success": True, "message": "User registered successfully", "access_token": access_token, "token_type": "bearer"}

@router.post("/login")
async def login(request: UserAuthRequest, response: Response):
    user = await get_user_by_username(request.username)
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)
    
    # Refresh token TTL 7 days
    refresh_token = create_access_token(data={"sub": user["username"]}, expires_delta=timedelta(days=7))
    
    # Set HTTP-only cookie for refresh token
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True, 
        max_age=7 * 24 * 60 * 60,
        samesite="lax",
        secure=False  # Typically True for https
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token")
    return {"success": True, "message": "Logged out"}
