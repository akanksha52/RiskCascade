
import requests
from bs4 import BeautifulSoup

urls = [
    "https://www.sec.gov/Archives/edgar/data/1488501/000190359626000372/0001903596-26-000372-index.htm",
    "https://www.sec.gov/Archives/edgar/data/885275/000119312526418699/0001193125-26-418699-index.htm",
]

headers = {
    "User-Agent": "RiskCascadePrototype/0.2 research contact: YOUR_EMAIL@example.com"
}

for url in urls:
    print("\nURL:", url)

    try:
        response = requests.get(url, headers=headers, timeout=20)
        print("STATUS:", response.status_code)
        print("BYTES:", len(response.content))

        if response.status_code != 200:
            print("RESPONSE:", response.text[:300])
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        print("TITLE:", soup.title.get_text(" ", strip=True) if soup.title else "None")

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if any(ext in href.lower() for ext in [".htm", ".txt", ".xml"]):
                print("LINK:", link.get_text(" ", strip=True)[:100], "->", href)

    except Exception as error:
        print("ERROR:", repr(error))
