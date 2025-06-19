import undetected_chromedriver as uc
import time
import os
import re
import subprocess
import platform
import logging

class DevToolsController:
    def __init__(self, logger=None):
        self.driver = None  # 초기에는 브라우저 실행 X
        self.logger = logger or logging.getLogger(__name__)

    def get_chrome_version(self):
        """현재 시스템에 설치된 Chrome 브라우저의 버전을 감지"""
        version = None
        system = platform.system()
        
        try:
            if system == "Windows":
                # Windows에서 Chrome 레지스트리 경로
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
            
            # 버전에서 메이저 버전 추출 (예: "92.0.4515.107" -> 92)
            if version:
                version_match = re.search(r'(\d+)\.', version)
                if version_match:
                    return int(version_match.group(1))
        
        except Exception as e:
            print(f"[WARNING] Chrome 버전 감지 중 오류 발생: {e}")
            print("[INFO] 기본 ChromeDriver 사용")
        
        return None  # 버전을 감지할 수 없는 경우

    def start_browser(self):
        """Chrome 브라우저 실행 (Performance Logging 활성화) - undetected_chromedriver 호환 버전"""
        # 이미 실행 중인 경우 먼저 닫기
        if self.driver:
            try:
                self.close_browser()
                time.sleep(1)  # 브라우저가 완전히 종료될 때까지 대기
            except Exception as e:
                print(f"[WARNING] 기존 브라우저 종료 실패: {e}")
                self.driver = None  # 참조 초기화
        
        # 첫 번째 시도: 간단한 Performance Logging 설정
        options = self._create_simple_chrome_options()
        if self._try_start_browser_with_options(options):
            return True
        
        # 두 번째 시도: 최소한의 설정
        print("[INFO] 최소한의 설정으로 재시도...")
        options = self._create_minimal_chrome_options()
        if self._try_start_browser_with_options(options):
            return True
        
        # 세 번째 시도: 기본 설정
        print("[INFO] 기본 설정으로 재시도...")
        options = self._create_basic_chrome_options()
        if self._try_start_browser_with_options(options):
            return True
        
        print("[ERROR] 모든 설정으로 브라우저 시작 실패")
        return False

    def _try_start_browser_with_options(self, options):
        """주어진 옵션으로 브라우저 시작 시도"""
        try:
            chrome_version = self.get_chrome_version()
            
            if chrome_version:
                print(f"[INFO] Chrome 버전 {chrome_version}으로 시도")
                try:
                    self.driver = uc.Chrome(options=options, version_main=chrome_version)
                except Exception as version_error:
                    print(f"[WARNING] 버전 지정 실행 실패: {version_error}")
                    # 버전 지정 실패 시 기본 설정으로 시도
                    self.driver = uc.Chrome(options=options)
            else:
                self.driver = uc.Chrome(options=options)
            
            # 브라우저 시작 성공 시 추가 설정
            if self.driver:
                self._post_browser_setup()
                print("[INFO] 브라우저 시작 및 설정 완료")
                return True
                
        except Exception as e:
            print(f"[ERROR] 브라우저 시작 시도 실패: {e}")
            self.driver = None
            
        return False

    def _create_simple_chrome_options(self):
        """Performance Logging 강제 활성화"""
        try:
            options = uc.ChromeOptions()
            options.headless = False
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Performance 로그 강제 활성화
            options.add_argument("--enable-logging")
            options.add_argument("--log-level=0")
            options.add_argument("--enable-network-service-logging")
            
            # 실험적 옵션 추가
            options.add_experimental_option('perfLoggingPrefs', {
                'enableNetwork': True,
                'enablePage': True,
                'enableTimeline': True
            })
            
            options.add_experimental_option('loggingPrefs', {
                'performance': 'ALL',
                'browser': 'ALL'
            })
            
            options.add_experimental_option("useAutomationExtension", False)
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            
            print("[INFO] Performance Logging 강제 활성화 설정 완료")
            return options
            
        except Exception as e:
            print(f"[ERROR] Performance 옵션 설정 오류: {e}")
            return self._create_minimal_chrome_options()
        
    def _create_minimal_chrome_options(self):
        """최소한의 Chrome 옵션 (안전한 설정)"""
        try:
            options = uc.ChromeOptions()
            options.headless = False
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--enable-logging")
            options.add_argument("--log-level=0")
            
            print("[INFO] 최소한의 Chrome 옵션 설정 완료")
            return options
            
        except Exception as e:
            print(f"[ERROR] 최소한의 Chrome 옵션 생성 오류: {e}")
            return self._create_basic_chrome_options()

    def _create_basic_chrome_options(self):
        """기본 Chrome 옵션 (백업용)"""
        try:
            options = uc.ChromeOptions()
            options.headless = False
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            print("[INFO] 기본 Chrome 옵션 설정 완료")
            return options
            
        except Exception as e:
            print(f"[ERROR] 기본 Chrome 옵션 생성 실패: {e}")
            # 최후의 수단
            return uc.ChromeOptions()

    def _post_browser_setup(self):
        """브라우저 시작 후 추가 설정"""
        try:
            if not self.driver:
                return False
            
            # 기본 설정
            self.driver.implicitly_wait(10)
            self.driver.set_page_load_timeout(30)
            
            # 간단한 테스트 페이지로 이동
            self.driver.get("data:text/html,<html><body><h1>Performance Test</h1></body></html>")
            time.sleep(2)
            
            # Performance Logging 테스트
            performance_available = self._test_performance_logging()
            
            if performance_available:
                print("[INFO] ✅ Performance Logging 사용 가능")
            else:
                print("[WARNING] ⚠️ Performance Logging 제한적 사용")
            
            # CDP 설정 시도
            self._setup_cdp_if_available()
            
            # WebSocket 후킹 설정
            self._setup_websocket_hooks()
            
            return True
            
        except Exception as e:
            print(f"[WARNING] 브라우저 후처리 설정 중 오류: {e}")
            return False

    def _test_performance_logging(self):
        """Performance Logging 사용 가능 여부 테스트"""
        try:
            logs = self.driver.get_log("performance")
            print(f"[INFO] Performance 로그 테스트 성공: {len(logs)}개")
            return True
        except Exception as e:
            print(f"[WARNING] Performance 로그 테스트 실패: {e}")
            return False

    def _setup_cdp_if_available(self):
        """CDP 사용 가능하면 설정"""
        try:
            # CDP 명령 테스트
            self.driver.execute_cdp_cmd('Runtime.evaluate', {'expression': '1+1'})
            
            # Network 도메인 활성화
            self.driver.execute_cdp_cmd('Network.enable', {})
            self.driver.execute_cdp_cmd('Runtime.enable', {})
            
            print("[INFO] ✅ CDP를 통한 Network 도메인 활성화 성공")
            return True
            
        except Exception as e:
            print(f"[WARNING] CDP 설정 실패 (무시하고 계속): {e}")
            return False

    def _setup_websocket_hooks(self):
        """WebSocket 연결 감지를 위한 JavaScript 후킹 설정"""
        try:
            websocket_hook_script = """
            // WebSocket 후킹을 위한 글로벌 저장소
            if (!window.websocketCapture) {
                window.websocketCapture = {
                    urls: [],
                    connections: [],
                    setupComplete: true
                };
                
                // 기존 WebSocket 생성자 백업
                window.OriginalWebSocket = window.WebSocket;
                
                // WebSocket 생성자 후킹
                window.WebSocket = function(url, protocols) {
                    console.log('🔗 WebSocket 연결 감지:', url);
                    window.websocketCapture.urls.push(url);
                    
                    const ws = new window.OriginalWebSocket(url, protocols);
                    window.websocketCapture.connections.push(ws);
                    
                    // 이벤트 리스너 추가
                    ws.addEventListener('open', function() {
                        console.log('📡 WebSocket 연결 열림:', url);
                    });
                    
                    return ws;
                };
                
                console.log('WebSocket 후킹 설정 완료');
            }
            
            return window.websocketCapture.setupComplete ? 'WebSocket 후킹 활성화됨' : 'WebSocket 후킹 실패';
            """
            
            result = self.driver.execute_script(websocket_hook_script)
            print(f"[INFO] WebSocket 후킹 설정: {result}")
            return True
            
        except Exception as e:
            print(f"[WARNING] WebSocket 후킹 설정 실패: {e}")
            return False

    def open_site(self, url):
        """버튼을 눌렀을 때만 브라우저를 실행하고 사이트 이동 - 에러 처리 강화"""
        try:
            # 브라우저가 없거나 실행 중이 아니면 새로 시작
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
            try:
                self.driver.get(url)
            except Exception as e:
                print(f"[ERROR] 페이지 이동 중 오류 발생: {e}")
                # 브라우저가 응답하지 않으면 재시작 시도
                print("[INFO] 브라우저 재시작 시도...")
                self.close_browser()
                time.sleep(1)
                start_success = self.start_browser()
                if start_success:
                    self.driver.get(url)
                else:
                    return False
                    
            time.sleep(2)  # 페이지 로딩 대기
            return True
        except Exception as e:
            print(f"[ERROR] 사이트 열기 실패: {e}")
            return False

    def close_browser(self):
        """브라우저 종료 - 에러 처리 강화"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None  # 종료 후 드라이버 변수 초기화
                print("[INFO] 브라우저 종료됨")
                return True
            except Exception as e:
                print(f"[WARNING] 브라우저 종료 중 오류: {e}")
                self.driver = None  # 오류 시에도 참조 초기화
                return False
        return True  # 이미 닫혀 있는 경우

    def get_page_source(self):
        """현재 페이지의 HTML 가져오기"""
        if not self.driver:
            print("[ERROR] 브라우저가 실행되지 않음")
            return None
        return self.driver.page_source  # HTML 반환

    def get_redirected_url(self):
        """현재 브라우저의 URL을 가져오는 함수"""
        if not self.driver:
            print("[ERROR] WebDriver가 실행되지 않음")
            return None
        return self.driver.current_url  # 현재 URL 반환
    
    def clear_browser_cache(self):
        """브라우저 캐시 및 쿠키 삭제"""
        try:
            if self.driver:
                self.driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                self.driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
                print("[INFO] 브라우저 캐시 및 쿠키 삭제 완료")
                return True
            return False
        except Exception as e:
            print(f"[ERROR] 캐시 삭제 중 오류: {e}")
            return False

    # ✅ Performance Logging 관련 메서드들 (안전한 버전)
    def get_performance_logs(self):
        """Performance 로그 안전하게 가져오기"""
        try:
            if not self.driver:
                return []
            
            return self.driver.get_log("performance")
            
        except Exception as e:
            print(f"[WARNING] Performance 로그 가져오기 실패: {e}")
            return []

    def get_browser_logs(self):
        """Browser 콘솔 로그 안전하게 가져오기"""
        try:
            if not self.driver:
                return []
            
            return self.driver.get_log("browser")
            
        except Exception as e:
            print(f"[WARNING] Browser 로그 가져오기 실패: {e}")
            return []

    def get_captured_websockets(self):
        """JavaScript 후킹으로 캡처된 웹소켓 URL들 가져오기"""
        try:
            if not self.driver:
                return []
            
            urls = self.driver.execute_script("""
                return window.websocketCapture ? 
                    window.websocketCapture.urls || [] : 
                    [];
            """)
            return urls or []
            
        except Exception as e:
            print(f"[WARNING] 캡처된 웹소켓 URL 가져오기 실패: {e}")
            return []

    def get_all_websocket_sources(self):
        """모든 소스에서 웹소켓 URL 수집"""
        try:
            all_websockets = []
            
            # 1. Performance 로그에서 수집
            perf_logs = self.get_performance_logs()
            for log in perf_logs:
                try:
                    import json
                    message = json.loads(log.get('message', '{}'))
                    log_message = message.get('message', {})
                    method = log_message.get('method', '')
                    params = log_message.get('params', {})
                    
                    # WebSocket 관련 이벤트 확인
                    if 'websocket' in method.lower() or 'ws' in method.lower():
                        url = params.get('url', '')
                        if url and ('ws://' in url or 'wss://' in url):
                            all_websockets.append(url)
                            
                except:
                    continue
            
            # 2. JavaScript 후킹에서 수집
            captured_urls = self.get_captured_websockets()
            all_websockets.extend(captured_urls)
            
            # 3. 콘솔 로그에서 수집
            browser_logs = self.get_browser_logs()
            for log in browser_logs:
                try:
                    message = log.get('message', '')
                    import re
                    ws_urls = re.findall(r'wss?://[^\s\'"]+', message)
                    all_websockets.extend(ws_urls)
                except:
                    continue
            
            # 중복 제거
            unique_websockets = list(set(all_websockets))
            
            print(f"[INFO] 전체 웹소켓 URL 수집: {len(unique_websockets)}개")
            return unique_websockets
            
        except Exception as e:
            print(f"[ERROR] 웹소켓 URL 수집 중 오류: {e}")
            return []

    def force_websocket_detection(self):
        """강제로 웹소켓 연결 감지 시도"""
        try:
            print("[INFO] 🔧 강제 웹소켓 감지 시작")
            
            if not self.driver:
                print("[ERROR] 드라이버가 없어 감지 불가")
                return []
            
            # 1. 현재 로그 수집
            initial_websockets = self.get_all_websocket_sources()
            
            # 2. 페이지 새로고침으로 네트워크 활동 유도
            try:
                current_url = self.driver.current_url
                if current_url and "data:" not in current_url:
                    print("[INFO] 페이지 새로고침으로 네트워크 활동 유도")
                    self.driver.refresh()
                    time.sleep(3)
            except Exception as refresh_error:
                print(f"[WARNING] 페이지 새로고침 실패: {refresh_error}")
            
            # 3. 추가 웹소켓 감지 스크립트 실행
            try:
                detection_script = """
                // 추가 웹소켓 감지 로직
                const resourceEntries = performance.getEntries();
                const wsUrls = [];
                
                for (const entry of resourceEntries) {
                    const name = entry.name || '';
                    if (name.includes('ws://') || name.includes('wss://')) {
                        wsUrls.push(name);
                    }
                }
                
                return wsUrls;
                """
                
                additional_urls = self.driver.execute_script(detection_script)
                initial_websockets.extend(additional_urls or [])
                
            except Exception as script_error:
                print(f"[WARNING] 추가 감지 스크립트 실패: {script_error}")
            
            # 4. 최종 수집
            final_websockets = self.get_all_websocket_sources()
            all_found = list(set(initial_websockets + final_websockets))
            
            print(f"[INFO] 강제 감지 완료: {len(all_found)}개 웹소켓 URL 발견")
            return all_found
            
        except Exception as e:
            print(f"[ERROR] 강제 웹소켓 감지 중 오류: {e}")
            return []

    def debug_logging_status(self):
        """현재 로깅 상태 디버깅 정보 출력"""
        try:
            if not self.driver:
                print("[ERROR] 드라이버가 실행되지 않음")
                return
            
            print("\n=== 로깅 상태 디버깅 ===")
            
            # 사용 가능한 로그 타입 확인
            try:
                log_types = self.driver.log_types
                print(f"사용 가능한 로그 타입: {log_types}")
            except Exception as e:
                print(f"로그 타입 확인 실패: {e}")
            
            # 각 로그 타입별 상태 확인
            log_type_tests = ['performance', 'browser', 'driver']
            
            for log_type in log_type_tests:
                try:
                    logs = self.driver.get_log(log_type)
                    print(f"{log_type} 로그: {len(logs)}개 항목")
                except Exception as e:
                    print(f"{log_type} 로그 실패: {e}")
            
            # Chrome 버전 정보
            try:
                capabilities = self.driver.capabilities
                version = capabilities.get('browserVersion', 'Unknown')
                print(f"Chrome 버전: {version}")
            except Exception as e:
                print(f"버전 정보 확인 실패: {e}")
            
            # 캡처된 웹소켓 URL 확인
            captured_urls = self.get_captured_websockets()
            print(f"캡처된 웹소켓 URL: {len(captured_urls)}개")
            for i, url in enumerate(captured_urls[:3]):  # 처음 3개만 표시
                print(f"  {i+1}: {url}")
            
            # 전체 웹소켓 수집 테스트
            all_websockets = self.get_all_websocket_sources()
            print(f"전체 수집된 웹소켓 URL: {len(all_websockets)}개")
            
            print("=== 디버깅 완료 ===\n")
            
        except Exception as e:
            print(f"[ERROR] 디버깅 정보 수집 실패: {e}")

    def is_driver_alive(self):
        """드라이버가 살아있는지 확인"""
        try:
            if not self.driver:
                return False
            
            # 간단한 명령으로 연결 상태 확인
            self.driver.current_url
            return True
            
        except Exception:
            return False