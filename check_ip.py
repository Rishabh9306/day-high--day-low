#!/usr/bin/env python3
"""
IP Checker for Kite Developer Console

Detects your current public IP (IPv4 + IPv6) and helps you whitelist it.
Since Cloudflare WARP changes your exit IP, run this daily before starting the bot.

Kite's developer console has no API — you must update IPs manually via the web UI.
This script makes it easy by detecting your current IP and opening the console.
"""

import urllib.request
import json
import webbrowser
import subprocess
import sys


def get_public_ipv4():
    """Get current public IPv4 address"""
    services = [
        "https://api.ipify.org?format=json",
        "https://ipv4.icanhazip.com",
        "https://checkip.amazonaws.com",
    ]
    for url in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode().strip()
                if "json" in url:
                    return json.loads(data).get("ip", data)
                return data
        except Exception:
            continue
    return None


def get_public_ipv6():
    """Get current public IPv6 address"""
    services = [
        "https://api64.ipify.org?format=json",
        "https://ipv6.icanhazip.com",
    ]
    for url in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode().strip()
                if "json" in url:
                    ip = json.loads(data).get("ip", data)
                else:
                    ip = data
                # Only return if it's actually IPv6
                if ":" in ip:
                    return ip
        except Exception:
            continue
    return None


def check_warp_status():
    """Check if Cloudflare WARP is active"""
    try:
        result = subprocess.run(
            ["warp-cli", "status"],
            capture_output=True, text=True, timeout=5
        )
        return "Connected" in result.stdout
    except Exception:
        # Check if WARP interface exists
        try:
            result = subprocess.run(
                ["ip", "link", "show", "CloudflareWARP"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False


def main():
    print("=" * 70)
    print("🔍 KITE IP WHITELIST CHECKER")
    print("=" * 70)
    print()

    # Check WARP status
    warp_active = check_warp_status()
    if warp_active:
        print("⚠️  Cloudflare WARP is ACTIVE — your exit IP will be a WARP IP")
        print("   WARP IPs change frequently. Consider disconnecting WARP")
        print("   before running the bot for a stable IP.")
        print()

    # Get public IPs
    print("🌐 Detecting your current public IPs...")
    print()

    ipv4 = get_public_ipv4()
    ipv6 = get_public_ipv6()

    ips_to_whitelist = []

    if ipv4:
        print(f"   IPv4: {ipv4}")
        ips_to_whitelist.append(ipv4)
    else:
        print("   IPv4: Not detected")

    if ipv6:
        print(f"   IPv6: {ipv6}")
        ips_to_whitelist.append(ipv6)
    else:
        print("   IPv6: Not detected")

    print()
    print("=" * 70)
    print("📋 ADD THESE IPs TO KITE DEVELOPER CONSOLE:")
    print("=" * 70)
    print()
    for ip in ips_to_whitelist:
        print(f"   {ip}")
    print()

    if warp_active:
        print("💡 TIP: To get a stable IP, run these before starting the bot:")
        print("   warp-cli disconnect")
        print("   # Then re-run this script to get your real IP")
        print()

    print("=" * 70)
    print("🔗 Opening Kite Developer Console...")
    print("   https://developers.kite.trade")
    print("=" * 70)
    print()
    print("Steps:")
    print("  1. Login to the developer console")
    print("  2. Click on your app")
    print("  3. Paste the IPs above into 'Allowed IPs' field")
    print("  4. Save")
    print()

    # Ask if user wants to open the browser
    if "--no-browser" not in sys.argv:
        try:
            webbrowser.open("https://developers.kite.trade")
            print("✅ Browser opened!")
        except Exception:
            print("⚠️  Could not open browser. Please open the URL manually.")

    print()
    print("After updating IPs, run the token validity check:")
    print("  .venv/bin/python -c \"import config; from kiteconnect import KiteConnect; "
          "kite = KiteConnect(api_key=config.API_KEY); "
          "kite.set_access_token(config.ACCESS_TOKEN); "
          "print('✅ Token valid:', kite.profile()['user_name'])\"")


if __name__ == "__main__":
    main()
