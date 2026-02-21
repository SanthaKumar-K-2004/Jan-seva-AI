"""
Jan-Seva AI — MyScheme.gov.in Bulk Scraper + NVIDIA Enrichment
================================================================
Comprehensive scraper that:
  1. Fetches ALL schemes from MyScheme.gov.in API (paginated)
  2. Scrapes individual scheme detail pages for deep data
  3. Uses NVIDIA Qwen 3.5 to extract structured eligibility info
  4. Stores everything in Supabase with rich embeddings
  
Usage:
  python -m app.services.scraper.myscheme_bulk_scraper
  python -m app.services.scraper.myscheme_bulk_scraper --enrich-only
  python -m app.services.scraper.myscheme_bulk_scraper --limit 50
"""

import re
import json
import time
import asyncio
import argparse
import requests
from typing import Optional
from datetime import datetime

from app.core.supabase_client import get_supabase_client
from app.core.embedding_client import get_embedding_client
from app.utils.logger import logger

# ═══════════════════════════════════════════════════
# MyScheme.gov.in API Configuration
# ═══════════════════════════════════════════════════

MYSCHEME_API = "https://www.myscheme.gov.in/api/v1/schemes"
MYSCHEME_SEARCH_API = "https://www.myscheme.gov.in/api/v1/search"
MYSCHEME_DETAIL_API = "https://www.myscheme.gov.in/api/v1/schemes/{slug}"
MYSCHEME_BASE_URL = "https://www.myscheme.gov.in"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.myscheme.gov.in/search",
    "Origin": "https://www.myscheme.gov.in",
}


def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from scheme name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug[:100]


# ═══════════════════════════════════════════════════
# Step 1: Fetch ALL scheme URLs from MyScheme
# ═══════════════════════════════════════════════════

def fetch_scheme_list_from_api(limit: int = 5000) -> list[dict]:
    """
    Fetch scheme list from MyScheme.gov.in API with pagination.
    Returns list of basic scheme info dicts.
    """
    all_schemes = []
    page = 1
    per_page = 50
    
    logger.info("Fetching scheme list from MyScheme.gov.in API...")
    
    while len(all_schemes) < limit:
        try:
            # Try multiple API endpoint patterns
            urls_to_try = [
                f"{MYSCHEME_API}?page={page}&per_page={per_page}",
                f"{MYSCHEME_SEARCH_API}?page={page}&per_page={per_page}&keyword=",
                f"{MYSCHEME_BASE_URL}/api/v1/search?page={page}&per_page={per_page}",
            ]
            
            data = None
            for url in urls_to_try:
                try:
                    resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)
                    if resp.status_code == 200:
                        data = resp.json()
                        break
                except Exception:
                    continue
            
            if not data:
                logger.warning(f"No API endpoint responded on page {page}")
                break
            
            # Handle different response structures
            schemes = (
                data.get("data", []) or
                data.get("schemes", []) or
                data.get("results", []) or
                []
            )
            
            if not schemes:
                logger.info(f"No more schemes on page {page}. Total fetched: {len(all_schemes)}")
                break
            
            all_schemes.extend(schemes)
            logger.info(f"  Page {page}: got {len(schemes)} schemes (total: {len(all_schemes)})")
            
            page += 1
            time.sleep(1.5)  # Rate limiting
            
            # Safety cap
            if page > 100:
                break
                
        except Exception as e:
            logger.error(f"Failed to fetch page {page}: {e}")
            break
    
    logger.info(f"Total schemes fetched from API: {len(all_schemes)}")
    return all_schemes


# ═══════════════════════════════════════════════════
# Step 2: Scrape individual scheme detail pages
# ═══════════════════════════════════════════════════

def scrape_scheme_detail_page(scheme_url: str) -> dict:
    """
    Scrape a single scheme detail page from MyScheme.gov.in.
    Extracts the full text content for enrichment.
    """
    try:
        from bs4 import BeautifulSoup
        
        resp = requests.get(scheme_url, headers=HEADERS, timeout=20, verify=False)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove script, style, nav, footer elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        
        # Extract main content
        content = soup.get_text(separator="\n", strip=True)
        
        # Try to find structured sections
        details = {
            "full_text": content[:5000],  # Cap at 5000 chars
        }
        
        # Look for common section patterns
        section_patterns = {
            "benefits": r"(?:benefits?|advantages?|incentives?)\s*[:—-]\s*(.+?)(?=\n\n|\Z)",
            "eligibility": r"(?:eligibility|who can apply|criteria)\s*[:—-]\s*(.+?)(?=\n\n|\Z)",
            "application_process": r"(?:how to apply|application process|steps)\s*[:—-]\s*(.+?)(?=\n\n|\Z)",
            "documents": r"(?:documents? required|papers needed)\s*[:—-]\s*(.+?)(?=\n\n|\Z)",
        }
        
        for key, pattern in section_patterns.items():
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                details[key] = match.group(1).strip()[:1000]
        
        return details
        
    except Exception as e:
        logger.warning(f"Failed to scrape detail page {scheme_url}: {e}")
        return {}


# ═══════════════════════════════════════════════════
# Step 3: Parse API response into our schema
# ═══════════════════════════════════════════════════

def parse_myscheme_entry(raw: dict) -> Optional[dict]:
    """Parse a single MyScheme API entry into our scheme format."""
    try:
        name = (
            raw.get("schemeName") or
            raw.get("title") or
            raw.get("name") or
            raw.get("scheme_name") or
            ""
        )
        if not name or len(name) < 3:
            return None
        
        # Extract state from tags/metadata
        state = raw.get("state", raw.get("level", "Central"))
        if state in ("Central", "central", "National", "All India", ""):
            state = "Central"
        
        # Extract categories
        categories = raw.get("categories", raw.get("tags", raw.get("category", [])))
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(",") if c.strip()]
        
        # Build description
        description = (
            raw.get("schemeDescription") or
            raw.get("description") or
            raw.get("brief") or
            raw.get("details") or
            ""
        )
        
        # Extract benefits
        benefits = raw.get("benefits") or raw.get("schemeBenefits") or ""
        if isinstance(benefits, list):
            benefits = "; ".join(str(b) for b in benefits)
        
        # Extract eligibility
        eligibility = raw.get("eligibility") or raw.get("eligibilityCriteria") or ""
        if isinstance(eligibility, list):
            eligibility = "; ".join(str(e) for e in eligibility)
        
        # Extract documents
        docs = raw.get("documentsRequired") or raw.get("documents_required") or []
        if isinstance(docs, str):
            docs = [d.strip() for d in docs.split(",") if d.strip()]
        
        # Extract application process
        how_to_apply = raw.get("howToApply") or raw.get("applicationProcess") or ""
        if isinstance(how_to_apply, list):
            how_to_apply = " → ".join(str(s) for s in how_to_apply)
        
        # Build source URL
        slug = raw.get("slug") or generate_slug(name)
        source_url = raw.get("schemeUrl") or raw.get("url") or f"{MYSCHEME_BASE_URL}/schemes/{slug}"
        
        return {
            "name": name.strip(),
            "slug": slug,
            "description": description[:2000],
            "ministry": raw.get("ministry") or raw.get("nodalMinistry") or "",
            "department": raw.get("department") or raw.get("nodalDepartment") or "",
            "state": state,
            "category": categories if categories else ["General"],
            "benefits": benefits[:2000],
            "documents_required": docs,
            "how_to_apply": how_to_apply[:2000],
            "application_url": raw.get("applicationUrl") or "",
            "source_url": source_url,
            "source_type": "myscheme_api",
            "eligibility": eligibility[:2000],
            "application_mode": raw.get("applicationMode") or "",
        }
        
    except Exception as e:
        logger.warning(f"Failed to parse entry: {e}")
        return None


# ═══════════════════════════════════════════════════
# Step 4: NVIDIA Qwen Deep Enrichment
# ═══════════════════════════════════════════════════

ENRICHMENT_PROMPT = """You are an expert on Indian government schemes. Given a scheme's name and description, extract structured information in JSON format.

SCHEME INFO:
Name: {name}
Description: {description}
Benefits: {benefits}
Current Eligibility: {eligibility}

Extract and return ONLY a JSON object with these fields (use null if unknown):
{{
  "eligibility_summary": "Clear 1-2 line eligibility criteria",
  "income_limit": "e.g., Rs. 2,00,000/year or null",
  "age_range": "e.g., 18-60 years or null",
  "eligible_categories": ["SC", "ST", "OBC", "General", etc.],
  "eligible_states": ["Tamil Nadu", "All States", etc.],
  "benefit_amount": "e.g., Rs. 50,000/year or Full tuition fee",
  "application_portal": "Official URL if known, or null",
  "documents_needed": ["Aadhaar", "Income Certificate", etc.],
  "application_steps": ["Step 1: Visit portal", "Step 2: Register", etc.],
  "sector": "Education/Healthcare/Agriculture/Housing/etc.",
  "target_group": "e.g., Women, Farmers, Students, Senior Citizens"
}}

Return ONLY valid JSON, no explanation."""


async def enrich_scheme_with_nvidia(scheme: dict) -> dict:
    """Use NVIDIA Qwen to extract structured data from scheme description."""
    try:
        from app.core.nvidia_client import get_nvidia_client
        nvidia = get_nvidia_client()
        
        prompt = ENRICHMENT_PROMPT.format(
            name=scheme.get("name", ""),
            description=scheme.get("description", "")[:1500],
            benefits=scheme.get("benefits", "")[:500],
            eligibility=scheme.get("eligibility", "")[:500],
        )
        
        result = await nvidia.generate(
            system="You are a government scheme data extraction assistant. Return ONLY valid JSON.",
            user_query=prompt,
            temperature=0.2,
        )
        
        # Parse JSON from response
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result, re.DOTALL)
        if json_match:
            enriched = json.loads(json_match.group())
            return enriched
        else:
            logger.warning(f"No JSON found in NVIDIA response for {scheme['name']}")
            return {}
            
    except Exception as e:
        logger.warning(f"NVIDIA enrichment failed for {scheme.get('name', '?')}: {e}")
        return {}


# ═══════════════════════════════════════════════════
# Step 5: Store in Supabase with Embeddings
# ═══════════════════════════════════════════════════

def upsert_scheme_to_db(scheme_data: dict) -> Optional[str]:
    """Insert or update a scheme in the database. Returns scheme ID."""
    client = get_supabase_client()
    slug = scheme_data.get("slug", "")
    
    if not slug:
        return None
    
    try:
        # Check if exists
        existing = client.table("schemes").select("id").eq("slug", slug).execute()
        
        if existing.data:
            scheme_id = existing.data[0]["id"]
            # Update with new data (don't overwrite with empty values)
            update_fields = {}
            for key, value in scheme_data.items():
                if value and key not in ("slug",):  # Don't update slug
                    update_fields[key] = value
            if update_fields:
                client.table("schemes").update(update_fields).eq("id", scheme_id).execute()
            return scheme_id
        else:
            # Insert new
            result = client.table("schemes").insert(scheme_data).execute()
            return result.data[0]["id"] if result.data else None
            
    except Exception as e:
        logger.error(f"DB upsert failed for '{scheme_data.get('name', '?')}': {e}")
        return None


def generate_and_store_embedding(scheme_id: str, scheme: dict, embedder):
    """Generate rich embedding text and store in scheme_embeddings table."""
    client = get_supabase_client()
    
    # Build comprehensive embedding text
    parts = [
        f"{scheme['name']}.",
        scheme.get("description", ""),
        f"Benefits: {scheme.get('benefits', '')}.",
    ]
    
    if scheme.get("category"):
        cats = scheme["category"]
        if isinstance(cats, list):
            cats = ", ".join(cats)
        parts.append(f"Category: {cats}.")
    
    parts.append(f"State: {scheme.get('state', 'Central')}.")
    parts.append(f"Ministry: {scheme.get('ministry', '')}.")
    
    if scheme.get("eligibility"):
        parts.append(f"Eligibility: {scheme['eligibility']}.")
    if scheme.get("source_url"):
        parts.append(f"Apply at: {scheme['source_url']}.")
    if scheme.get("application_mode"):
        parts.append(f"Application mode: {scheme['application_mode']}.")
    if scheme.get("documents_required"):
        docs = scheme["documents_required"]
        if isinstance(docs, list):
            docs = ", ".join(docs)
        parts.append(f"Documents: {docs}.")
    if scheme.get("how_to_apply"):
        parts.append(f"How to apply: {scheme['how_to_apply']}.")
    
    embed_text = " ".join(p for p in parts if p)
    
    # Cap at reasonable length for embedding model
    embed_text = embed_text[:2000]
    
    try:
        # Delete old embeddings
        try:
            client.table("scheme_embeddings").delete().eq("scheme_id", scheme_id).execute()
        except Exception:
            pass
        
        embedding = embedder.embed_text(embed_text)
        
        client.table("scheme_embeddings").insert({
            "scheme_id": scheme_id,
            "chunk_text": embed_text,
            "chunk_index": 0,
            "embedding": embedding,
            "metadata": {
                "source": "myscheme_bulk_scraper",
                "scraped_at": datetime.utcnow().isoformat(),
            },
        }).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"Embedding storage failed for scheme {scheme_id}: {e}")
        return False


# ═══════════════════════════════════════════════════
# Step 6: Alternative - Scrape Individual Pages
# ═══════════════════════════════════════════════════

def scrape_scheme_page_directly(url: str) -> Optional[dict]:
    """
    Scrape a single MyScheme.gov.in scheme page and extract structured data.
    This is the fallback if the API doesn't return good data.
    """
    try:
        from bs4 import BeautifulSoup
        
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Try to extract from structured data (JSON-LD)
        json_ld = soup.find("script", type="application/ld+json")
        if json_ld:
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, dict) and data.get("name"):
                    return parse_myscheme_entry(data)
            except json.JSONDecodeError:
                pass
        
        # Extract from page content
        title_el = soup.find("h1") or soup.find("h2")
        title = title_el.get_text(strip=True) if title_el else ""
        
        if not title:
            return None
        
        # Get main content area
        main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile("content|scheme|detail", re.I))
        content = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)
        
        return {
            "name": title,
            "slug": generate_slug(title),
            "description": content[:2000],
            "source_url": url,
            "source_type": "myscheme_scraped",
            "state": "Central",
            "category": ["General"],
        }
        
    except Exception as e:
        logger.warning(f"Page scrape failed for {url}: {e}")
        return None


# ═══════════════════════════════════════════════════
# Main Orchestrator
# ═══════════════════════════════════════════════════

async def run_bulk_scrape(limit: int = 5000, enrich: bool = True, enrich_only: bool = False):
    """
    Main function: Fetch, parse, enrich, and store all MyScheme schemes.
    """
    client = get_supabase_client()
    embedder = get_embedding_client()
    
    stats = {
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "enriched": 0,
        "embedded": 0,
        "errors": 0,
    }
    
    if enrich_only:
        # Only enrich existing schemes that lack eligibility data
        logger.info("Running enrichment-only mode...")
        result = client.table("schemes").select("id, name, description, benefits, eligibility").is_("eligibility", "null").limit(limit).execute()
        schemes_to_enrich = result.data or []
        logger.info(f"Found {len(schemes_to_enrich)} schemes needing enrichment")
        
        for i, scheme in enumerate(schemes_to_enrich):
            enriched = await enrich_scheme_with_nvidia(scheme)
            if enriched:
                update_fields = {}
                if enriched.get("eligibility_summary"):
                    update_fields["eligibility"] = enriched["eligibility_summary"]
                if enriched.get("application_portal"):
                    update_fields["source_url"] = enriched["application_portal"]
                if enriched.get("application_steps"):
                    update_fields["application_mode"] = " → ".join(enriched["application_steps"])
                if enriched.get("documents_needed"):
                    update_fields["documents_required"] = enriched["documents_needed"]
                if enriched.get("income_limit"):
                    update_fields["eligibility"] = (update_fields.get("eligibility", "") + f" Income limit: {enriched['income_limit']}").strip()
                
                if update_fields:
                    try:
                        client.table("schemes").update(update_fields).eq("id", scheme["id"]).execute()
                        stats["enriched"] += 1
                        
                        # Regenerate embedding
                        # Fetch full scheme data for embedding
                        full_scheme = client.table("schemes").select("*").eq("id", scheme["id"]).execute()
                        if full_scheme.data:
                            generate_and_store_embedding(scheme["id"], full_scheme.data[0], embedder)
                            stats["embedded"] += 1
                    except Exception as e:
                        logger.error(f"Enrichment update failed for {scheme['name']}: {e}")
                        stats["errors"] += 1
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Enrichment progress: {i+1}/{len(schemes_to_enrich)} ({stats['enriched']} enriched)")
            
            # Rate limit NVIDIA API
            await asyncio.sleep(2)
        
        logger.info(f"\nEnrichment complete! Enriched: {stats['enriched']}, Errors: {stats['errors']}")
        return stats
    
    # ── Full scrape mode ──
    
    # Step 1: Fetch scheme list from API
    logger.info("=" * 60)
    logger.info("PHASE 1: Fetching scheme list from MyScheme.gov.in")
    logger.info("=" * 60)
    
    raw_schemes = fetch_scheme_list_from_api(limit=limit)
    stats["fetched"] = len(raw_schemes)
    
    if not raw_schemes:
        logger.warning("API returned no schemes. Trying alternative approach...")
        # Fallback: try fetching the search page and extracting schemes
        try:
            resp = requests.get(
                f"{MYSCHEME_BASE_URL}/search",
                headers=HEADERS,
                timeout=30,
                verify=False,
            )
            # Try to extract scheme data from the search page HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Look for scheme links
            scheme_links = soup.find_all("a", href=re.compile(r"/schemes/"))
            for link in scheme_links:
                href = link.get("href", "")
                if href.startswith("/schemes/"):
                    full_url = f"{MYSCHEME_BASE_URL}{href}"
                    scheme_data = scrape_scheme_page_directly(full_url)
                    if scheme_data:
                        raw_schemes.append(scheme_data)
                        time.sleep(1.5)
            
            logger.info(f"Scraped {len(raw_schemes)} schemes from search page fallback")
        except Exception as e:
            logger.error(f"Search page fallback also failed: {e}")
    
    # Step 2: Parse and store each scheme
    logger.info("=" * 60)
    logger.info("PHASE 2: Parsing and storing schemes")
    logger.info("=" * 60)
    
    for i, raw in enumerate(raw_schemes):
        # Parse into our format
        if isinstance(raw, dict) and raw.get("name"):
            scheme = raw  # Already parsed (from fallback)
        else:
            scheme = parse_myscheme_entry(raw)
        
        if not scheme:
            stats["errors"] += 1
            continue
        
        # Upsert to DB
        scheme_id = upsert_scheme_to_db(scheme)
        if scheme_id:
            # Check if it was insert or update
            existing = client.table("schemes").select("created_at, updated_at").eq("id", scheme_id).execute()
            if existing.data:
                created = existing.data[0].get("created_at", "")
                updated = existing.data[0].get("updated_at", "")
                if created == updated:
                    stats["inserted"] += 1
                else:
                    stats["updated"] += 1
            
            # Generate embedding
            if generate_and_store_embedding(scheme_id, scheme, embedder):
                stats["embedded"] += 1
        else:
            stats["errors"] += 1
        
        if (i + 1) % 20 == 0:
            logger.info(f"  Progress: {i+1}/{len(raw_schemes)} processed | "
                       f"Inserted: {stats['inserted']} | Updated: {stats['updated']} | Errors: {stats['errors']}")
    
    # Step 3: NVIDIA Enrichment (if enabled)
    if enrich:
        logger.info("=" * 60)
        logger.info("PHASE 3: NVIDIA Qwen enrichment for schemes lacking details")
        logger.info("=" * 60)
        
        # Find schemes with missing eligibility
        result = client.table("schemes").select("id, name, description, benefits, eligibility").is_("eligibility", "null").limit(100).execute()
        schemes_to_enrich = result.data or []
        logger.info(f"Found {len(schemes_to_enrich)} schemes needing enrichment")
        
        for i, scheme in enumerate(schemes_to_enrich):
            enriched = await enrich_scheme_with_nvidia(scheme)
            if enriched:
                update_fields = {}
                if enriched.get("eligibility_summary"):
                    update_fields["eligibility"] = enriched["eligibility_summary"]
                if enriched.get("application_portal"):
                    update_fields["source_url"] = enriched["application_portal"]
                if enriched.get("documents_needed"):
                    update_fields["documents_required"] = enriched["documents_needed"]
                if enriched.get("application_steps"):
                    update_fields["application_mode"] = " → ".join(enriched["application_steps"])
                
                if update_fields:
                    try:
                        client.table("schemes").update(update_fields).eq("id", scheme["id"]).execute()
                        stats["enriched"] += 1
                        
                        # Regenerate embedding
                        full_scheme = client.table("schemes").select("*").eq("id", scheme["id"]).execute()
                        if full_scheme.data:
                            generate_and_store_embedding(scheme["id"], full_scheme.data[0], embedder)
                    except Exception as e:
                        logger.error(f"Enrichment update failed: {e}")
                        stats["errors"] += 1
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Enrichment: {i+1}/{len(schemes_to_enrich)} ({stats['enriched']} enriched)")
            
            await asyncio.sleep(2)  # Rate limit
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("BULK SCRAPE COMPLETE!")
    logger.info("=" * 60)
    logger.info(f"  Fetched from API: {stats['fetched']}")
    logger.info(f"  Inserted (new):   {stats['inserted']}")
    logger.info(f"  Updated:          {stats['updated']}")
    logger.info(f"  Enriched (NVIDIA): {stats['enriched']}")
    logger.info(f"  Embeddings:       {stats['embedded']}")
    logger.info(f"  Errors:           {stats['errors']}")
    
    # Count total in DB
    try:
        total = client.table("schemes").select("id", count="exact").execute()
        logger.info(f"  Total in DB:      {total.count}")
    except Exception:
        pass
    
    return stats


# ═══════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="MyScheme.gov.in Bulk Scraper")
    parser.add_argument("--limit", type=int, default=5000, help="Max schemes to fetch")
    parser.add_argument("--no-enrich", action="store_true", help="Skip NVIDIA enrichment")
    parser.add_argument("--enrich-only", action="store_true", help="Only enrich existing schemes")
    args = parser.parse_args()
    
    asyncio.run(run_bulk_scrape(
        limit=args.limit,
        enrich=not args.no_enrich,
        enrich_only=args.enrich_only,
    ))


if __name__ == "__main__":
    main()
