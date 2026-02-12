#!/usr/bin/env python3
"""Test browser connection and Cloudflare warmup."""
import asyncio
from scraper.browser import launch_browser, warmup_cloudflare

async def test():
    print("Testing browser launch...")
    page = await launch_browser()
    print("✓ Browser launched")
    
    print("\nTesting Cloudflare warmup...")
    await warmup_cloudflare(page)
    print("✓ Warmup complete")
    
    print("\nBrowser test passed! Press Ctrl+C to close.")
    await asyncio.sleep(300)  # Keep open for 5 minutes

if __name__ == "__main__":
    asyncio.run(test())
