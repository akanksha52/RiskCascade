from src.ingestion import fetch_news

result = fetch_news(max_per_feed=5)

print(f"Retrieved articles: {len(result['articles'])}")
print(f"Feed errors: {len(result['errors'])}")

for error in result["errors"]:
    print("ERROR:", error)

for article in result["articles"][:5]:
    print("\nHeadline:", article["title"])
    print("Publisher:", article["source"])
    print("Published:", article["published_at"])
    print("URL:", article["url"])