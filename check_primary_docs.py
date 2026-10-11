
import requests
from bs4 import BeautifulSoup

base = "https://www.sec.gov"
documents = [
    (
        "MetroSpaces 8-K",
        "/Archives/edgar/data/1488501/000190359626000372/mspc_8k.htm",
    ),
    (
        "MetroSpaces Exhibit 99.1",
        "/Archives/edgar/data/1488501/000190359626000372/ex99_1.htm",
    ),
    (
        "Wilson Bank 8-K",
        "/Archives/edgar/data/885275/000119312526418699/ck0000885275-20261009.htm",
    ),
    (
        "Wilson Bank Exhibit 99.1",
        "/Archives/edgar/data/885275/000119312526418699/ck0000885275-ex99_1.htm",
    ),
]

headers = {
    "User-Agent": "RiskCascadePrototype/0.2 research contact: lilymaria2344@gmail.com"
}

for name, path in documents:
    print("\n" + "=" * 70)
    print("DOCUMENT:", name)

    try:
        response = requests.get(base + path, headers=headers, timeout=25)
        print("STATUS:", response.status_code)

        if response.status_code != 200:
            print(response.text[:200])
            continue

        soup = BeautifulSoup(response.content, "html.parser")

        for tag in soup(["script", "style", "ix:header"]):
            tag.decompose()

        text = "\n".join(
            line.strip()
            for line in soup.get_text("\n").splitlines()
            if line.strip()
        )

        print("EXTRACTED CHARACTERS:", len(text))
        print("TEXT PREVIEW:\n", text[:1800])

    except Exception as error:
        print("ERROR:", repr(error))
