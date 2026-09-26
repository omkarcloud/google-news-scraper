# 📰 Google News Scraper

Google News Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Google News data for free.

## ✨ What Can I Get?

- 📰 **Top headlines in 90 editions across 72 countries** — every story with images, authors, publisher & related coverage
- 🔍 **Search any keyword, 100 articles deep** — date ranges, publisher filter, exact phrases & real publisher URLs
- 🧵 **Full coverage of any story** — up to 100+ articles, top picks, opinion, explainers & posts on X
- 🏙️ **Every topic, city, publisher & journalist** — Technology, Beverly Hills, TechCrunch or your favorite reporter

## 🎥 Example: A Full Google News Headline

```json
{
  "count": 70,
  "current_page": 1,
  "total_pages": 4,
  "articles": [
    {
      "id": "CBMifEFVX3lxTE1nT3o2LXNzMGpwdWxoTUtxUlZScHFGLXhiUy1maHJOOTNXSXpfRzNXb1FWVUxFM2gxN3M3T0pvVHVrQ0RVZTN2Y09XcWhVRHYtcVl0alJlUFdmVXlwR09ONFg0OVo4Sm4zZy1BRjhZRTZaYlhPNE9FMEQ0dmM",
      "title": "Trump and Chinese president Xi end summit without major agreement on AI",
      "link": "https://www.theguardian.com/technology/2026/sep/25/trump-xi-ai-arms-race",
      "published_at": "2026-09-25T22:13:00Z",
      "image": {"link": "https://i.guim.co.uk/img/media/dd96a7ac2aebddf0eba5644f06e8e33e6f1eb6ac/0_0_3118_2078/master/3118.jpg?width=465&dpr=1&s=none&crop=none", "width": 465, "height": 310},
      "publisher": {"name": "The Guardian", "domain": "theguardian.com", "link": "https://www.theguardian.com"},
      "authors": [{"id": "CAAqJAgKIh5DQkFTRUFvS0wyMHZNSFEwZGpWaVloSUNaVzRvQUFQAQ", "name": "David Smith"}],
      "story": {"id": "CAAqNggKIjBDQklTSGpvSmMzUnZjbmt0TXpZd1NoRUtEd2o3MjlyOUVSRzg0M0plWmQxNXNpZ0FQAQ", "title": "President Donald Trump hosts Chinese President Xi Jinping for state visit"},
      "related_articles": [
        {
          "title": "You Get an Eagle, and You Get an Eagle: Xi Takes Home Trump’s Go-To Gift",
          "link": "https://www.nytimes.com/2026/09/25/world/americas/trump-bald-eagle-gift-xi.html",
          "publisher": {"name": "The New York Times", "domain": "nytimes.com"}
        }
      ]
    }
  ]
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Google News Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/google-news-scraper
cd google-news-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/top-headlines"
```

```json
{
  "count": 70,
  "current_page": 1,
  "total_pages": 4,
  "articles": [
    {
      "title": "Huge crowds greet Pope in Paris ahead of open-air Mass",
      "link": "https://www.bbc.com/news/articles/cm4gjjwvvlzro",
      "published_at": "2026-09-26T12:51:10Z",
      "image": {"link": "https://ichef.bbci.co.uk/news/480/cpsprodpb/f85e/live/5d5a64a0-b9aa-11f1-bc1f-3f186ca4140c.jpg.webp", "width": 480, "height": 269},
      "publisher": {"name": "BBC", "domain": "bbc.com"},
      "authors": [{"name": "Jacob Phillips"}],
      "story": {"title": "Pope Leo XIV visits France"},
      "related_articles": [{"title": "Vast crowd greets pope with 'Leo' chants at France tour's biggest event", "publisher": {"name": "reuters.com"}}]
    }
  ]
}
```

All 15 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

15 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Top Headlines | `/top-headlines` | ~70 top stories with authors, images and related coverage |
| Autocomplete | `/autocomplete` | Google News query suggestions with relevance scores |
| Search News | `/search` | Up to 100 articles per keyword with real publisher URLs |
| Story Full Coverage | `/story` | Every article on a story, plus top picks and posts on X |
| Resolve Article Link | `/article/resolve` | The publisher's real URL behind any Google News link |
| Topic Articles / Details | `/topic/articles`, `/topic/details` | Any topic or section tab: AI, NFL, Markets and more |
| Local Headlines | `/local-headlines` | Local news for any city, region or country |
| Publication Articles / Details | `/publication/articles`, `/publication/details` | Any publisher's latest articles and profile, by domain |
| Author Articles | `/author/articles` | Any journalist's latest articles across publishers |
| Home Page / News Showcase | `/home`, `/showcase` | The front-page briefing and publisher-curated Showcase panels |
| Topics / Editions | `/topics`, `/editions` | Topic IDs for any edition, and all 90 editions |


## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-google-news-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-google-news-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-google-news-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/search",
    params={"query": "OpenAI", "time_published": "past_week"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Google News Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20Google%20News%20Scraper%20API.)

[![Ask Us by Email about Google News Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Google%20News%20Scraper%20API&body=I%20need%20help%20using%20the%20Google%20News%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**Google Search Scraper**](https://github.com/omkarcloud/google-scraper) — full Google results pages, AI Overviews, Images, Shopping & Trends
- [**Reddit Scraper**](https://github.com/omkarcloud/reddit-scraper) — Reddit posts, full comment threads, subreddits & users
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper) — live product details, SKU variants, stock & shipping

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/google-news-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/google-news-scraper)
