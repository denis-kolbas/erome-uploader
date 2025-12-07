#!/usr/bin/env python3
"""
Simple script to test proxy connection
"""
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

PROXY_HOST = os.getenv("PROXY_HOST", "p.webshare.io")
PROXY_PORT = os.getenv("PROXY_PORT", "80")
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "mhcbvnkx-rotate")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "wsramyu1qzh0")

print("="*60)
print("Proxy Connection Test")
print("="*60)
print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}")
print(f"Username: {PROXY_USERNAME}")
print("="*60 + "\n")

with sync_playwright() as p:
    # Test WITHOUT proxy first
    print("1. Testing WITHOUT proxy...")
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    try:
        page.goto('https://api.ipify.org?format=json', wait_until='networkidle', timeout=10000)
        ip_json = page.content()
        print(f"   Response: {ip_json}")
        
        page.goto('https://ifconfig.me/ip', wait_until='networkidle', timeout=10000)
        direct_ip = page.locator('body').text_content().strip()
        print(f"   ✓ Your direct IP: {direct_ip}\n")
    except Exception as e:
        print(f"   ✗ Error: {e}\n")
    
    context.close()
    browser.close()
    
    # Test WITH proxy
    print("2. Testing WITH proxy...")
    proxy_config = {
        'server': f'http://{PROXY_HOST}:{PROXY_PORT}',
        'username': PROXY_USERNAME,
        'password': PROXY_PASSWORD
    }
    
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(proxy=proxy_config)
    page = context.new_page()
    
    try:
        page.goto('https://api.ipify.org?format=json', wait_until='networkidle', timeout=15000)
        ip_json = page.content()
        print(f"   Response: {ip_json}")
        
        page.goto('https://ifconfig.me/ip', wait_until='networkidle', timeout=15000)
        proxy_ip = page.locator('body').text_content().strip()
        print(f"   ✓ Proxy IP: {proxy_ip}\n")
        
        if direct_ip != proxy_ip:
            print("="*60)
            print("✓ SUCCESS! Proxy is working correctly")
            print(f"   Direct IP: {direct_ip}")
            print(f"   Proxy IP:  {proxy_ip}")
            print("="*60)
        else:
            print("="*60)
            print("⚠️ WARNING! IPs are the same - proxy might not be working")
            print("="*60)
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("\n" + "="*60)
        print("✗ FAILED! Could not connect through proxy")
        print("="*60)
        print("\nPossible issues:")
        print("- Proxy credentials are incorrect")
        print("- Proxy server is down")
        print("- Network connectivity issues")
    
    context.close()
    browser.close()
