
import requests
from bs4 import BeautifulSoup

urls = [
    "https://www.sec.gov/Archives/edgar/data/1488501/000190359626000372/0001903596-26-000372.txt",
    "https://www.sec.gov/Archives/edgar/data/885275/000119312526418699/0001193125-26-418699.txt",
]

headers = {
    "User-Agent": "RiskCascadePrototype/0.2 research contact: YOUR_EMAIL@example.com"
}

for url in urls:
    print("\n" + "=" * 70)
    try:
        response = requests.get(url, headers=headers, timeout=25)
        print("Status:", response.status_code)
        print("Downloaded bytes:", len(response.content))

        if response.status_code != 200:
            print(response.text[:300])
            continue

        soup = BeautifulSoup(response.content, "html.parser")
        text = " ".join(soup.stripped_strings)

        print("Extracted characters:", len(text))
        print("Preview:\n", text[:1200])

    except Exception as error:
        print("Error:", repr(error))
