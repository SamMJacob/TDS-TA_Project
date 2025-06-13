import requests
from datetime import datetime, timezone
import os
from bs4 import BeautifulSoup
import time
import json  # Added missing import

COOKIE = {"_forum_session": r"TYgmsDF94Ke8eqpEdOdmz1gZecvhWK5pufwY4WKfT6JTxyOTplPVs9EwNv1eQfNpxaF0dHOOI6IiY%2BrNYy5brIcmIilcc35oo8UmPqd1KJkKcCNeDFiNo19%2FOhvpdDxzEeUE2L1k2oTQmu6%2FgICWtzIwaYT6XKlTtXNsFWoz9vEjbO9pjXdQ80BM5oSSf0mquzoHOkdvTSxSd5zec75GANNZg%2B8ZI3GuLKWSd6viRASV4R7MhI%2BSviFL1riztjGwdYrdJVWHmFzyhWgR%2BZ9gyrPmW0N%2BhsYs1i9CR5loiOg7nNKz3fY%2FdrF9hsbEa8GixlJNabTWBZj6a7wjtuLefOR7YGqQomytiRhpOfnpROfbpXNoMv2qlYfyv%2FtH3A%3D%3D--fvxGWhSLWNH3iXRQ--t%2Ftp8gM5gjMUwgMSCCyUAw%3D%3D",
          "_bypass_cache":"true",
          "_t":r"bb5mmwUvRBHJTrvYB9x9PztUQdbZUmxiyigxUATFlx3ZqK3jx%2BVuLWEzn%2FjqXvceYFRGNZLtCU6IulFySkMvEm%2BFigqGsBkCYoeDvjygxyf5gv2Kj5QRp0pM8srrIblDuAk4GrgcZ%2BSMXDZvoLtzOHBuNrCMQd0ibIvrWhLV5txE9DRUaWQpvGppFwXyOy7VqrYClx4wngDXxYdXUKzXPlm5UTi9O156affMxHTXt4ABEOtPhTx1%2BgEoNl%2BpWRrskzELMKjVwMf24wFdytTwjkJRBFq71YuIPq%2BDsVz5t9R2RwE4%2BfudAA%3D%3D--EVCN6b2%2BOWhgIWqB--iL3zusQOI8iXgRiFOjPLuA%3D%3D",
          "_fbp":"fb.2.1739894294246.252628899525647917",
          "_ga":"GA1.1.588076598.1739894294",
          "_ga_08NPRH5L4M":"GS2.1.s1748359806$o23$g0$t1748359806$j60$l0$h0$daEc8t4yZfkgGRovJ3lVjgFfVe5Rmq9Xj4w",
          "_ga_5HTJMW67XK":"GS1.1.1745411436.2.0.1745411477.0.0.0",
          "_gcl_au":"1.1.1354992849.1747818860",
          "_gcl_aw":"GCL.1743007193.Cj0KCQjw4v6-BhDuARIsALprm31OEIxejxzcxD5K43ZXh-_GcTvR5Lammuih9nE2lqCXR7cYooMKGl0aAptFEALw_wcB",
          "_gcl_gs":"2.1.k1$i1742747257$u129582030"}

BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
CATEGORY_JSON_URL = f"{BASE_URL}/c/courses/tds-kb/34.json"

START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2025, 4, 14, 23, 59, 59, tzinfo=timezone.utc)


def fetch_json(url):
    """Fetch JSON data with better error handling and rate limiting"""
    print(f"Fetching: {url}")
    time.sleep(0.5)  # Rate limiting
    
    response = requests.get(url, cookies=COOKIE)
    response.raise_for_status()
    return response.json()


def parse_date(date_str):
    """Parse ISO 8601 date string to datetime object"""
    if not date_str:
        raise ValueError("Empty or None date string")
    try:
        # Convert from ISO 8601 with Zulu to Python datetime with timezone
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.fromisoformat(date_str)
    except Exception as e:
        print(f"Error parsing date: {date_str} -> {e}")
        raise


def scrape_topics_in_date_range():
    """Scrape all topics in the specified date range with improved pagination"""
    filtered_topics = []
    page = 0
    
    while True:
        # Construct URL with page parameter
        if page == 0:
            url = CATEGORY_JSON_URL
        else:
            url = f"{CATEGORY_JSON_URL}?page={page}"
        
        try:
            data = fetch_json(url)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page {page}: {e}")
            break
            
        topic_list = data.get("topic_list", {})
        topics = topic_list.get("topics", [])
        
        print(f"Page {page}: Fetched {len(topics)} topics")
        
        if not topics:
            print("No more topics found. Stopping pagination.")
            break

        # Track topics in date range for this page
        page_filtered_count = 0
        oldest_date = None
        newest_date = None
        
        for topic in topics:
            created_at_str = topic.get("created_at")
            if not created_at_str:
                print(f"Skipping topic with missing created_at: {topic.get('id', 'unknown')}")
                continue

            try:
                created_at = parse_date(created_at_str)
            except Exception:
                print(f"Skipping topic with invalid date: {topic.get('id', 'unknown')}")
                continue

            # Track date range for debugging
            if oldest_date is None or created_at < oldest_date:
                oldest_date = created_at
            if newest_date is None or created_at > newest_date:
                newest_date = created_at

            if START_DATE <= created_at <= END_DATE:
                filtered_topics.append(topic)
                page_filtered_count += 1

        print(f"Page {page}: {page_filtered_count} topics in date range")
        if oldest_date and newest_date:
            print(f"Page {page}: Date range {oldest_date.date()} to {newest_date.date()}")

        # Check if we should continue pagination
        # Stop if all topics are older than our start date
        if oldest_date and oldest_date < START_DATE:
            print(f"Page {page}: Some topics older than start date ({START_DATE.date()}), but continuing pagination.")
            
        # Check for more pages - try multiple methods
        has_more = False
        
        # Method 1: Check load_more_topics_url
        load_more_url = topic_list.get("load_more_topics_url")
        if load_more_url:
            print(f"Found load_more_topics_url: {load_more_url}")
            # Extract page number from load_more_url if possible
            if "page=" in load_more_url:
                try:
                    next_page = int(load_more_url.split("page=")[1].split("&")[0])
                    page = next_page
                    has_more = True
                except:
                    page += 1
                    has_more = True
            else:
                page += 1
                has_more = True
        
        # Method 2: Check if we got a full page of results (usually 30)
        elif len(topics) >= 30:
            print(f"Got full page of {len(topics)} topics, trying next page")
            page += 1
            has_more = True
            
        # Method 3: Check more_topics_url
        elif topic_list.get("more_topics_url"):
            print(f"Found more_topics_url: {topic_list.get('more_topics_url')}")
            page += 1
            has_more = True
        
        if not has_more:
            print("No more pages available. Stopping pagination.")
            break
            
        # Safety check to prevent infinite loops
        if page > 150:  # Adjust this limit as needed
            print("Reached maximum page limit (150). Stopping.")
            break

    print(f"\nTotal topics found in date range: {len(filtered_topics)}")
    return filtered_topics


def fetch_and_save_topic(topic, folder="discourse_threads"):
    """Fetch and save individual topic content and metadata"""
    os.makedirs(folder, exist_ok=True)
    topic_id = topic["id"]
    topic_slug = topic["slug"]
    url = f"{BASE_URL}/t/{topic_slug}/{topic_id}"
    created_at = topic.get("created_at")
    title = topic.get("title")

    try:
        data = fetch_json(f"{url}.json")
        posts = data.get("post_stream", {}).get("posts", [])

        texts = []
        for post in posts:
            html_content = post.get("cooked", "")
            soup = BeautifulSoup(html_content, "html.parser")
            plain_text = soup.get_text(separator="\n").strip()
            texts.append(plain_text)

        text = "\n\n---\n\n".join(texts)

        filename_txt = f"{topic_id}_{topic_slug}.txt"
        filepath_txt = os.path.join(folder, filename_txt)

        with open(filepath_txt, "w", encoding="utf-8") as f:
            f.write(text)

        # Save metadata JSON alongside
        metadata = {
            "topic_id": topic_id,
            "slug": topic_slug,
            "title": title,
            "url": url,
            "created_at": created_at,
            "post_count": len(posts),
        }
        filename_json = f"{topic_id}_{topic_slug}.json"
        filepath_json = os.path.join(folder, filename_json)
        with open(filepath_json, "w", encoding="utf-8") as fjson:
            json.dump(metadata, fjson, indent=2)

        print(f"Saved topic '{title}' text to {filepath_txt} and metadata to {filepath_json}")

    except Exception as e:
        print(f"Error saving topic {topic_id}: {e}")


# MAIN EXECUTION - This was missing!
if __name__ == "__main__":
    try:
        print("Starting discourse scraper...")
        print(f"Date range: {START_DATE.date()} to {END_DATE.date()}")
        
        # Step 1: Get all topics in date range
        topics = scrape_topics_in_date_range()
        
        if not topics:
            print("No topics found in the specified date range.")
        else:
            print(f"\nFound {len(topics)} topics. Starting to download individual topics...")
            
            # Step 2: Download each topic
            for i, topic in enumerate(topics, 1):
                print(f"\nProcessing topic {i}/{len(topics)}: {topic.get('title', 'Untitled')}")
                fetch_and_save_topic(topic)
                
        print("\nScraping completed!")
        
    except Exception as e:
        print(f"Script failed with error: {e}")
        import traceback
        traceback.print_exc()