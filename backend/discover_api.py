"""Discover the correct MyScheme.gov.in API endpoints."""
import requests
import re
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
}

# Step 1: Try known API patterns
print("=== Testing API endpoints ===")
urls = [
    "https://www.myscheme.gov.in/api/v1/schemes?page=1&per_page=10",
    "https://www.myscheme.gov.in/api/schemes?page=1",
    "https://api.myscheme.gov.in/v1/schemes",
    "https://www.myscheme.gov.in/api/v1/search?keyword=&page=1",
]

for url in urls:
    try:
        r = requests.get(url, headers=headers, timeout=10, verify=False, allow_redirects=True)
        ct = r.headers.get("content-type", "")
        print(f"{r.status_code} | {ct[:30]:30s} | {url}")
        if r.status_code == 200 and "json" in ct:
            data = r.json()
            print(f"  Keys: {list(data.keys())[:10]}")
            print(f"  Preview: {str(data)[:300]}")
    except Exception as e:
        print(f"ERR  | {url}: {type(e).__name__}")

# Step 2: Fetch the search page and find API endpoints in the HTML/JS
print("\n=== Analyzing search page HTML ===")
try:
    r = requests.get("https://www.myscheme.gov.in/search", headers=headers, timeout=15, verify=False)
    text = r.text
    
    # Find all script src URLs
    scripts = re.findall(r'src=["\']([^"\']+(?:\.js|chunk)[^"\']*)["\']', text)
    print(f"Scripts found: {len(scripts)}")
    for s in scripts[:10]:
        print(f"  {s}")
    
    # Find any _next/data or API patterns
    api_patterns = re.findall(r'["\'](/(?:api|_next/data|v1|v2)[^"\']*)["\']', text)
    print(f"\nAPI patterns in HTML: {len(api_patterns)}")
    for p in set(api_patterns[:20]):
        print(f"  {p}")
    
    # Look for __NEXT_DATA__ (Next.js apps embed initial data)
    next_data = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*;?\s*</script>', text, re.DOTALL)
    if next_data:
        try:
            nd = json.loads(next_data.group(1))
            print(f"\n__NEXT_DATA__ found! Top keys: {list(nd.keys())}")
            if "props" in nd:
                print(f"  props keys: {list(nd['props'].keys())[:5]}")
                if "pageProps" in nd.get("props", {}):
                    pp = nd["props"]["pageProps"]
                    print(f"  pageProps keys: {list(pp.keys())[:10]}")
                    # Check for scheme data
                    for key in pp:
                        val = pp[key]
                        if isinstance(val, list) and len(val) > 0:
                            print(f"  pageProps.{key}: list of {len(val)} items")
                            if isinstance(val[0], dict):
                                print(f"    First item keys: {list(val[0].keys())[:10]}")
                                print(f"    First item preview: {str(val[0])[:300]}")
                        elif isinstance(val, dict):
                            print(f"  pageProps.{key}: dict with keys {list(val.keys())[:10]}")
        except json.JSONDecodeError as e:
            print(f"  Failed to parse __NEXT_DATA__: {e}")
    else:
        print("\nNo __NEXT_DATA__ found (not a Next.js app or SSR)")
    
    # Look for fetch/axios API calls in inline scripts
    inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', text, re.DOTALL)
    for script in inline_scripts:
        if len(script) > 50:
            fetches = re.findall(r'fetch\s*\(\s*["\']([^"\']+)["\']', script)
            if fetches:
                print(f"\nfetch() calls found: {fetches[:5]}")
            axios_calls = re.findall(r'axios\.\w+\s*\(\s*["\']([^"\']+)["\']', script)
            if axios_calls:
                print(f"axios calls found: {axios_calls[:5]}")

except Exception as e:
    print(f"Failed: {e}")

# Step 3: Try Next.js data route  
print("\n=== Testing Next.js _next/data routes ===")
try:
    # First get the build ID
    r = requests.get("https://www.myscheme.gov.in/search", headers=headers, timeout=15, verify=False)
    build_id_match = re.search(r'"buildId"\s*:\s*"([^"]+)"', r.text)
    if build_id_match:
        build_id = build_id_match.group(1)
        print(f"Build ID: {build_id}")
        
        # Try Next.js data route
        next_url = f"https://www.myscheme.gov.in/_next/data/{build_id}/search.json"
        r2 = requests.get(next_url, headers=headers, timeout=15, verify=False)
        print(f"Next.js data route: {r2.status_code}")
        if r2.status_code == 200:
            data = r2.json()
            print(f"Keys: {list(data.keys())}")
            if "pageProps" in data:
                print(f"pageProps keys: {list(data['pageProps'].keys())[:10]}")
    else:
        print("No build ID found")
except Exception as e:
    print(f"Next.js data route failed: {e}")

# Step 4: Try individual scheme page
print("\n=== Testing individual scheme page ===")
try:
    r = requests.get("https://www.myscheme.gov.in/schemes/pradhan-mantri-jan-dhan-yojana", 
                     headers=headers, timeout=15, verify=False)
    print(f"Status: {r.status_code}")
    
    next_data = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*;?\s*</script>', r.text, re.DOTALL)
    if next_data:
        nd = json.loads(next_data.group(1))
        if "props" in nd and "pageProps" in nd["props"]:
            pp = nd["props"]["pageProps"]
            print(f"pageProps keys: {list(pp.keys())[:15]}")
            for key in pp:
                val = pp[key]
                if isinstance(val, str) and len(val) > 10:
                    print(f"  {key}: {val[:150]}...")
                elif isinstance(val, dict):
                    print(f"  {key} (dict): {list(val.keys())[:10]}")
                elif isinstance(val, list):
                    print(f"  {key} (list): {len(val)} items")
except Exception as e:
    print(f"Failed: {e}")
