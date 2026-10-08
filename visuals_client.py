import base64
import urllib.parse
import httpx

HEADERS = {"User-Agent": "PDFStudyBuddy/0.1 (personal study app)"}
WIKIMEDIA_URL = "https://commons.wikimedia.org/w/api.php"
WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"

IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"BM")


def _is_real_image(data: bytes) -> bool:
    return data.startswith(IMAGE_MAGIC)


async def _download(client, url):
    r = await client.get(url, headers=HEADERS)
    r.raise_for_status()
    if not _is_real_image(r.content):
        return None
    return base64.b64encode(r.content).decode()


async def _wikipedia_image(client, query):
    """Most accurate single image: lead image of the best-matching Wikipedia article."""
    try:
        r = await client.get(WIKI_SEARCH_URL, params={
            "action": "opensearch", "search": query, "limit": "3",
            "namespace": "0", "format": "json",
        }, headers=HEADERS)
        titles = r.json()[1]
    except Exception as ex:
        print(f"[visuals] wiki search failed: {ex}")
        return None

    for title in titles:
        try:
            s = await client.get(
                f"{WIKI_SUMMARY_URL}/{urllib.parse.quote(title.replace(' ', '_'))}",
                headers=HEADERS,
            )
            data = s.json()
            thumb = (data.get("thumbnail") or {}).get("source")
            full = (data.get("originalimage") or {}).get("source") or thumb
            if thumb:
                print(f"[visuals] wikipedia hit: {title}")
                return thumb, full
        except Exception as ex:
            print(f"[visuals] wiki summary failed for '{title}': {ex}")
    return None


async def _commons_search(client, query, limit):
    params = {
        "action": "query", "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": "400",
    }
    r = await client.get(WIKIMEDIA_URL, params=params, headers=HEADERS)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    out = []
    for p in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        info = p.get("imageinfo", [{}])[0]
        if info.get("mime", "").startswith("image/") and info.get("thumburl"):
            out.append((info["thumburl"], info.get("url")))
    return out


async def search_images(query: str, word: str, limit: int = 3):
    results = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        # 1. Wikipedia lead image = the accurate one
        wiki = await _wikipedia_image(client, query)
        if not wiki and query != word:
            wiki = await _wikipedia_image(client, word)
        if wiki:
            b64 = await _download(client, wiki[0])
            if b64:
                results.append((b64, wiki[1]))

        # 2. Fill remaining slots with Commons search
        if len(results) < limit:
            for q in (query, word):
                try:
                    candidates = await _commons_search(client, q, limit)
                except Exception as ex:
                    print(f"[visuals] commons search failed for '{q}': {ex}")
                    candidates = []
                for thumb_url, full_url in candidates:
                    if len(results) >= limit:
                        break
                    b64 = await _download(client, thumb_url)
                    if b64:
                        results.append((b64, full_url or thumb_url))
                if len(results) >= limit:
                    break
    return results