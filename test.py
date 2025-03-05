from bs4 import BeautifulSoup

# HTML 파일 로드
iframe_file_path = "debug_casino_iframe.html"  # 파일 경로를 맞게 수정해야 함.

with open(iframe_file_path, "r", encoding="utf-8") as f:
    iframe_html = f.read()

# BeautifulSoup으로 HTML 파싱
soup = BeautifulSoup(iframe_html, "html.parser")

# 방 목록을 포함할 가능성이 높은 클래스명들
room_classes = ["tile--466c7", "tile--5d2e6", "Category--17479"]

# 각 클래스별 요소 찾기 및 출력
for room_class in room_classes:
    print(f"\n🔍 클래스명: {room_class}")
    elements = soup.find_all("div", class_=room_class)
    
    if not elements:
        print("❌ 해당 클래스의 요소를 찾을 수 없음.")
        continue

    for idx, element in enumerate(elements, 1):
        text_content = element.get_text(strip=True)
        print(f"  [{idx}] {text_content[:100]}")  # 너무 길면 100자까지만 출력
