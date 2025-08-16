"""
브라우저 실행 테스트
"""
from playwright.sync_api import sync_playwright
import time

def test_browser_launch():
    print("브라우저 실행 테스트 시작...")
    
    # Playwright 시작
    p = sync_playwright().start()
    
    # 브라우저 실행
    browser = p.chromium.launch(headless=False)
    print("[OK] Browser launched successfully!")
    
    # 페이지 생성
    page = browser.new_page()
    
    # 사이트 접속
    page.goto("https://pan-3718.com")
    print("[OK] Site accessed successfully!")
    
    # 5초 대기
    time.sleep(5)
    
    # 브라우저 종료
    browser.close()
    p.stop()
    print("[OK] Browser closed successfully!")

if __name__ == "__main__":
    test_browser_launch()