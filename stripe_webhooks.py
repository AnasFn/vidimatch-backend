import stripe
from datetime import datetime
import os
from typing import Optional
from auth import supabase
import httpx

async def call_verify_user(user_id: str):
    """Call verify-user endpoint to update subscription status"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'http://localhost:8000/verify-user',
                headers={'X-User-ID': user_id},
                timeout=5.0
            )
            print(f"Verify-user response: {response.status_code}")
    except Exception as e:
        print(f"Error calling verify-user: {str(e)}")

async def handle_subscription_updated(event):
    """Handle subscription updated event"""
    try:
        subscription = event.data.object
        customer_id = subscription.customer
        print(f"Processing subscription update for customer {customer_id}")
        
        # Get user by stripe customer ID
        user_data = supabase.table('subscriptions').select('user_id').eq('stripe_customer_id', customer_id).execute()
        if not user_data.data:
            print(f"No subscription found for customer {customer_id}")
            return
        
        user_id = user_data.data[0]['user_id']
        
        # Update subscription data
        subscription_data = {
            'status': subscription.status,
            'current_period_start': datetime.fromtimestamp(subscription.current_period_start).isoformat(),
            'current_period_end': datetime.fromtimestamp(subscription.current_period_end).isoformat(),
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'updated_at': datetime.now().isoformat()
        }
        
        print(f"Updating subscription data for user {user_id}")
        supabase.table('subscriptions').update(subscription_data).eq('stripe_customer_id', customer_id).execute()
        print("Subscription update successful")
        
        # Update subscription token
        await call_verify_user(user_id)
        
    except Exception as e:
        print(f"Error in handle_subscription_updated: {str(e)}")
        raise e

async def handle_checkout_completed(event):
    """Handle successful checkout completion"""
    try:
        session = event.data.object
        print(f"Processing checkout session {session.id}")
        
        # Get the user ID from client_reference_id
        user_id = session.client_reference_id
        if not user_id:
            print("Error: No user_id found in client_reference_id")
            return
            
        customer_id = session.customer
        subscription_id = getattr(session, 'subscription', None)
        print(f"Customer ID: {customer_id}, Subscription ID: {subscription_id}")
        
        # Get line items using Stripe API
        session_with_items = stripe.checkout.Session.retrieve(
            session.id,
            expand=['line_items.data.price']
        )
        
        if not session_with_items.line_items.data:
            print("Error: No line items found in session")
            return
            
        # Get the price from the first line item
        price = session_with_items.line_items.data[0].price
        price_id = price.id
        print(f"Price ID from session: {price_id}")
        
        # Get the plan type based on mode and price
        plan_type = None
        if session.mode == 'subscription':
            recurring = getattr(price, 'recurring', None)
            if recurring and recurring.get('interval') == 'month':
                plan_type = 'monthly'
            elif recurring and recurring.get('interval') == 'year':
                plan_type = 'yearly'
        else:
            # One-time payment
            plan_type = 'lifetime'
            
        print(f"Determined plan type: {plan_type} from mode: {session.mode}")
            
        # Get subscription details if it exists
        current_period_end = None
        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            current_period_end = datetime.fromtimestamp(subscription.current_period_end).isoformat()
            print(f"Subscription period end: {current_period_end}")
        
        # For one-time payments, set current_period_end to None
        if plan_type == 'lifetime':
            current_period_end = None
        
        # Insert or update subscription record
        subscription_data = {
            'user_id': user_id,
            'stripe_customer_id': customer_id,
            'stripe_subscription_id': subscription_id,
            'plan_type': plan_type,
            'status': 'active',
            'current_period_start': datetime.now().isoformat(),
            'current_period_end': current_period_end,
            'cancel_at_period_end': False
        }
        
        print(f"Preparing to save subscription data: {subscription_data}")
        
        # Check if subscription exists
        existing = supabase.table('subscriptions').select('*').eq('user_id', user_id).execute()
        
        if existing.data:
            print(f"Updating existing subscription for user {user_id}")
            supabase.table('subscriptions').update(subscription_data).eq('user_id', user_id).execute()
        else:
            print(f"Creating new subscription for user {user_id}")
            supabase.table('subscriptions').insert(subscription_data).execute()
            
        print("Subscription saved successfully")
        
        # Update subscription token
        await call_verify_user(user_id)
            
    except Exception as e:
        print(f"Error in handle_checkout_completed: {str(e)}")
        print(f"Event data: {event.data}")
        raise e

async def handle_subscription_deleted(event):
    """Handle subscription deletion"""
    try:
        subscription = event.data.object
        customer_id = subscription.customer
        print(f"Processing subscription deletion for customer {customer_id}")
        
        # Get user by stripe customer ID
        user_data = supabase.table('subscriptions').select('user_id').eq('stripe_customer_id', customer_id).execute()
        if not user_data.data:
            print(f"No subscription found for customer {customer_id}")
            return
            
        user_id = user_data.data[0]['user_id']
        
        # Update subscription status
        subscription_data = {
            'status': 'expired',
            'updated_at': datetime.now().isoformat()
        }
        
        print(f"Marking subscription as expired for customer {customer_id}")
        supabase.table('subscriptions').update(subscription_data).eq('stripe_customer_id', customer_id).execute()
        print("Subscription marked as expired")
        
        # Update subscription token
        await call_verify_user(user_id)
        
    except Exception as e:
        print(f"Error in handle_subscription_deleted: {str(e)}")
        raise e

# Webhook handler mapping
WEBHOOK_HANDLERS = {
    'checkout.session.completed': handle_checkout_completed,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted
}
