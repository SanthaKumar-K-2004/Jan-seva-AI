"""
Jan-Seva AI — Sector Configuration
Defines seed URLs and search patterns for the Crawler Swarm.
"""

SECTOR_CONFIG = {
    "central": {
        "seeds": [
            "https://www.myscheme.gov.in/search",
            "https://www.india.gov.in/my-government/schemes",
            "https://pib.gov.in/allRel.aspx" 
        ],
        "keywords": ["scheme", "yojana", "mission", "bima", "kalyan"]
    },
    "agriculture": {
        "seeds": [
            "https://agricoop.nic.in/en/Schemes",
            "https://pmkisan.gov.in/"
        ],
        "keywords": ["farmer", "kisan", "crop", "agriculture", "subsidy"]
    },
    "education": {
        "seeds": [
            "https://education.gov.in/schemes",
            "https://scholarships.gov.in/"
        ],
        "keywords": ["scholarship", "student", "education", "school", "university"]
    },
    "health": {
        "seeds": [
            "https://pmjay.gov.in/",
            "https://main.mohfw.gov.in/major-programmes/schemes"
        ],
        "keywords": ["health", "swasthya", "insurance", "hospital", "treatment"]
    },
    "finance": {
        "seeds": [
            "https://financialservices.gov.in/schemes",
            "https://www.mudra.org.in/"
        ],
        "keywords": ["loan", "finance", "pension", "insurance", "bank"]
    },
    "women": {
        "seeds": [
            "https://wcd.nic.in/schemes"
        ],
        "keywords": ["women", "child", "girl", "shakti", "mahila"]
    }
}

def get_sector_config(sector: str) -> dict:
    return SECTOR_CONFIG.get(sector.lower(), {})
