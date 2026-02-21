"""
Jan-Seva AI — NVIDIA Qwen-Powered Mass Scheme Generator
=========================================================
Uses NVIDIA Qwen 3.5 to generate comprehensive, structured data for
ALL Indian government schemes across every sector.

Strategy:
  1. Define ALL sectors/categories that government schemes cover
  2. For each sector × state combination, ask Qwen to list ALL schemes
  3. For each scheme, ask Qwen to provide detailed structured data
  4. Deduplicate, validate, and store in Supabase with embeddings

Usage:
  python -m app.services.scraper.nvidia_scheme_generator
  python -m app.services.scraper.nvidia_scheme_generator --sector education
  python -m app.services.scraper.nvidia_scheme_generator --state "Tamil Nadu"
  python -m app.services.scraper.nvidia_scheme_generator --enrich-existing
"""

import re
import json
import asyncio
import argparse
from datetime import datetime
from typing import Optional

from app.core.supabase_client import get_supabase_client
from app.core.embedding_client import get_embedding_client
from app.core.nvidia_client import get_nvidia_client
from app.utils.logger import logger


# ═══════════════════════════════════════════════════
# Sector and State Definitions
# ═══════════════════════════════════════════════════

SECTORS = [
    "Education & Scholarships",
    "Healthcare & Medical",
    "Agriculture & Farming",
    "Housing & Urban Development",
    "Employment & Skill Development",
    "Women & Child Welfare",
    "Social Security & Pension",
    "SC/ST/OBC Welfare",
    "Disability & Differently Abled",
    "Senior Citizens",
    "Minority Welfare",
    "Rural Development",
    "MSME & Business Support",
    "Financial Inclusion & Banking",
    "Food Security & Nutrition",
    "Environmental Protection",
    "Technology & Digital India",
    "Transportation & Infrastructure",
    "Sports & Youth Affairs",
    "Ex-Servicemen & Defence",
    "Fisheries & Animal Husbandry",
    "Water & Sanitation",
    "Energy & Renewable Energy",
    "Insurance & Risk Coverage",
    "Legal Aid & Justice",
]

STATES = [
    "Central",  # Central government schemes
    "Tamil Nadu",
    "Kerala",
    "Karnataka",
    "Andhra Pradesh",
    "Telangana",
    "Maharashtra",
    "Uttar Pradesh",
    "Bihar",
    "West Bengal",
    "Rajasthan",
    "Madhya Pradesh",
    "Gujarat",
    "Odisha",
    "Punjab",
    "Haryana",
    "Jharkhand",
    "Chhattisgarh",
    "Assam",
    "Uttarakhand",
    "Himachal Pradesh",
    "Goa",
    "Delhi",
]

# ═══════════════════════════════════════════════════
# Prompts
# ═══════════════════════════════════════════════════

LIST_SCHEMES_PROMPT = """You are an expert on Indian government schemes with deep knowledge of both well-known and obscure programs.

List ALL government schemes in the "{sector}" sector for {state}.
Include:
- Central government schemes applicable to {state}
- State-specific schemes unique to {state}
- Both popular well-known schemes AND obscure lesser-known ones
- Recently launched schemes (2023-2026)
- Legacy schemes that are still active

For EACH scheme, provide this JSON array with EXACT details:
[
  {{
    "name": "Full Official Scheme Name",
    "short_name": "Common abbreviation if any",
    "ministry": "Ministry/Department responsible",
    "type": "central" or "state",
    "launched_year": 2020,
    "still_active": true,
    "brief": "One-line description under 100 chars"
  }}
]

Return ONLY a valid JSON array. List at least 10-15 schemes if they exist. Include both well-known flagship schemes and lesser-known niche programs."""


DETAIL_SCHEME_PROMPT = """You are an Indian government scheme data extraction expert. Provide PRECISE, VERIFIED details for this scheme.

SCHEME: {name}
STATE: {state}
MINISTRY: {ministry}

Return ONLY a valid JSON object with these fields (use null if genuinely unknown):
{{
  "name": "Full official name",
  "description": "2-3 sentence description of what the scheme does",
  "benefits": "Specific benefits: amounts in INR, services provided, subsidies",
  "eligibility": "Who can apply - age, income, category, occupation requirements",
  "income_limit": "Exact income ceiling if applicable, e.g. Rs. 2,50,000/year",
  "age_range": "Age requirement, e.g. 18-60 years",
  "eligible_categories": ["General", "SC", "ST", "OBC", "BC", "MBC", "EWS"],
  "documents_required": ["Aadhaar Card", "Income Certificate", "etc"],
  "application_process": "Step-by-step how to apply",
  "application_mode": "Online/Offline/Both",
  "official_portal": "URL of official website or application portal",
  "benefit_amount": "Specific monetary benefit if applicable",
  "sector": "{sector}",
  "target_group": "Primary beneficiaries: Women/Farmers/Students/etc",
  "deadline": "Application deadline or 'Rolling/Year-round'"
}}

Be PRECISE with amounts (use Rs. or ₹), URLs, and eligibility criteria. Do NOT guess or fabricate details — use null for unknown fields."""


# ═══════════════════════════════════════════════════
# Core Functions
# ═══════════════════════════════════════════════════

def generate_slug(name: str) -> str:
    """Generate URL-friendly slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug[:100]


def extract_json_from_text(text: str):
    """Extract JSON array or object from LLM response text."""
    # Try parsing the whole text
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # Try finding JSON array
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    # Try finding JSON object
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    return None


async def list_schemes_for_sector(nvidia, sector: str, state: str) -> list[dict]:
    """Ask NVIDIA Qwen to list all schemes in a sector for a state."""
    try:
        prompt = LIST_SCHEMES_PROMPT.format(sector=sector, state=state)
        result = await nvidia.generate(
            system="You are a government scheme database. Return ONLY valid JSON arrays.",
            user_query=prompt,
            temperature=0.3,
        )
        
        schemes = extract_json_from_text(result)
        if isinstance(schemes, list):
            logger.info(f"  Found {len(schemes)} schemes for {sector} / {state}")
            return schemes
        else:
            logger.warning(f"  Invalid response for {sector} / {state}")
            return []
    except Exception as e:
        logger.error(f"  Failed to list schemes for {sector} / {state}: {e}")
        return []


async def get_scheme_details(nvidia, name: str, state: str, ministry: str, sector: str) -> Optional[dict]:
    """Ask NVIDIA Qwen for detailed scheme information."""
    try:
        prompt = DETAIL_SCHEME_PROMPT.format(
            name=name, state=state, ministry=ministry, sector=sector
        )
        result = await nvidia.generate(
            system="You are a precise government scheme data extractor. Return ONLY valid JSON.",
            user_query=prompt,
            temperature=0.2,
        )
        
        details = extract_json_from_text(result)
        if isinstance(details, dict) and details.get("name"):
            return details
        return None
    except Exception as e:
        logger.error(f"  Failed to get details for {name}: {e}")
        return None


def store_scheme(client, embedder, scheme_data: dict, state: str, sector: str) -> Optional[str]:
    """Store a scheme in the database with embedding."""
    name = scheme_data.get("name", "")
    if not name or len(name) < 3:
        return None
    
    slug = generate_slug(name)
    
    # Build the DB record
    record = {
        "name": name,
        "slug": slug,
        "description": scheme_data.get("description", ""),
        "benefits": scheme_data.get("benefits", ""),
        "eligibility": scheme_data.get("eligibility", ""),
        "income_limit": scheme_data.get("income_limit"),
        "age_range": scheme_data.get("age_range"),
        "ministry": scheme_data.get("ministry", "") or "",
        "department": scheme_data.get("department", "") or "",
        "state": state if state != "Central" else "Central",
        "sector": sector,
        "category": [sector.split(" & ")[0].strip()],
        "source_url": scheme_data.get("official_portal") or "",
        "application_mode": scheme_data.get("application_mode", ""),
        "benefit_amount": scheme_data.get("benefit_amount"),
        "application_steps": scheme_data.get("application_process", ""),
        "deadline": scheme_data.get("deadline"),
        "how_to_apply": scheme_data.get("application_process", ""),
        "source_type": "nvidia_generated",
        "enrichment_status": "enriched",
        "enriched_at": datetime.utcnow().isoformat(),
    }
    
    # Handle documents_required (must be text[] array)
    docs = scheme_data.get("documents_required", [])
    if isinstance(docs, str):
        docs = [d.strip() for d in docs.split(",") if d.strip()]
    record["documents_required"] = docs if isinstance(docs, list) else []
    
    # Handle eligible_categories
    cats = scheme_data.get("eligible_categories", [])
    if isinstance(cats, str):
        cats = [c.strip() for c in cats.split(",") if c.strip()]
    record["eligible_categories"] = cats if isinstance(cats, list) else []
    
    try:
        # Check if exists
        existing = client.table("schemes").select("id").eq("slug", slug).execute()
        
        if existing.data:
            scheme_id = existing.data[0]["id"]
            # Only update with non-empty values
            update_fields = {k: v for k, v in record.items() if v and k != "slug"}
            if update_fields:
                client.table("schemes").update(update_fields).eq("id", scheme_id).execute()
            return scheme_id
        else:
            result = client.table("schemes").insert(record).execute()
            scheme_id = result.data[0]["id"] if result.data else None
            if not scheme_id:
                return None
            
            # Generate embedding
            embed_parts = [
                f"{name}.",
                record.get("description", ""),
                f"Benefits: {record.get('benefits', '')}.",
                f"State: {record.get('state', 'Central')}.",
                f"Ministry: {record.get('ministry', '')}.",
                f"Sector: {sector}.",
            ]
            if record.get("eligibility"):
                embed_parts.append(f"Eligibility: {record['eligibility']}.")
            if record.get("source_url"):
                embed_parts.append(f"Apply at: {record['source_url']}.")
            if record.get("documents_required"):
                embed_parts.append(f"Documents: {', '.join(record['documents_required'])}.")
            
            embed_text = " ".join(p for p in embed_parts if p)[:2000]
            
            try:
                embedding = embedder.embed_text(embed_text)
                client.table("scheme_embeddings").insert({
                    "scheme_id": scheme_id,
                    "chunk_text": embed_text,
                    "chunk_index": 0,
                    "embedding": embedding,
                    "metadata": {
                        "source": "nvidia_scheme_generator",
                        "generated_at": datetime.utcnow().isoformat(),
                    },
                }).execute()
            except Exception as e:
                logger.warning(f"Embedding failed for {name}: {e}")
            
            return scheme_id
            
    except Exception as e:
        logger.error(f"DB store failed for '{name}': {e}")
        return None


# ═══════════════════════════════════════════════════
# Enrichment of Existing Schemes
# ═══════════════════════════════════════════════════

async def enrich_existing_schemes(limit: int = 100):
    """Enrich existing schemes that have missing eligibility data."""
    client = get_supabase_client()
    embedder = get_embedding_client()
    nvidia = get_nvidia_client()
    
    # Find schemes needing enrichment
    result = (
        client.table("schemes")
        .select("id, name, description, benefits, eligibility, state, ministry, sector")
        .or_("eligibility.is.null,eligibility.eq.")
        .limit(limit)
        .execute()
    )
    
    schemes = result.data or []
    logger.info(f"Found {len(schemes)} existing schemes needing enrichment")
    
    enriched_count = 0
    for i, scheme in enumerate(schemes):
        details = await get_scheme_details(
            nvidia,
            name=scheme["name"],
            state=scheme.get("state", "Central"),
            ministry=scheme.get("ministry", ""),
            sector=scheme.get("sector", "General"),
        )
        
        if details:
            update = {}
            if details.get("eligibility"):
                update["eligibility"] = details["eligibility"]
            if details.get("income_limit"):
                update["income_limit"] = details["income_limit"]
            if details.get("age_range"):
                update["age_range"] = details["age_range"]
            if details.get("benefit_amount"):
                update["benefit_amount"] = details["benefit_amount"]
            if details.get("application_process"):
                update["how_to_apply"] = details["application_process"]
                update["application_steps"] = details["application_process"]
            if details.get("application_mode"):
                update["application_mode"] = details["application_mode"]
            if details.get("official_portal"):
                update["source_url"] = details["official_portal"]
            if details.get("documents_required"):
                docs = details["documents_required"]
                if isinstance(docs, list):
                    update["documents_required"] = docs
            if details.get("eligible_categories"):
                cats = details["eligible_categories"]
                if isinstance(cats, list):
                    update["eligible_categories"] = cats
            if details.get("sector"):
                update["sector"] = details["sector"]
            if details.get("deadline"):
                update["deadline"] = details["deadline"]
            
            update["enrichment_status"] = "enriched"
            update["enriched_at"] = datetime.utcnow().isoformat()
            
            if update:
                try:
                    client.table("schemes").update(update).eq("id", scheme["id"]).execute()
                    enriched_count += 1
                    
                    # Regenerate embedding
                    full = client.table("schemes").select("*").eq("id", scheme["id"]).execute()
                    if full.data:
                        s = full.data[0]
                        embed_parts = [
                            f"{s['name']}.",
                            s.get("description", ""),
                            f"Benefits: {s.get('benefits', '')}.",
                            f"State: {s.get('state', 'Central')}.",
                            f"Eligibility: {s.get('eligibility', '')}.",
                        ]
                        embed_text = " ".join(p for p in embed_parts if p)[:2000]
                        
                        try:
                            client.table("scheme_embeddings").delete().eq("scheme_id", scheme["id"]).execute()
                        except Exception:
                            pass
                        
                        embedding = embedder.embed_text(embed_text)
                        client.table("scheme_embeddings").insert({
                            "scheme_id": scheme["id"],
                            "chunk_text": embed_text,
                            "chunk_index": 0,
                            "embedding": embedding,
                            "metadata": {"source": "nvidia_enrichment"},
                        }).execute()
                except Exception as e:
                    logger.error(f"Update failed for {scheme['name']}: {e}")
        
        if (i + 1) % 5 == 0:
            logger.info(f"  Enrichment progress: {i+1}/{len(schemes)} ({enriched_count} enriched)")
        
        await asyncio.sleep(3)  # Rate limit (avoid 429)
    
    logger.info(f"Enrichment complete! {enriched_count}/{len(schemes)} enriched")
    return enriched_count


# ═══════════════════════════════════════════════════
# Main Orchestrator
# ═══════════════════════════════════════════════════

async def run_mass_generation(
    sectors: list[str] | None = None,
    states: list[str] | None = None,
    enrich_existing: bool = False,
    skip_listing: bool = False,
):
    """Generate comprehensive scheme data using NVIDIA Qwen."""
    
    if enrich_existing:
        await enrich_existing_schemes()
        return
    
    client = get_supabase_client()
    embedder = get_embedding_client()
    nvidia = get_nvidia_client()
    
    target_sectors = sectors or SECTORS
    target_states = states or ["Central", "Tamil Nadu"]  # Start with these, expand later
    
    stats = {"listed": 0, "detailed": 0, "stored": 0, "duplicates": 0, "errors": 0}
    
    # Track all discovered scheme names to avoid duplicate calls
    seen_slugs = set()
    
    # Load existing slugs from DB
    try:
        existing = client.table("schemes").select("slug").execute()
        for row in (existing.data or []):
            seen_slugs.add(row["slug"])
        logger.info(f"Existing schemes in DB: {len(seen_slugs)}")
    except Exception:
        pass
    
    total_combos = len(target_sectors) * len(target_states)
    combo_idx = 0
    
    for state in target_states:
        for sector in target_sectors:
            combo_idx += 1
            logger.info(f"\n[{combo_idx}/{total_combos}] {sector} / {state}")
            logger.info("-" * 50)
            
            if not skip_listing:
                # Step 1: List all schemes in this sector/state
                scheme_list = await list_schemes_for_sector(nvidia, sector, state)
                stats["listed"] += len(scheme_list)
                await asyncio.sleep(5)
                
                # Step 2: Get details for each new scheme
                for scheme_brief in scheme_list:
                    name = scheme_brief.get("name", "")
                    slug = generate_slug(name)
                    
                    if slug in seen_slugs:
                        stats["duplicates"] += 1
                        continue
                    seen_slugs.add(slug)
                    
                    # Get detailed info
                    details = await get_scheme_details(
                        nvidia,
                        name=name,
                        state=state,
                        ministry=scheme_brief.get("ministry", ""),
                        sector=sector,
                    )
                    
                    if details:
                        stats["detailed"] += 1
                        
                        # Store in DB
                        scheme_id = store_scheme(client, embedder, details, state, sector)
                        if scheme_id:
                            stats["stored"] += 1
                        else:
                            stats["errors"] += 1
                    else:
                        stats["errors"] += 1
                    
                    await asyncio.sleep(4)  # Rate limit (avoid 429)
            
            logger.info(f"  Subtotal — Listed: {stats['listed']} | Stored: {stats['stored']} | "
                        f"Dupes: {stats['duplicates']} | Errors: {stats['errors']}")
    
    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("MASS SCHEME GENERATION COMPLETE!")
    logger.info("=" * 60)
    logger.info(f"  Schemes discovered: {stats['listed']}")
    logger.info(f"  Details fetched:    {stats['detailed']}")
    logger.info(f"  Stored in DB:       {stats['stored']}")
    logger.info(f"  Duplicates skipped: {stats['duplicates']}")
    logger.info(f"  Errors:             {stats['errors']}")
    
    try:
        total = client.table("schemes").select("id", count="exact").execute()
        logger.info(f"  Total in DB now:    {total.count}")
    except Exception:
        pass
    
    return stats


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NVIDIA Qwen Mass Scheme Generator")
    parser.add_argument("--sector", type=str, help="Single sector to generate for")
    parser.add_argument("--state", type=str, help="Single state to generate for")
    parser.add_argument("--all-states", action="store_true", help="Generate for ALL states")
    parser.add_argument("--enrich-existing", action="store_true", help="Only enrich existing schemes")
    args = parser.parse_args()
    
    sectors = [args.sector] if args.sector else None
    states = None
    if args.state:
        states = [args.state]
    elif args.all_states:
        states = STATES
    
    asyncio.run(run_mass_generation(
        sectors=sectors,
        states=states,
        enrich_existing=args.enrich_existing,
    ))


if __name__ == "__main__":
    main()
