import undetected_chromedriver as uc
import time

class DevToolsController:
    def __init__(self):
        self.driver = None  # ❌ 초기에는 브라우저 실행 X

    def start_browser(self):
        """Chrome 브라우저 실행 (버튼 클릭 시 실행)"""
        if self.driver is None:  # ✅ 브라우저가 실행되지 않았을 때만 실행
            options = uc.ChromeOptions()
            options.headless = False  # False: UI 보이게, True: 백그라운드 실행
            options.add_argument("--disable-blink-features=AutomationControlled")  # 봇 탐지 우회
            self.driver = uc.Chrome(options=options)
            print("[INFO] Chrome 브라우저 실행됨")
        else:
            print("[INFO] 이미 실행 중인 Chrome 브라우저가 있음")

    def open_site(self, url):
        """✅ 버튼을 눌렀을 때만 브라우저를 실행하고 사이트 이동"""
        if not self.driver:
            print("[INFO] 브라우저가 실행되지 않아 start_browser() 호출")
            self.start_browser()

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        print(f"[INFO] 사이트 이동: {url}")
        self.driver.get(url)
        time.sleep(3)  # 페이지 로딩 대기

    def get_page_source(self):
        """현재 페이지의 HTML 가져오기"""
        if not self.driver:
            print("[ERROR] 브라우저가 실행되지 않음")
            return None
        return self.driver.page_source  # HTML 반환

    def close_browser(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None  # ✅ 종료 후 드라이버 변수 초기화
            print("[INFO] 브라우저 종료됨")
