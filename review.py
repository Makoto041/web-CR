import requests
from bs4 import BeautifulSoup
import json
import time
from requests.exceptions import RequestException

BASE_URL = "https://www.itreview.jp"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def get_product_links():
    """OCRカテゴリの全製品URLを取得"""
    products = set()
    page = 1
    
    while True:
        url = f"{BASE_URL}/categories/ocr?page={page}"
        print(f"Accessing category page: {url}")
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            
            # 製品詳細ページリンクを抽出
            new_products = {
                a["href"] for a in soup.select("a[href^='/products/']:not([href*='lead_campaigns'])")
            }
            
            if not new_products:
                print("No more product links found. Stopping.")
                break
            
            products.update(new_products)
            print(f"Page {page} processed, found {len(new_products)} new links.")
            page += 1
            time.sleep(1)
        except RequestException as e:
            print(f"Error accessing {url}: {e}")
            break

    return list(products)

def extract_reviews_from_html(html):
    """HTMLからレビュー情報を抽出"""
    soup = BeautifulSoup(html, "html.parser")
    reviews = []
    
    for review_card in soup.select("article.review-card"):
        try:
            # レビュータイトル
            title = review_card.select_one("h4 a").text.strip() if review_card.select_one("h4 a") else ""
            
            # 投稿日時
            date_tag = review_card.select_one("time")
            date = date_tag.text.strip() if date_tag else ""
            
            # レビュアー情報
            author_tag = review_card.select_one(".ribbin-wrap .bold")
            author = author_tag.text.strip() if author_tag else ""
            author_info_tag = review_card.select_one(".ribbin-wrap .small")
            author_info = author_info_tag.text.strip() if author_info_tag else ""
            
            # 評価（星）
            star_elem = review_card.select_one(".star-rating")
            star_rating = ""
            if star_elem and star_elem.has_attr("class"):
                # star-rating five / star-rating three half などのクラスから星数を抽出
                star_rating_classes = star_elem["class"]
                rating_candidates = {"one", "two", "three", "four", "five"}
                found = rating_candidates.intersection(star_rating_classes)
                star_rating = " ".join(found) if found else ""
            
            # 良いポイント
            good_points = ""
            gp_title = review_card.select_one(".first-sentence h5")
            if gp_title and gp_title.find_next_sibling("p"):
                good_points = gp_title.find_next_sibling("p").text.strip()
            
            # 改善ポイント
            improvement_points = ""
            for h5 in review_card.select(".txt h5"):
                if "改善してほしいポイント" in h5.get_text():
                    next_p = h5.find_next_sibling("p")
                    if next_p:
                        improvement_points = next_p.get_text(strip=True)
                    break
            
            # 課題解決
            resolved_issues = ""
            for h5 in review_card.select(".txt h5"):
                if "どのような課題" in h5.get_text():
                    next_p = h5.find_next_sibling("p")
                    if next_p:
                        resolved_issues = next_p.get_text(strip=True)
                    break
            
            # URL (レビュー詳細リンク)
            review_url_tag = review_card.select_one("h4 a")
            review_url = (BASE_URL + review_url_tag["href"]) if review_url_tag and review_url_tag.has_attr("href") else ""
            
            reviews.append({
                "title": title,
                "date": date,
                "author": author,
                "author_info": author_info,
                "rating": star_rating,
                "good_points": good_points,
                "improvement_points": improvement_points,
                "resolved_issues": resolved_issues,
                "url": review_url,
            })
        except Exception as e:
            print(f"Error parsing review card: {e}")
    
    return reviews

def get_reviews(product_path, max_reviews=5):
    """
    個別製品の全レビューデータを取得。
    max_reviews で上限件数を指定する（デフォルト5件）。
    """
    reviews = []
    page = 1
    
    while len(reviews) < max_reviews:
        url = f"{BASE_URL}{product_path}?page={page}"
        print(f"Accessing reviews page: {url}")
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
            response.raise_for_status()
            new_reviews = extract_reviews_from_html(response.text)
            if not new_reviews:
                print("No reviews found on this page. Stopping.")
                break
            
            reviews.extend(new_reviews)
            if len(reviews) >= max_reviews:
                break
            
            page += 1
            time.sleep(1)
        except RequestException as e:
            print(f"Error accessing {url}: {e}")
            break
    
    return reviews[:max_reviews]

def main():
    # 製品リンクを取得
    products = get_product_links()
    print(f"Found {len(products)} products.")
    
    all_reviews = {}
    max_reviews = 5  # 最大取得件数を変更可能
    
    # 製品ごとにレビューを取得
    for i, product_path in enumerate(products, start=1):
        print(f"\nProcessing product {i}/{len(products)}: {product_path}")
        reviews = get_reviews(product_path, max_reviews=max_reviews)
        all_reviews[product_path] = reviews
        time.sleep(1)
    
    # 結果をJSONファイルに保存
    with open("reviews_by_product.json", "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, ensure_ascii=False, indent=2)
    
    print("Reviews saved to reviews_by_product.json.")

if __name__ == "__main__":
    main()