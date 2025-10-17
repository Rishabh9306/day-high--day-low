#!/usr/bin/env python3
"""
Automatic Access Token Generator for Kite Connect
This script runs a local server to handle the OAuth callback
"""
from kiteconnect import KiteConnect
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

# Your credentials
API_KEY = "8b3x3vuxw5qw7mfn"
API_SECRET = "i2xrv31cmmtyec4cef3j3r41l1olac3k"

# Global variable to store request token
request_token = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global request_token
        
        # Parse the URL to get request_token
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        
        if 'request_token' in params:
            request_token = params['request_token'][0]
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = """
            <html>
            <head>
                <title>Kite Connect - Success</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    }
                    .container {
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                        text-align: center;
                    }
                    .success {
                        color: #4CAF50;
                        font-size: 48px;
                        margin-bottom: 20px;
                    }
                    h1 {
                        color: #333;
                        margin-bottom: 10px;
                    }
                    p {
                        color: #666;
                        font-size: 16px;
                    }
                    .token {
                        background: #f5f5f5;
                        padding: 10px;
                        border-radius: 5px;
                        margin: 20px 0;
                        font-family: monospace;
                        word-break: break-all;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">✓</div>
                    <h1>Authentication Successful!</h1>
                    <p>Request token received successfully.</p>
                    <div class="token">""" + request_token + """</div>
                    <p>Generating access token...</p>
                    <p><strong>You can close this window now.</strong></p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            
            # Stop server after handling request
            threading.Thread(target=self.server.shutdown).start()
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Error: No request token found</h1></body></html>")
    
    def log_message(self, format, *args):
        # Suppress server logs
        pass

print("="*70)
print("KITE CONNECT - ACCESS TOKEN GENERATOR")
print("="*70)
print()

# Initialize Kite Connect
kite = KiteConnect(api_key=API_KEY)

# Start local server on port 3001
print("🚀 Starting local server on http://localhost:3001...")
try:
    server = HTTPServer(('localhost', 3001), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    print("✅ Server started successfully!")
except Exception as e:
    print(f"❌ Error starting server: {e}")
    print("Make sure port 3001 is not in use.")
    exit(1)

print()

# Generate login URL
login_url = kite.login_url()
print("🔐 Opening Kite Connect login page...")
print()
print("📋 Login URL:")
print(login_url)
print()

# Open browser automatically
try:
    webbrowser.open(login_url)
    print("✅ Browser opened automatically")
except:
    print("⚠️  Could not open browser automatically")
    print("Please copy and paste the URL above into your browser")

print()
print("⏳ Waiting for authentication...")
print("   (Please login to Kite and authorize the app)")
print()

# Wait for request token (timeout after 2 minutes)
timeout = 120
elapsed = 0
while request_token is None and elapsed < timeout:
    time.sleep(1)
    elapsed += 1

if request_token is None:
    print("❌ Timeout: No request token received")
    print("   Please try again")
    exit(1)

print("✅ Request token received!")
print(f"   Token: {request_token}")
print()

# Generate access token
print("🔑 Generating access token...")
try:
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    access_token = data["access_token"]
    
    print("✅ Access token generated successfully!")
    print()
    print("="*70)
    print("YOUR ACCESS TOKEN:")
    print("="*70)
    print(access_token)
    print("="*70)
    print()
    
    # Update .env file
    print("💾 Updating .env file...")
    
    env_content = f"""# Kite Connect API Credentials
API_KEY={API_KEY}
API_SECRET={API_SECRET}
ACCESS_TOKEN={access_token}

# Trading Configuration
CAPITAL_PER_TRADE=50000
MAX_TRADES_PER_DAY=2
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ .env file updated successfully!")
    print()
    print("="*70)
    print("🎉 SETUP COMPLETE!")
    print("="*70)
    print()
    print("You can now run the trading bot:")
    print("   python main.py")
    print()
    print("⚠️  Note: Access tokens expire daily. Run this script again tomorrow.")
    print()
    
except Exception as e:
    print(f"❌ Error generating access token: {e}")
    print()
    print("Common issues:")
    print("  • Request token expired (they expire in few minutes)")
    print("  • API credentials incorrect")
    print("  • Network connectivity issue")
    print()
    print("Please try running the script again.")

