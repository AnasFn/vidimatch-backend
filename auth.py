from fastapi import FastAPI, Request, Response, HTTPException, Depends, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import jwt

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key')  # Add this to your .env file

if not supabase_url or not supabase_key:
    raise ValueError("Supabase credentials not found in environment variables")

supabase: Client = create_client(supabase_url, supabase_key)

def create_subscription_token(user_id: str, has_active_subscription: bool) -> str:
    """Create a JWT token containing user ID and subscription status"""
    payload = {
        'user_id': user_id,
        'has_active_subscription': has_active_subscription,
        'exp': datetime.utcnow() + timedelta(hours=24)  # Token expires in 24 hours
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_subscription_token(token: str) -> dict:
    """Verify and decode the subscription JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(request: Request):
    """Extracts and verifies the JWT from cookies using Supabase"""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Use Supabase to verify the token and get user
        user = supabase.auth.get_user(token)
        return user.user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication")

def check_subscription_status(request: Request):
    """Check subscription status without requiring it"""
    subscription = request.cookies.get("subscription")
    if not subscription:
        return False
    
    try:
        payload = verify_subscription_token(subscription)
        return payload.get('has_active_subscription', False)
    except:
        return False

def get_subscription_status(user=Depends(get_current_user), subscription: str = Cookie(None)):
    """Verify user's subscription status from JWT cookie"""
    if not subscription:
        raise HTTPException(status_code=403, detail="Active subscription required")
    
    try:
        payload = verify_subscription_token(subscription)
        if not payload['has_active_subscription']:
            raise HTTPException(status_code=403, detail="Active subscription required")
        if payload['user_id'] != user.id:
            raise HTTPException(status_code=403, detail="Invalid subscription token")
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid subscription token")

def init_auth_routes(app):
    """Initialize authentication routes with the main FastAPI application"""
    app.post("/auth/google/signin")(google_signin)
    app.get("/auth/callback")(auth_callback)
    app.get("/auth/user")(get_user)
    app.post("/auth/logout")(logout)
    app.post("/verify-user")(verify_user)
    return app

@app.post("/auth/google/signin")
async def google_signin():
    """Starts Google OAuth login and redirects to Google's auth page"""
    try:
        auth_response = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "http://localhost:8000/auth/callback"
            }
        })

        # The URL is directly available on the response object
        return RedirectResponse(auth_response.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/callback")
async def auth_callback(code: str):
    """Handles the OAuth callback and sets a session cookie"""
    try:
        # Correct way to exchange code for session
        session = supabase.auth.exchange_code_for_session({"auth_code": code})

        # Extract access token
        access_token = session.session.access_token
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token in session")

        # Set secure cookie with JWT
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(
            key="session",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400  # 24 hours
        )
        
        # After setting session cookie, verify subscription status
        user = supabase.auth.get_user(access_token).user
        subscription_response = await verify_user_subscription(user.id)
        if isinstance(subscription_response, Response):
            # Copy subscription cookie to this response
            subscription_cookie = subscription_response.headers.get('set-cookie')
            if subscription_cookie:
                response.headers.append('set-cookie', subscription_cookie)
        
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/user")
async def get_user(request: Request):
    """Returns authenticated user's details"""
    try:
        user = get_current_user(request)
        has_subscription = check_subscription_status(request)
        return {
            "email": user.email,
            "user_id": user.id,
            "role": user.role,
            "avatar_url": user.user_metadata.get('avatar_url') if user.user_metadata else None,
            "name": user.user_metadata.get('full_name') if user.user_metadata else None,
            "has_subscription": has_subscription
        }
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.post("/auth/logout")
async def logout(response: Response):
    """Clears authentication cookie"""
    response = RedirectResponse(url="/login")
    response.delete_cookie(key="session")
    response.delete_cookie(key="subscription")
    return response

async def verify_user_subscription(user_id: str) -> Response:
    """Check user's subscription status and update subscription cookie"""
    try:
        # Query Supabase for active subscription
        subscription = supabase.table('subscriptions').select('*').eq('user_id', user_id).eq('status', 'active').execute()
        has_active_subscription = len(subscription.data) > 0
        
        # Create subscription token
        subscription_token = create_subscription_token(user_id, has_active_subscription)
        
        # Create response with subscription cookie
        response = JSONResponse(content={
            "has_active_subscription": has_active_subscription
        })
        
        response.set_cookie(
            key="subscription",
            value=subscription_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400  # 24 hours
        )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify-user")
async def verify_user(user=Depends(get_current_user)):
    """Verify user's authentication and subscription status"""
    return await verify_user_subscription(user.id)
