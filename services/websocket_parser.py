# services/websocket_parser.py
import json
import time
import logging
from typing import Optional, Dict, Any, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class WebSocketParser:
    """에볼루션 로비에서 웹소켓 URL을 자동으로 파싱하는 서비스"""
    
    def __init__(self, devtools):
        self.devtools = devtools
        self.driver = devtools.driver
        self.logger = logging.getLogger(__name__)
        self.websocket_url = None
        self.network_events = []
        
    def parse_websocket_url_from_lobby(self, timeout=30) -> Optional[str]:
        """
        에볼루션 로비에서 웹소켓 URL을 자동으로 파싱합니다.
        
        Args:
            timeout (int): 타임아웃 시간 (초)
            
        Returns:
            Optional[str]: 파싱된 웹소켓 URL 또는 None
        """
        try:
            self.logger.info("웹소켓 URL 자동 파싱 시작")
            
            # 1. 네트워크 이벤트 리스너 설정
            self._setup_network_listeners()
            
            # 2. 로비 페이지 새로고침하여 네트워크 트래픽 캡처
            self.logger.info("로비 페이지 새로고침하여 네트워크 트래픽 캡처")
            self.driver.refresh()
            time.sleep(3)
            
            # 3. 웹소켓 연결 감지 시도
            websocket_url = self._detect_websocket_from_cdp(timeout)
            
            if websocket_url:
                self.websocket_url = websocket_url
                self.logger.info(f"웹소켓 URL 파싱 성공: {websocket_url}")
                return websocket_url
            else:
                self.logger.warning("웹소켓 URL을 찾을 수 없습니다. 대안 방법 시도")
                return self._try_alternative_methods()
                
        except Exception as e:
            self.logger.error(f"웹소켓 URL 파싱 중 오류: {e}")
            return None
    
    def _setup_network_listeners(self):
        """Chrome DevTools Protocol을 사용하여 네트워크 이벤트 리스너 설정"""
        try:
            # 네트워크 도메인 활성화
            self.driver.execute_cdp_cmd('Network.enable', {})
            self.driver.execute_cdp_cmd('Runtime.enable', {})
            
            # 네트워크 이벤트 리스너 설정
            self.driver.execute_cdp_cmd('Network.setRequestInterception', {'patterns': [{'urlPattern': '*'}]})
            
            self.logger.info("네트워크 이벤트 리스너 설정 완료")
        except Exception as e:
            self.logger.warning(f"네트워크 이벤트 리스너 설정 실패: {e}")
    
    def _detect_websocket_from_cdp(self, timeout=30) -> Optional[str]:
        """
        Chrome DevTools Protocol을 사용하여 웹소켓 URL 감지
        
        Args:
            timeout (int): 타임아웃 시간
            
        Returns:
            Optional[str]: 감지된 웹소켓 URL
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # CDP 명령으로 네트워크 이벤트 가져오기
                events = self._get_network_events()
                
                for event in events:
                    websocket_url = self._extract_websocket_url_from_event(event)
                    if websocket_url:
                        return websocket_url
                
                time.sleep(0.5)  # 짧은 대기
                
            except Exception as e:
                self.logger.warning(f"CDP 이벤트 분석 중 오류: {e}")
                time.sleep(1)
        
        return None
    
    def _get_network_events(self) -> List[Dict[str, Any]]:
        """CDP를 통해 네트워크 이벤트 가져오기"""
        try:
            # Performance 로그 대신 CDP 명령 사용
            result = self.driver.execute_cdp_cmd('Network.getResponseBody', {})
            return [result] if result else []
        except:
            # 대안: JavaScript로 네트워크 요청 모니터링
            return self._get_network_events_via_javascript()
    
    def _get_network_events_via_javascript(self) -> List[Dict[str, Any]]:
        """JavaScript를 통해 네트워크 이벤트 모니터링"""
        try:
            js_code = """
            // 네트워크 요청을 모니터링하는 JavaScript
            if (!window.networkMonitor) {
                window.networkMonitor = {
                    requests: [],
                    originalFetch: window.fetch,
                    originalWebSocket: window.WebSocket
                };
                
                // Fetch API 모니터링
                window.fetch = function(...args) {
                    const url = args[0];
                    window.networkMonitor.requests.push({
                        type: 'fetch',
                        url: url,
                        timestamp: Date.now()
                    });
                    return window.networkMonitor.originalFetch.apply(this, args);
                };
                
                // WebSocket 생성 모니터링
                window.WebSocket = function(url, protocols) {
                    window.networkMonitor.requests.push({
                        type: 'websocket',
                        url: url,
                        timestamp: Date.now()
                    });
                    return new window.networkMonitor.originalWebSocket(url, protocols);
                };
                
                // 기존 WebSocket 프로토타입 유지
                window.WebSocket.prototype = window.networkMonitor.originalWebSocket.prototype;
            }
            
            return window.networkMonitor.requests;
            """
            
            result = self.driver.execute_script(js_code)
            return result if result else []
            
        except Exception as e:
            self.logger.warning(f"JavaScript 네트워크 모니터링 실패: {e}")
            return []
    
    def _extract_websocket_url_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """이벤트에서 웹소켓 URL 추출"""
        try:
            if event.get('type') == 'websocket':
                url = event.get('url', '')
                if self._is_evolution_websocket(url):
                    self.logger.info(f"웹소켓 연결 감지: {url}")
                    return url
            return None
        except Exception as e:
            self.logger.warning(f"이벤트 분석 중 오류: {e}")
            return None
    
    def _is_evolution_websocket(self, url: str) -> bool:
        """
        에볼루션 웹소켓 URL인지 확인
        
        Args:
            url (str): 확인할 URL
            
        Returns:
            bool: 에볼루션 웹소켓 여부
        """
        # 에볼루션 웹소켓 URL 패턴들
        evolution_patterns = [
            'ws://',
            'wss://',
            'evolution',
            'game-server',
            'socket'
        ]
        
        url_lower = url.lower()
        
        # 웹소켓 프로토콜 확인
        if not (url_lower.startswith('ws://') or url_lower.startswith('wss://')):
            return False
        
        # 에볼루션 관련 키워드 확인
        for pattern in evolution_patterns[2:]:  # ws:// wss:// 제외
            if pattern in url_lower:
                return True
        
        # 포트나 경로 패턴으로도 확인
        if any(port in url for port in [':8080', ':3000', ':9090', ':8443']):
            return True
            
        return False
    
    def _try_alternative_methods(self) -> Optional[str]:
        """
        대안 방법으로 웹소켓 URL 찾기
        
        Returns:
            Optional[str]: 찾은 웹소켓 URL
        """
        try:
            # 방법 1: JavaScript로 WebSocket 객체 검색
            websocket_url = self._search_websocket_via_javascript()
            if websocket_url:
                return websocket_url
            
            # 방법 2: 페이지 소스에서 웹소켓 URL 패턴 검색
            websocket_url = self._search_websocket_in_page_source()
            if websocket_url:
                return websocket_url
            
            # 방법 3: Local Storage나 Session Storage 확인
            websocket_url = self._search_websocket_in_storage()
            if websocket_url:
                return websocket_url
            
            # 방법 4: 브라우저 네트워크 탭 분석
            websocket_url = self._analyze_browser_network_tab()
            if websocket_url:
                return websocket_url
            
            return None
            
        except Exception as e:
            self.logger.error(f"대안 방법 시도 중 오류: {e}")
            return None
    
    def _search_websocket_via_javascript(self) -> Optional[str]:
        """JavaScript를 통해 활성화된 WebSocket 연결 검색"""
        try:
            # JavaScript 코드로 WebSocket 연결 정보 찾기
            js_code = """
            // WebSocket 연결 정보를 찾는 JavaScript
            var websockets = [];
            var foundUrls = [];
            
            // 전역 객체에서 WebSocket 인스턴스 검색
            function findWebSockets(obj, visited = new Set()) {
                if (visited.has(obj) || obj === null || typeof obj !== 'object') {
                    return;
                }
                visited.add(obj);
                
                for (let key in obj) {
                    try {
                        let value = obj[key];
                        if (value instanceof WebSocket) {
                            websockets.push({
                                url: value.url,
                                readyState: value.readyState,
                                protocol: value.protocol
                            });
                            foundUrls.push(value.url);
                        } else if (typeof value === 'object' && value !== null) {
                            findWebSockets(value, visited);
                        }
                    } catch (e) {
                        // 접근 불가능한 프로퍼티 무시
                    }
                }
            }
            
            // window 객체에서 WebSocket 검색
            findWebSockets(window);
            
            // 추가: 프레임 내부도 검색
            try {
                for (let i = 0; i < window.frames.length; i++) {
                    findWebSockets(window.frames[i]);
                }
            } catch (e) {
                // 프레임 접근 실패 무시
            }
            
            // 결과 반환
            return foundUrls.length > 0 ? foundUrls : null;
            """
            
            result = self.driver.execute_script(js_code)
            if result:
                for url in result:
                    if self._is_evolution_websocket(url):
                        self.logger.info(f"JavaScript로 웹소켓 URL 발견: {url}")
                        return url
                        
        except Exception as e:
            self.logger.warning(f"JavaScript 웹소켓 검색 실패: {e}")
        
        return None
    
    def _search_websocket_in_page_source(self) -> Optional[str]:
        """페이지 소스에서 웹소켓 URL 패턴 검색"""
        try:
            import re
            
            page_source = self.driver.page_source
            
            # 웹소켓 URL 패턴들
            websocket_patterns = [
                r'wss?://[^\s\'">\]]+',  # 기본 웹소켓 URL 패턴
                r'"(wss?://[^"]+)"',     # 따옴표로 둘러싸인 패턴
                r"'(wss?://[^']+)'",     # 작은따옴표로 둘러싸인 패턴
                r'url:\s*["\']?(wss?://[^"\'>\s]+)["\']?',  # url: 패턴
                r'websocket["\']?\s*:\s*["\']?(wss?://[^"\'>\s]+)["\']?',  # websocket: 패턴
            ]
            
            for pattern in websocket_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for match in matches:
                    # 튜플인 경우 첫 번째 요소 사용
                    url = match[0] if isinstance(match, tuple) else match
                    
                    if self._is_evolution_websocket(url):
                        self.logger.info(f"페이지 소스에서 웹소켓 URL 발견: {url}")
                        return url
                        
        except Exception as e:
            self.logger.warning(f"페이지 소스 검색 실패: {e}")
        
        return None
    
    def _search_websocket_in_storage(self) -> Optional[str]:
        """Local Storage나 Session Storage에서 웹소켓 URL 검색"""
        try:
            # Local Storage 검색
            local_storage = self.driver.execute_script("return window.localStorage;")
            if local_storage:
                for key, value in local_storage.items():
                    if isinstance(value, str) and self._is_evolution_websocket(value):
                        self.logger.info(f"Local Storage에서 웹소켓 URL 발견: {value}")
                        return value
            
            # Session Storage 검색
            session_storage = self.driver.execute_script("return window.sessionStorage;")
            if session_storage:
                for key, value in session_storage.items():
                    if isinstance(value, str) and self._is_evolution_websocket(value):
                        self.logger.info(f"Session Storage에서 웹소켓 URL 발견: {value}")
                        return value
                        
        except Exception as e:
            self.logger.warning(f"Storage 검색 실패: {e}")
        
        return None
    
    def _analyze_browser_network_tab(self) -> Optional[str]:
        """브라우저 네트워크 탭 분석을 통한 웹소켓 URL 찾기"""
        try:
            # CDP를 사용하여 네트워크 요청 분석
            result = self.driver.execute_cdp_cmd('Network.getResponseBody', {})
            
            # 리소스 타입이 WebSocket인 것 찾기
            js_code = """
            // Performance API를 사용하여 네트워크 요청 분석
            var entries = performance.getEntriesByType('resource');
            var websocketUrls = [];
            
            entries.forEach(function(entry) {
                if (entry.name && (entry.name.startsWith('ws://') || entry.name.startsWith('wss://'))) {
                    websocketUrls.push(entry.name);
                }
            });
            
            return websocketUrls;
            """
            
            urls = self.driver.execute_script(js_code)
            if urls:
                for url in urls:
                    if self._is_evolution_websocket(url):
                        self.logger.info(f"브라우저 네트워크 탭에서 웹소켓 URL 발견: {url}")
                        return url
            
        except Exception as e:
            self.logger.warning(f"브라우저 네트워크 탭 분석 실패: {e}")
        
        return None
    
    def get_websocket_url_with_game_room(self, room_name: str, timeout=30) -> Optional[str]:
        """
        특정 게임 방에 입장하여 웹소켓 URL을 가져옵니다.
        
        Args:
            room_name (str): 입장할 방 이름
            timeout (int): 타임아웃 시간
            
        Returns:
            Optional[str]: 방 전용 웹소켓 URL
        """
        try:
            self.logger.info(f"방 '{room_name}' 입장하여 웹소켓 URL 파싱 시도")
            
            # 1. 네트워크 이벤트 리스너 설정
            self._setup_network_listeners()
            
            # 2. 방 입장 시도
            if not self._enter_game_room(room_name):
                return None
            
            # 3. 방 입장 후 웹소켓 연결 감지
            websocket_url = self._detect_websocket_from_cdp(timeout)
            
            if websocket_url:
                self.logger.info(f"방 전용 웹소켓 URL 파싱 성공: {websocket_url}")
                return websocket_url
            else:
                self.logger.warning("방 전용 웹소켓 URL을 찾을 수 없습니다.")
                return None
                
        except Exception as e:
            self.logger.error(f"방 전용 웹소켓 URL 파싱 중 오류: {e}")
            return None
    
    def _enter_game_room(self, room_name: str) -> bool:
        """게임 방에 입장"""
        try:
            # iframe으로 전환
            iframe = self.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.driver.switch_to.frame(iframe)
            
            # 방 찾기 및 클릭
            room_elements = self.driver.find_elements(By.CSS_SELECTOR, ".tile--5d2e6")
            
            for element in room_elements:
                if room_name in element.text:
                    element.click()
                    self.logger.info(f"방 '{room_name}' 클릭 완료")
                    time.sleep(3)  # 방 로딩 대기
                    return True
            
            self.logger.warning(f"방 '{room_name}'을 찾을 수 없습니다.")
            return False
            
        except Exception as e:
            self.logger.error(f"방 입장 중 오류: {e}")
            return False
        finally:
            # iframe에서 나오기
            try:
                self.driver.switch_to.default_content()
            except:
                pass
    
    def validate_websocket_url(self, url: str) -> bool:
        """
        웹소켓 URL 유효성 검증
        
        Args:
            url (str): 검증할 웹소켓 URL
            
        Returns:
            bool: 유효한지 여부
        """
        try:
            if not url:
                return False
            
            # 기본 웹소켓 URL 형식 확인
            if not (url.startswith('ws://') or url.startswith('wss://')):
                return False
            
            # 에볼루션 관련 패턴 확인
            if not self._is_evolution_websocket(url):
                return False
            
            self.logger.info(f"웹소켓 URL 유효성 검증 성공: {url}")
            return True
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 검증 중 오류: {e}")
            return False
    
    def get_current_websocket_url(self) -> Optional[str]:
        """현재 저장된 웹소켓 URL 반환"""
        return self.websocket_url