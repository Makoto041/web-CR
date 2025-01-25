from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import re

def clean_json_text(text: str) -> str:
    """
    JSON文字列に混入しがちな BOM や制御文字を除去して返す関数
    """
    # 先頭のBOM(UTF-8) (\ufeff)を削除
    text = text.lstrip('\ufeff')
    # ASCII制御文字(0x00-0x1F、0x7F)をまとめて削除
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    return text

def split_multiple_jsons(raw_text: str):
    """
    複数のJSONオブジェクトが1つの文字列に含まれている場合、それらを分割する
    """
    pattern = r'\{.*?\}'  # JSONオブジェクトを検出する正規表現
    matches = re.findall(pattern, raw_text, re.DOTALL)
    return matches

def extract_reviews_from_json(obj):
    """
    再帰的にJSONオブジェクトを探索し、`@type: "Review"` のdescriptionとratingValueを抽出する
    """
    reviews = []

    if isinstance(obj, dict):
        # @typeがReviewの場合、descriptionとratingValueを抽出
        if obj.get('@type') == 'Review':
            rating_value = obj.get('reviewRating', {}).get('ratingValue')
            description = obj.get('description')
            reviews.append({
                'ratingValue': rating_value,
                'description': description
            })

        # 子要素を再帰的に探索
        for v in obj.values():
            reviews.extend(extract_reviews_from_json(v))

    elif isinstance(obj, list):
        # リストの場合、各要素を再帰的に探索
        for item in obj:
            reviews.extend(extract_reviews_from_json(item))

    return reviews

def main():
    url = "https://www.itreview.jp/products/dx-suite-ai-ocr/reviews"

    # ブラウザ起動オプション設定
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')  # 必要に応じてヘッドレスモードを使用

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # 指定した XPATH の要素が出現するまで最大20秒待機
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//script[@type="application/ld+json"]'))
        )
    except:
        print("Timeout - ld+json script not found within 20 seconds.")
        driver.quit()
        return

    # 追加待機
    time.sleep(2)

    # <script type="application/ld+json"> をすべて取得
    scripts = driver.find_elements(By.XPATH, '//script[@type="application/ld+json"]')
    print(f"Found {len(scripts)} script tags with type=application/ld+json")

    # Script 2 を選択
    if len(scripts) >= 2:
        # script要素の textContent を取得
        raw_text = scripts[1].get_attribute("textContent") or ""
        raw_inner = scripts[1].get_attribute("innerHTML") or ""

        # textContent が空なら innerHTML を使う
        content = raw_text.strip() if raw_text.strip() else raw_inner.strip()

        # BOM や制御文字を削除
        content = clean_json_text(content)

        print(f"\n--- [Script 2] raw_text ---\n{content}")

        # JSON 分割
        json_blocks = split_multiple_jsons(content)
        print(f"Found {len(json_blocks)} JSON blocks in Script 2")

        # 各JSONブロックを解析
        all_reviews = []
        for idx, json_block in enumerate(json_blocks, start=1):
            try:
                data = json.loads(json_block)
                # 再帰的に @type = 'Review' を抽出
                extracted = extract_reviews_from_json(data)
                all_reviews.extend(extracted)
            except json.JSONDecodeError as e:
                print(f"[Block {idx}] JSONDecodeError: {e}")

        # 抽出したレビューを表示
        print("\n=== Extracted Reviews from Script 2 ===")
        if not all_reviews:
            print("No reviews found.")
        else:
            for i, r in enumerate(all_reviews, start=1):
                print(f"[Review {i}] rating={r['ratingValue']} desc={r['description']}")
    else:
        print("Script 2 not found.")

    # ブラウザを閉じる
    driver.quit()

if __name__ == "__main__":
    main()