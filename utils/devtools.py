import undetected_chromedriver as uc
import time
import os
import re
import subprocess
import platform
import logging
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class DevToolsController:
    def __init__(self, logger=None):
        self.driver = None
        self.logger = logger or logging.getLogger(__name__)

    def get_chrome_version(self):
        """현재 시스템에 설치된 Chrome 브라우저의 버전을 감지"""
        version = None
        system = platform.system()
        
        try:
            if system == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Google\Chrome\BLBeacon')
                version, _ = winreg.QueryValueEx(key, 'version')
            
            elif system == "Darwin":  # macOS
                process = subprocess.Popen(
                    ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version'],
                    stdout=subprocess.PIPE
                )
                version = process.communicate()[0].decode('UTF-8').replace('Google Chrome', '').strip()
            
            elif system == "Linux":
                process = subprocess.Popen(
                    ['google-chrome', '--version'],
                    stdout=subprocess.PIPE
                )
                version = process.communicate()[0].decode('UTF-8').replace('Google Chrome', '').strip()
            
            if version:
                version_match = re.search(r'(\d+)\.', version)
                if version_match:
                    return int(version_match.group(1))
        
        except Exception as e:
            print(f"[WARNING] Chrome 버전 감지 중 오류 발생: {e}")
            print("[INFO] 기본 ChromeDriver 사용")
        
        return None

    def start_browser(self):
        """Chrome 버전 호환성 문제 해결 - 강제 버전 지정"""
        if self.driver:
            try:
                self.close_browser()
                time.sleep(2)
                print("[INFO] 기존 브라우저 종료 완료")
            except Exception as e:
                print(f"[WARNING] 기존 브라우저 종료 실패: {e}")
                self.driver = None

        # Chrome 137 버전 강제 지정으로 시도
        try:
            print("[INFO] Chrome 137 호환 ChromeDriver로 브라우저 시작...")
            options = self._create_minimal_safe_options()
            
            # Chrome 137 전용 ChromeDriver 사용
            self.driver = uc.Chrome(
                options=options,
                version_main=137,  # Chrome 137 버전 명시적 지정
                driver_executable_path=None,
                browser_executable_path=None
            )
            
            if self.driver:
                self._configure_minimal_settings()
                print("[INFO] Chrome 137 호환 브라우저 시작 완료")
                return True
                
        except Exception as e:
            print(f"[WARNING] Chrome 137 전용 시도 실패: {e}")
            self.driver = None

        # 백업: 버전 자동 감지로 시도
        try:
            print("[INFO] 버전 자동 감지로 재시도...")
            options = self._create_ultra_minimal_options()
            
            # 가장 기본적인 설정으로 시도
            self.driver = uc.Chrome(options=options)
            
            if self.driver:
                self.driver.implicitly_wait(5)
                print("[INFO] 자동 감지 브라우저 시작 완료")
                return True
                
        except Exception as e:
            print(f"[ERROR] 모든 브라우저 시작 시도 실패: {e}")
            print("[SOLUTION] 해결 방법:")
            print("1. Chrome을 최신 버전(138+)으로 업데이트")
            print("2. 또는 undetected_chromedriver를 재설치: pip install --upgrade undetected-chromedriver")
            print("3. 또는 수동으로 ChromeDriver 137 다운로드")
            self.driver = None
            return False

        return False

    def _create_minimal_safe_options(self):
        """Chrome 137에서 확실히 작동하는 최소 옵션"""
        options = uc.ChromeOptions()
        
        # Chrome 137에서 확실히 지원되는 기본 옵션만
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        
        # 자동화 감지 방지 (Chrome 137 호환)
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        print("[INFO] Chrome 137 최소 안전 옵션 설정 완료")
        return options

    def _create_ultra_minimal_options(self):
        """가장 기본적인 옵션 (최후의 수단)"""
        options = uc.ChromeOptions()
        
        # 필수 옵션만
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        print("[INFO] 울트라 미니멀 옵션 설정 완료")
        return options

    def _configure_minimal_settings(self):
        """최소한의 안전한 설정만 적용"""
        try:
            self.driver.implicitly_wait(10)
            self.driver.set_page_load_timeout(30)
            
            # Chrome 137에서 안전한 스크립트만 실행
            try:
                self.driver.execute_script("console.log('Browser initialized');")
                print("[INFO] 기본 JavaScript 실행 테스트 성공")
            except Exception as js_error:
                print(f"[WARNING] JavaScript 실행 실패: {js_error}")
            
            print("[INFO] 최소 설정 적용 완료")
            return True
            
        except Exception as e:
            print(f"[WARNING] 최소 설정 적용 중 오류: {e}")
            return False

    def _create_stealth_options(self):
        """최소한의 실험적 옵션 제거 버전"""
        options = uc.ChromeOptions()
        
        # Chrome 137에서 확실히 지원되는 옵션만 사용
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        
        # 임시 프로파일 (Windows 경로 호환)
        temp_profile = f"C:\\temp\\chrome_profile_{random.randint(1000, 9999)}"
        options.add_argument(f"--user-data-dir={temp_profile}")
        
        # 실험적 옵션 완전 제거 (Chrome 137 호환성 문제)
        print("[INFO] Chrome 137 호환 옵션 설정 완료 (실험적 옵션 제거)")
        return options

    def _configure_stealth_settings(self):
        """브라우저 시작 후 스텔스 설정 적용"""
        try:
            # 기본 타임아웃 설정
            self.driver.implicitly_wait(10)
            self.driver.set_page_load_timeout(30)
            
            # 자동화 관련 JavaScript 속성 제거
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Navigator 속성들을 실제 브라우저처럼 설정
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en'],
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)
            
            print("[INFO] 스텔스 설정 적용 완료")
            return True
            
        except Exception as e:
            print(f"[WARNING] 스텔스 설정 적용 중 오류: {e}")
            return False

    def open_site(self, url, wait_for_cloudflare=True):
        """Cloudflare 체크를 고려한 사이트 열기"""
        try:
            if not self.driver:
                print("[INFO] 브라우저가 실행되지 않아 start_browser() 호출")
                start_success = self.start_browser()
                if not start_success:
                    print("[ERROR] 브라우저 시작 실패")
                    return False

            # URL 형식 검증 및 수정
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            print(f"[INFO] 사이트 이동: {url}")
            
            # 랜덤 지연으로 자연스럽게
            time.sleep(random.uniform(1, 3))
            
            self.driver.get(url)
            
            if wait_for_cloudflare:
                return self._handle_cloudflare_check()
            else:
                time.sleep(2)
                return True
                
        except Exception as e:
            print(f"[ERROR] 사이트 열기 실패: {e}")
            return False

    def _handle_cloudflare_check(self):
        """Cloudflare 보안 검사 처리"""
        try:
            print("[INFO] Cloudflare 보안 검사 대기 중...")
            
            # Cloudflare 체크 페이지 감지
            max_wait_time = 30  # 최대 30초 대기
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                current_url = self.driver.current_url
                page_source = self.driver.page_source.lower()
                
                # Cloudflare 체크 페이지 패턴 감지
                cf_patterns = [
                    "checking your browser",
                    "verifying you are human",
                    "please wait",
                    "security check",
                    "cloudflare",
                    "작업을 완료하여 사람인지 확인"
                ]
                
                is_cf_page = any(pattern in page_source for pattern in cf_patterns)
                
                if is_cf_page:
                    print(f"[INFO] Cloudflare 보안 검사 진행 중... ({int(time.time() - start_time)}초)")
                    
                    # 자연스러운 마우스 움직임 시뮬레이션
                    self._simulate_human_behavior()
                    
                    time.sleep(2)
                    continue
                else:
                    print("[INFO] Cloudflare 보안 검사 통과 완료")
                    return True
            
            # 타임아웃 발생
            print("[WARNING] Cloudflare 보안 검사 타임아웃")
            return False
            
        except Exception as e:
            print(f"[ERROR] Cloudflare 처리 중 오류: {e}")
            return False

    def _simulate_human_behavior(self):
        """사람처럼 행동하는 패턴 시뮬레이션"""
        try:
            # 랜덤한 마우스 움직임
            self.driver.execute_script("""
                // 랜덤한 스크롤
                window.scrollBy(0, Math.random() * 100 - 50);
                
                // 마우스 이벤트 시뮬레이션
                document.dispatchEvent(new MouseEvent('mousemove', {
                    clientX: Math.random() * window.innerWidth,
                    clientY: Math.random() * window.innerHeight
                }));
            """)
            
            # 랜덤 지연
            time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            print(f"[WARNING] 인간 행동 시뮬레이션 실패: {e}")

    def wait_for_element(self, selector, timeout=10):
        """요소가 나타날 때까지 대기"""
        try:
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return element
        except Exception as e:
            print(f"[WARNING] 요소 대기 실패: {e}")
            return None

    def close_browser(self):
        """브라우저 종료"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                print("[INFO] 브라우저 종료됨")
                return True
            except Exception as e:
                print(f"[WARNING] 브라우저 종료 중 오류: {e}")
                self.driver = None
                return False
        return True

    def get_page_source(self):
        """현재 페이지의 HTML 가져오기"""
        if not self.driver:
            print("[ERROR] 브라우저가 실행되지 않음")
            return None
        return self.driver.page_source

    def get_redirected_url(self):
        """현재 브라우저의 URL을 가져오는 함수"""
        if not self.driver:
            print("[ERROR] WebDriver가 실행되지 않음")
            return None
        return self.driver.current_url

    def is_driver_alive(self):
        """드라이버가 살아있는지 확인"""
        try:
            if not self.driver:
                return False
            self.driver.current_url
            return True
        except Exception:
            return False