#!/usr/bin/env python3
"""
Automated Zerodha Kite Login via TOTP
─────────────────────────────────────
Generates a fresh access_token without any browser or manual interaction.

Flow:
  1. POST /api/login          → user_id + password → request_id
  2. POST /api/twofa          → user_id + request_id + TOTP → request_token (via redirect)
  3. kite.generate_session()  → access_token
  4. Surgical .env update     → only ACCESS_TOKEN line replaced

Required .env variables:
  KITE_USER_ID, KITE_PASSWORD, TOTP_SECRET, API_KEY, API_SECRET
"""

import os
import sys
import time
import requests
import pyotp
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs
from kiteconnect import KiteConnect

# ── Load config ──────────────────────────────────────────────────────
load_dotenv()

API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
KITE_USER_ID = os.getenv('KITE_USER_ID')
KITE_PASSWORD = os.getenv('KITE_PASSWORD')
TOTP_SECRET = os.getenv('TOTP_SECRET')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '.env')


def validate_config():
    """Ensure all required credentials are present."""
    missing = []
    for name, val in [('API_KEY', API_KEY), ('API_SECRET', API_SECRET),
                      ('KITE_USER_ID', KITE_USER_ID), ('KITE_PASSWORD', KITE_PASSWORD),
                      ('TOTP_SECRET', TOTP_SECRET)]:
        if not val:
            missing.append(name)
    if missing:
        print(f"❌ Missing .env variables: {', '.join(missing)}")
        sys.exit(1)


def step1_login(session: requests.Session) -> str:
    """
    POST login credentials → get request_id for 2FA.
    """
    print("🔑 Step 1: Logging in with user_id + password...")

    resp = session.post(
        "https://kite.zerodha.com/api/login",
        data={
            "user_id": KITE_USER_ID,
            "password": KITE_PASSWORD,
        },
    )

    data = resp.json()

    if data.get("status") != "success":
        print(f"❌ Login failed: {data.get('message', data)}")
        sys.exit(1)

    request_id = data["data"]["request_id"]
    print(f"   ✅ Login OK — request_id: {request_id[:12]}...")
    return request_id


def step2_twofa(session: requests.Session, request_id: str) -> str:
    """
    POST TOTP code → get request_token from redirect URL.
    """
    print("🔐 Step 2: Submitting TOTP code...")

    totp = pyotp.TOTP(TOTP_SECRET)
    twofa_value = totp.now()
    print(f"   TOTP code: {twofa_value}")

    resp = session.post(
        "https://kite.zerodha.com/api/twofa",
        data={
            "user_id": KITE_USER_ID,
            "request_id": request_id,
            "twofa_value": twofa_value,
            "twofa_type": "totp",
        },
    )

    data = resp.json()

    if data.get("status") != "success":
        # If TOTP was generated at the tail end of its 30s window,
        # retry once with the next code after a short wait
        print(f"   ⚠️  TOTP rejected, waiting for next code...")
        time.sleep(5)
        twofa_value = totp.now()
        print(f"   Retry TOTP code: {twofa_value}")
        resp = session.post(
            "https://kite.zerodha.com/api/twofa",
            data={
                "user_id": KITE_USER_ID,
                "request_id": request_id,
                "twofa_value": twofa_value,
                "twofa_type": "totp",
            },
        )
        data = resp.json()
        if data.get("status") != "success":
            print(f"❌ 2FA failed: {data.get('message', data)}")
            sys.exit(1)

    print("   ✅ 2FA OK")

    # Now fetch the Kite Connect login URL which will redirect with request_token
    # Flow: /connect/login → /connect/finish?sess_id=X → callback?request_token=X
    print("🔗 Step 2b: Fetching request_token from Kite Connect...")

    login_url = f"https://kite.zerodha.com/connect/login?api_key={API_KEY}&v=3"
    resp = session.get(login_url, allow_redirects=False)

    redirect_url = ""
    if resp.status_code in (301, 302, 303):
        redirect_url = resp.headers.get("Location", "")

    # If we got /connect/finish?sess_id=X, follow it to get request_token
    if "connect/finish" in redirect_url and "request_token" not in redirect_url:
        print(f"   Following finish redirect...")
        # Make the redirect URL absolute if needed
        if redirect_url.startswith("/"):
            redirect_url = f"https://kite.zerodha.com{redirect_url}"
        resp = session.get(redirect_url, allow_redirects=False)
        if resp.status_code in (301, 302, 303):
            redirect_url = resp.headers.get("Location", "")

    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)

    request_token = params.get("request_token", [None])[0]

    if not request_token:
        print(f"❌ Could not extract request_token from redirect")
        print(f"   Redirect URL: {redirect_url}")
        sys.exit(1)

    print(f"   ✅ request_token: {request_token[:12]}...")
    return request_token


def step3_generate_session(request_token: str) -> str:
    """
    Exchange request_token for access_token via Kite Connect API.
    """
    print("🔄 Step 3: Generating access token...")

    kite = KiteConnect(api_key=API_KEY)
    session_data = kite.generate_session(request_token, api_secret=API_SECRET)
    access_token = session_data["access_token"]

    # Verify it works
    kite.set_access_token(access_token)
    profile = kite.profile()

    print(f"   ✅ Access token generated for: {profile['user_name']}")
    print(f"   Token: {access_token[:12]}...")
    return access_token


def step4_update_env(access_token: str):
    """
    Surgically update ONLY the ACCESS_TOKEN line in .env.
    All other settings (MAX_LOTS, TOTP_SECRET, etc.) are preserved.
    """
    print("💾 Step 4: Updating .env file...")

    try:
        with open(ENV_PATH, 'r') as f:
            lines = f.readlines()

        token_found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith('ACCESS_TOKEN='):
                new_lines.append(f'ACCESS_TOKEN={access_token}\n')
                token_found = True
            else:
                new_lines.append(line)

        # If ACCESS_TOKEN line didn't exist, add it after API_SECRET
        if not token_found:
            final_lines = []
            for line in new_lines:
                final_lines.append(line)
                if line.strip().startswith('API_SECRET='):
                    final_lines.append(f'ACCESS_TOKEN={access_token}\n')
            new_lines = final_lines

        with open(ENV_PATH, 'w') as f:
            f.writelines(new_lines)

        print("   ✅ .env updated (ACCESS_TOKEN only — all settings preserved)")
    except Exception as e:
        print(f"   ❌ Failed to update .env: {e}")
        print(f"   Manually set: ACCESS_TOKEN={access_token}")
        sys.exit(1)


def main():
    print()
    print("=" * 60)
    print("🤖 AUTOMATED KITE LOGIN (TOTP)")
    print("=" * 60)
    print()

    validate_config()

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "X-Kite-Version": "3",
    })

    request_id = step1_login(session)
    request_token = step2_twofa(session, request_id)
    access_token = step3_generate_session(request_token)
    step4_update_env(access_token)

    print()
    print("=" * 60)
    print("🎉 AUTO-LOGIN COMPLETE — Token is ready!")
    print("=" * 60)
    print()

    return access_token


if __name__ == "__main__":
    main()
