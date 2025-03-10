import os
from dotenv import load_dotenv
import stripe

load_dotenv()

# Initialize Stripe with the secret key from .env
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Price IDs from .env
PRICE_IDS = {
    'monthly': os.getenv('STRIPE_PRICE_ID_MONTHLY'),
    'yearly': os.getenv('STRIPE_PRICE_ID_YEARLY'),
    'lifetime': os.getenv('STRIPE_PRICE_ID_LIFETIME')
}

def create_checkout_session(plan: str, user_id: str, customer_email: str):
    """Create a Stripe checkout session for subscription or one-time payment."""
    price_id = PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Invalid plan: {plan}")

    print(f"Creating checkout session for plan: {plan} with price_id: {price_id}")

    # Create or get customer
    customers = stripe.Customer.list(email=customer_email, limit=1)
    if customers.data:
        customer = customers.data[0]
    else:
        customer = stripe.Customer.create(email=customer_email)
    
    print(f"Using customer: {customer.id}")

    # Use checkout_success.html page instead of login page
    success_url = os.getenv('STRIPE_SUCCESS_URL', 'http://localhost:8000/checkout-success')
    cancel_url = os.getenv('STRIPE_CANCEL_URL', 'http://localhost:8000/dashboard')

    # Base parameters
    checkout_params = {
        'success_url': success_url,
        'cancel_url': cancel_url,
        'customer': customer.id,  # Always set the customer
        'client_reference_id': user_id,
        'line_items': [{'price': price_id, 'quantity': 1}],
        'mode': 'subscription' if plan in ['monthly', 'yearly'] else 'payment'
    }

    print(f"Checkout parameters: {checkout_params}")
    session = stripe.checkout.Session.create(**checkout_params)
    print(f"Created checkout session: {session.id}")
    return session.url
