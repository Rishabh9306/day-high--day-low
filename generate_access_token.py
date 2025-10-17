#!/usr/bin/env python3
"""
Kite Connect Access Token Generator

This script helps you generate an access token for Kite Connect API.
You need to run this once to get the access token.
"""

import os
from kiteconnect import KiteConnect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API credentials
api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')

if not api_key or not api_secret:
    print("❌ Error: API_KEY or API_SECRET not found in .env file")
    print("Please update your .env file with the API credentials")
    exit(1)

print("="*70)
print("KITE CONNECT - ACCESS TOKEN GENERATOR")
print("="*70)
print(f"\nAPI Key: {api_key}")
print(f"API Secret: {api_secret[:10]}...{api_secret[-5:]}")

# Initialize KiteConnect
kite = KiteConnect(api_key=api_key)

# Generate login URL
login_url = kite.login_url()

print("\n" + "="*70)
print("STEP 1: LOGIN TO KITE")
print("="*70)
print("\nPlease open this URL in your browser:")
print(f"\n{login_url}\n")

print("After login, you will be redirected to a URL like:")
print("http://localhost:3001/trade/redirect?request_token=XXXXX&action=login&status=success")
print("\nCopy the 'request_token' value from the URL")

# Get request token from user
print("\n" + "="*70)
request_token = input("Enter the request_token: ").strip()

if not request_token:
    print("❌ Error: Request token is required")
    exit(1)

try:
    # Generate session
    print("\n" + "="*70)
    print("STEP 2: GENERATING ACCESS TOKEN")
    print("="*70)
    
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    
    print(f"\n✅ Success! Your access token is:")
    print(f"\n{access_token}\n")
    
    # Update .env file
    print("="*70)
    print("STEP 3: UPDATING .ENV FILE")
    print("="*70)
    
    # Read current .env
    with open('.env.example', 'r') as f:
        lines = f.readlines()
    
    # Update access token
    updated_lines = []
    for line in lines:
        if line.startswith('ACCESS_TOKEN='):
            updated_lines.append(f'ACCESS_TOKEN={access_token}\n')
        else:
            updated_lines.append(line)
    
    # Write to .env
    with open('.env', 'w') as f:
        f.writelines(updated_lines)
    
    print("\n✅ .env file updated successfully!")
    print(f"\nYour access token has been saved to .env file")
    
    # Verify connection
    print("\n" + "="*70)
    print("STEP 4: VERIFYING CONNECTION")
    print("="*70)
    
    kite.set_access_token(access_token)
    profile = kite.profile()
    
    print(f"\n✅ Connected successfully!")
    print(f"User: {profile['user_name']}")
    print(f"Email: {profile['email']}")
    print(f"Broker: {profile['broker']}")
    
    print("\n" + "="*70)
    print("🎉 SETUP COMPLETE!")
    print("="*70)
    print("\nYou can now run the trading bot:")
    print("python main.py")
    print("\n⚠️  Note: Access token expires daily. You'll need to regenerate it each day.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nPlease check:")
    print("1. Your API key and secret are correct")
    print("2. The request token is valid (expires in 5 minutes)")
    print("3. Your internet connection is stable")
    exit(1)
