from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from jose import JWTError, jwt
from typing import List
from models import VideoAnalysisRequest, VideoAnalysis
from youtube_client import get_youtube_client, get_video_details, get_video_comments
from openai_client import analyze_content
from auth import init_auth_routes, get_current_user, get_subscription_status, verify_user_subscription, check_subscription_status, supabase
from stripe_config import create_checkout_session
from stripe_webhooks import WEBHOOK_HANDLERS
from pydantic import BaseModel
import stripe
import os

class CheckoutRequest(BaseModel):
    plan: str

# Create a FastAPI application instance
app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize templates
templates = Jinja2Templates(directory="static/templates")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    #allow_origins=["chrome-extension://iegaghldafpocoemdkcldpnchgignjgg"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
) 

@app.post("/analyze/", response_model=List[VideoAnalysis])
async def analyze_videos(request: VideoAnalysisRequest, subscription=Depends(get_subscription_status)):
    """Endpoint to analyze multiple videos. Requires active subscription."""
    youtube = get_youtube_client()
    results = []
    
    for video_id in request.video_ids:
        video_details = get_video_details(youtube, video_id)
        comments = get_video_comments(youtube, video_id)
        
        analysis = analyze_content(
            request.search_term,
            video_details['title'],
            video_details['description'],
            comments
        )
        
        results.append(VideoAnalysis(
            video_id=video_id,
            match_rate=analysis['match_rate'],
            comment_summaries=analysis['comment_summaries'],
            title=video_details['title'],
            description=video_details['description']
        ))
    
    return results

# Initialize authentication routes
init_auth_routes(app)

@app.post("/create-checkout-session")
async def create_stripe_checkout_session(request: CheckoutRequest, user=Depends(get_current_user)):
    """Create a Stripe checkout session for subscription or one-time payment."""
    try:
        checkout_url = create_checkout_session(request.plan, user.id, user.email)
        return JSONResponse(content={"url": checkout_url})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    handler = WEBHOOK_HANDLERS.get(event.type)
    if handler:
        try:
            await handler(event)
            # After successful payment/subscription update, verify user subscription
            if event.type == 'checkout.session.completed':
                user_id = event.data.object.client_reference_id
                if user_id:
                    await verify_user_subscription(user_id)
            return JSONResponse(content={"status": "success"})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return JSONResponse(content={"status": "ignored", "type": event.type})
  
# Page routes
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/checkout-success")
async def checkout_success(request: Request):
    """Handle successful checkout with subscription verification polling"""
    return templates.TemplateResponse("checkout_success.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    try:
        # Check if user is already authenticated
        token = request.cookies.get("session")
        if token:
            user = supabase.auth.get_user(token)
            if user and user.user:
                # Valid session exists, redirect to dashboard
                return RedirectResponse(url="/dashboard", status_code=303)
    except Exception:
        # If token is invalid, delete it and show login page
        response = templates.TemplateResponse("login.html", {"request": request})
        response.delete_cookie(key="session")
        return response
    
    # No token or invalid token, show login page
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard")
async def dashboard(request: Request):
    try:
        # Check if user is authenticated
        token = request.cookies.get("session")
        print(f"Session token present: {bool(token)}")
        if not token:
            return RedirectResponse(url="/login", status_code=303)
        
        # Verify token
        try:
            print("Attempting to verify user token...")
            user = supabase.auth.get_user(token)
            if not user or not user.user:
                print("User verification failed: No user data returned")
                response = RedirectResponse(url="/login", status_code=303)
                response.delete_cookie(key="session")
                return response
                
            print(f"User verified successfully: {user.user.email}")
            # Check subscription status
            has_subscription = check_subscription_status(request)
            print(f"Subscription status: {has_subscription}")
                
            # User is authenticated, show dashboard
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "user": {
                    "email": user.user.email,
                    "name": user.user.user_metadata.get('full_name') if user.user.user_metadata else None,
                    "has_subscription": has_subscription
                }
            })
        except Exception as e:
            print(f"Token verification error: {str(e)}")
            # Only delete cookie if it's a token validation error
            if "JWT" in str(e) or "token" in str(e).lower():
                print("JWT validation error detected, clearing session")
                response = RedirectResponse(url="/login", status_code=303)
                response.delete_cookie(key="session")
                return response
            # For other errors, just redirect without deleting cookie
            print(f"Non-JWT error occurred: {str(e)}")
            return RedirectResponse(url="/login", status_code=303)
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        return RedirectResponse(url="/login", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)