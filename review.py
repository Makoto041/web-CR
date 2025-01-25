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
    text = text.lstrip('\ufeff')  # 先頭のBOM(UTF-8) (\ufeff)を削除
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)  # ASCII制御文字(0x00-0x1F、0x7F)を削除
    return text

def parse_multiple_jsons(raw_text: str):
    """
    テキスト中に連結されている複数のJSONオブジェクトを、
    '{' と '}' の対応関係を追いかけながら順番に抽出し、パースして返す。
    """
    idx = 0
    length = len(raw_text)
    result = []

    while idx < length:
        # '{' を探す
        start = raw_text.find('{', idx)
        if start == -1:
            break  # もう '{' が見つからない → 終了

        # ブレースの深さを追跡する
        brace_depth = 1
        end = start + 1

        while end < length and brace_depth > 0:
            if raw_text[end] == '{':
                brace_depth += 1
            elif raw_text[end] == '}':
                brace_depth -= 1
            end += 1

        if brace_depth == 0:
            # 一つのJSONブロックを切り出せる
            json_block = raw_text[start:end]
            # ここで JSON パースを試みる
            try:
                parsed = json.loads(json_block)
                result.append(parsed)
            except json.JSONDecodeError:
                pass
            # 次の探索はここから続ける
            idx = end
        else:
            # もしブレースが最後まで対応しなかったら終了
            break

    return result

def extract_reviews_from_json(obj):
    """
    再帰的にJSONオブジェクトを探索し、`@type: "Review"` のdescriptionとratingValueを抽出する
    """
    reviews = []

    if isinstance(obj, dict):
        # @type が 'Review' の場合、description と ratingValue を抽出
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

def parse_reviews_on_current_page(driver):
    """
    現在のページにある <script type="application/ld+json"> を解析し、
    全てのJSONブロックから @type=Review のデータを抽出して返す
    """
    # <script type="application/ld+json"> をすべて取得
    scripts = driver.find_elements(By.XPATH, '//script[@type="application/ld+json"]')

    page_reviews = []

    # 各 <script> を処理
    for idx, script_element in enumerate(scripts, start=1):
        raw_text = script_element.get_attribute("textContent") or ""
        raw_inner = script_element.get_attribute("innerHTML") or ""

        # textContent が空なら innerHTML を使う
        content = raw_text.strip() if raw_text.strip() else raw_inner.strip()

        # BOM や制御文字を削除
        content = clean_json_text(content)

        # JSON の複数ブロックを抽出
        json_blocks = parse_multiple_jsons(content)

        # 各ブロックから再帰的にレビューを抽出
        for data in json_blocks:
            extracted = extract_reviews_from_json(data)
            page_reviews.extend(extracted)

    return page_reviews

def main():
    base_url = "https://www.itreview.jp/products/dx-suite-ai-ocr/reviews"

    # ブラウザ起動オプション設定
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # 必要に応じてヘッドレスモードを使用

    driver = webdriver.Chrome(options=options)

    all_reviews = []
    page = 1

    while True:
        # ページ遷移
        target_url = f"{base_url}?page={page}"
        print(f"Accessing: {target_url}")
        driver.get(target_url)

        # ページが表示されるまで待機（最大20秒）
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
        except:
            print("Timeout waiting for page body.")
            break

        time.sleep(2)  # 必要に応じて待機時間調整

        # 「絞り込み条件に一致するレビューがありません。」があるかチェック
        no_reviews_elements = driver.find_elements(By.XPATH, '//div[contains(@class, "txt-c") and contains(text(), "絞り込み条件に一致するレビューがありません。")]')
        if no_reviews_elements:
            print("No more reviews. Stopping.")
            break

        # このページのレビューを抽出
        page_reviews = parse_reviews_on_current_page(driver)
        if not page_reviews:
            # 何も取れなかった場合も終了条件にする
            print("No reviews found on this page. Stopping.")
            break

        all_reviews.extend(page_reviews)
        print(f"Page {page} - found {len(page_reviews)} reviews.")

        page += 1

    driver.quit()

    # 全ページのレビューを出力
    print("\n=== 全てのレビュー ===")
    if not all_reviews:
        print("No reviews found at all.")
    else:
        for i, r in enumerate(all_reviews, start=1):
            print(f"[Review {i}] 評価(MAX5.0)={r['ratingValue']} レビュー={r['description']}")

if __name__ == "__main__":
    main()