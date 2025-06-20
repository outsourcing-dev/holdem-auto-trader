# services/websocket_parser.py
"""
WebSocketParser - Performance 로그와 CDP 이벤트를 이용한 웹소켓 URL 자동 탐지
2~3회 새로고침 시도, 사용자 행동 없이 최대한 자동으로 웹소켓 주소 탐지
"""
import time
import logging
import re
from typing import List, Optional
import asyncio
from playwright.async_api import async_playwright

class WebSocketParser:
    def __init__(self, devtools_controller, logger=None):
        self.devtools = devtools_controller
        self.logger = logger or logging.getLogger(__name__)
        self.found_websockets = set()  # 중복 방지용
        self.max_refresh_attempts = 3
        self.detection_timeout = 30  # 30초 타임아웃

    def auto_detect_websocket_urls(self) -> List[str]:
        """
        Playwright를 이용한 웹소켓 URL 자동 탐지 (동기 wrapper)
        """
        target_url = self.devtools.get_redirected_url() if self.devtools else None
        if not target_url:
            raise ValueError("DevTools에서 현재 URL을 가져올 수 없습니다.")

        return asyncio.run(self._auto_detect_websocket_urls_with_playwright(target_url))

    async def _auto_detect_websocket_urls_with_playwright(self, target_url: str) -> List[str]:
        websocket_urls = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            page.on("websocket", lambda ws: websocket_urls.append(ws.url))

            self.logger.info(f"🌐 {target_url} 접속 중 (Playwright)...")
            await page.goto(target_url)

            await page.wait_for_timeout(5000)  # 5초 대기 (필요시 늘리세요)

            await browser.close()

        # 중복 제거 후 반환
        unique_urls = list(set(websocket_urls))
        self.logger.info(f"✅ Playwright로 탐지한 웹소켓: {unique_urls}")
        return unique_urls
    
    def _collect_websockets_from_current_state(self):
        """현재 상태에서 웹소켓 수집"""
        try:
            # Performance 로그에서 웹소켓 수집
            performance_websockets = self.devtools.get_websocket_connections_from_logs()
            
            for ws_url in performance_websockets:
                if self._is_valid_websocket_url(ws_url):
                    self.found_websockets.add(ws_url)
                    self.logger.info(f"🔍 Performance 로그에서 웹소켓 발견: {ws_url[:80]}...")
            
            # CDP 이벤트에서 웹소켓 수집
            cdp_events = self.devtools.get_cdp_network_events()
            # CDP 이벤트 처리 로직은 DevToolsController에서 구현됨
            
            # JavaScript를 통한 추가 탐지
            js_websockets = self._detect_websockets_via_javascript()
            for ws_url in js_websockets:
                if self._is_valid_websocket_url(ws_url):
                    self.found_websockets.add(ws_url)
                    self.logger.info(f"🔍 JavaScript에서 웹소켓 발견: {ws_url[:80]}...")
                    
        except Exception as e:
            self.logger.warning(f"웹소켓 수집 중 오류: {e}")

    def _refresh_and_detect(self) -> bool:
        """페이지 새로고침 후 웹소켓 탐지"""
        try:
            # 새로고침 전 로그 클리어
            self.devtools.get_performance_logs()  # 기존 로그 소비
            
            # 페이지 새로고침
            if not self.devtools.refresh_page():
                return False
            
            # 새로고침 후 웹소켓 연결 대기
            start_time = time.time()
            websockets_before = len(self.found_websockets)
            
            while time.time() - start_time < 10:  # 10초 동안 대기
                self._collect_websockets_from_current_state()
                
                # 새로운 웹소켓이 발견되면 성공
                if len(self.found_websockets) > websockets_before:
                    return True
                
                time.sleep(1)
            
            return False
            
        except Exception as e:
            self.logger.warning(f"새로고침 후 탐지 실패: {e}")
            return False

    def _trigger_interactions_for_websocket_detection(self):
        """자동 상호작용으로 웹소켓 연결 유도"""
        try:
            # 스크롤 이벤트로 지연 로딩 콘텐츠 유도
            scroll_script = """
            window.scrollTo(0, document.body.scrollHeight);
            setTimeout(() => window.scrollTo(0, 0), 1000);
            """
            self.devtools.execute_javascript(scroll_script)
            time.sleep(2)
            
            # 버튼이나 링크 클릭 시뮬레이션 (안전한 요소만)
            safe_interaction_script = """
            // 안전한 상호작용 요소 찾기 (로고, 새로고침 버튼 등)
            const safeSelectors = [
                '.logo', '.refresh-btn', '.reload-button', 
                '[data-testid="refresh"]', '.casino-logo'
            ];
            
            for (let selector of safeSelectors) {
                const elements = document.querySelectorAll(selector);
                if (elements.length > 0) {
                    const element = elements[0];
                    if (element.offsetParent !== null) { // 화면에 보이는지 확인
                        element.click();
                        break;
                    }
                }
            }
            
            // 마우스 이동 이벤트 시뮬레이션
            const event = new MouseEvent('mousemove', {
                view: window,
                bubbles: true,
                cancelable: true,
                clientX: Math.random() * window.innerWidth,
                clientY: Math.random() * window.innerHeight
            });
            document.dispatchEvent(event);
            
            return 'interactions_triggered';
            """
            
            result = self.devtools.execute_javascript(safe_interaction_script)
            self.logger.info(f"자동 상호작용 실행: {result}")
            
            # 상호작용 후 웹소켓 재확인
            time.sleep(3)
            self._collect_websockets_from_current_state()
            
        except Exception as e:
            self.logger.warning(f"자동 상호작용 중 오류: {e}")

    def _detect_websockets_via_javascript(self) -> List[str]:
        """JavaScript를 통한 웹소켓 URL 탐지"""
        websocket_detection_script = """
        // 전역 WebSocket 객체 후킹으로 연결 감지
        const foundWebSockets = [];
        
        // 기존 WebSocket 생성자 백업
        if (!window.originalWebSocket) {
            window.originalWebSocket = window.WebSocket;
            
            // WebSocket 생성자 오버라이드
            window.WebSocket = function(url, protocols) {
                foundWebSockets.push(url);
                console.log('WebSocket 연결 감지:', url);
                return new window.originalWebSocket(url, protocols);
            };
        }
        
        // 페이지 소스에서 웹소켓 URL 패턴 검색
        const pageContent = document.documentElement.outerHTML;
        const wsUrlPattern = /wss?:\\/\\/[^\\s"'`]+/gi;
        const matches = pageContent.match(wsUrlPattern) || [];
        
        // 스크립트 태그 내용에서 웹소켓 URL 검색
        const scripts = document.querySelectorAll('script');
        scripts.forEach(script => {
            if (script.textContent) {
                const scriptMatches = script.textContent.match(wsUrlPattern) || [];
                matches.push(...scriptMatches);
            }
        });
        
        // Performance API를 통한 리소스 확인
        try {
            const performanceEntries = performance.getEntries();
            performanceEntries.forEach(entry => {
                if (entry.name && (entry.name.startsWith('ws://') || entry.name.startsWith('wss://'))) {
                    matches.push(entry.name);
                }
            });
        } catch (e) {
            console.log('Performance API 접근 실패:', e);
        }
        
        // 중복 제거 및 반환
        const uniqueWebSockets = [...new Set([...foundWebSockets, ...matches])];
        return uniqueWebSockets.filter(url => url && (url.startsWith('ws://') || url.startsWith('wss://')));
        """
        
        try:
            result = self.devtools.execute_javascript(websocket_detection_script)
            return result if isinstance(result, list) else []
            
        except Exception as e:
            self.logger.warning(f"JavaScript 웹소켓 탐지 실패: {e}")
            return []

    def _is_valid_websocket_url(self, url: str) -> bool:
        """웹소켓 URL 유효성 검증"""
        if not url or not isinstance(url, str):
            return False
        
        # 기본 형식 확인
        if not (url.startswith('ws://') or url.startswith('wss://')):
            return False
        
        # 최소 길이 확인
        if len(url) < 10:
            return False
        
        # 에볼루션 카지노 관련 패턴 확인 (선택적)
        evolution_patterns = [
            'evo-games.com',
            'evolution',
            'socket',
            'lobby'
        ]
        
        # 에볼루션 관련 URL이면 우선순위 부여
        is_evolution_related = any(pattern in url.lower() for pattern in evolution_patterns)
        
        return True  # 기본적으로 모든 웹소켓 URL 허용

    def _validate_and_filter_websockets(self, websocket_urls: List[str]) -> List[str]:
        """웹소켓 URL 검증 및 필터링"""
        valid_urls = []
        
        for url in websocket_urls:
            if not self._is_valid_websocket_url(url):
                continue
            
            # 중복 확인 (파라미터 제외한 베이스 URL 기준)
            base_url = url.split('?')[0]
            if any(base_url in valid_url for valid_url in valid_urls):
                continue
            
            valid_urls.append(url)
        
        # 에볼루션 관련 URL 우선순위 정렬
        def sort_priority(url):
            priority = 0
            url_lower = url.lower()
            
            if 'evo-games.com' in url_lower:
                priority += 100
            if 'evolution' in url_lower:
                priority += 50
            if 'lobby' in url_lower:
                priority += 30
            if 'socket' in url_lower:
                priority += 20
            if url.startswith('wss://'):
                priority += 10
                
            return -priority  # 높은 우선순위가 앞에 오도록
        
        valid_urls.sort(key=sort_priority)
        
        return valid_urls

    def get_best_websocket_url(self) -> Optional[str]:
        """최적의 웹소켓 URL 하나 반환"""
        urls = self.auto_detect_websocket_urls()
        
        if not urls:
            return None
        
        # 가장 우선순위가 높은 URL 반환
        best_url = urls[0]
        self.logger.info(f"🎯 최적 웹소켓 URL 선택: {best_url}")
        
        return best_url

    def monitor_websocket_connections(self, duration_seconds: int = 30) -> List[str]:
        """
        지정된 시간 동안 웹소켓 연결을 모니터링
        
        Args:
            duration_seconds: 모니터링 시간 (초)
            
        Returns:
            list: 모니터링 기간 중 발견된 웹소켓 URL들
        """
        self.logger.info(f"🔍 {duration_seconds}초 동안 웹소켓 연결 모니터링 시작")
        
        start_time = time.time()
        initial_count = len(self.found_websockets)
        
        while time.time() - start_time < duration_seconds:
            self._collect_websockets_from_current_state()
            time.sleep(2)  # 2초마다 확인
        
        new_websockets = len(self.found_websockets) - initial_count
        self.logger.info(f"✅ 모니터링 완료: {new_websockets}개의 새로운 웹소켓 발견")
        
        return list(self.found_websockets)