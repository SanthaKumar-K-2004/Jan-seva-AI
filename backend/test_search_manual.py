
import requests
from bs4 import BeautifulSoup

def manual_search(query):
    print(f"Manual scraping for: {query}")
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        data = {"q": query}
        
        # DDG HTML version uses POST
        res = requests.post(url, data=data, headers=headers, timeout=10)
        
        if res.status_code != 200:
            print(f"Failed with status: {res.status_code}")
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        
        # Select result links
        for i, link in enumerate(soup.find_all("a", class_="result__a"), 1):
            title = link.text.strip()
            href = link.get("href")
            # snippet is usually in a sibling div
            snippet = ""
            
            # Try to find snippet
            parent = link.find_parent("div", class_="result__body")
            if parent:
                snippet_div = parent.find("a", class_="result__snippet")
                if snippet_div:
                    snippet = snippet_div.text.strip()
            
            if href and title:
                print(f"{i}. {title} ({href})")
                results.append({"title": title, "href": href, "body": snippet})
                
            if i >= 5: break
            
        return results
        
    except Exception as e:
        print(f"Manual Error: {e}")
        return []

if __name__ == "__main__":
    manual_search("Tamil Nadu Chief Minister")
    print("-" * 20)
    manual_search("Ulagam Ungal Kaiyil scheme 2026")
