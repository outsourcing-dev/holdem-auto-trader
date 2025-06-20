# services/websocket_parser.py
"""
WebSocketParser - Playwright를 이용한 웹소켓 URL 자동 탐지
기존 Selenium 브라우저와 별개로 Playwright를 사용하여 정확한 웹소켓 주소를 파싱합니다.
"""
import time
import logging
import re
import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright

class WebSocketParser:
    def __init__(self, devtools_controller, logger=None):
        self.devtools = devtools_controller
        self.logger = logger or logging.getLogger(__name__)
        self.found_websockets = set()  # 중복 방지용
        self.max_refresh_attempts = 3
        self.detection_timeout = 45  # 45초 타임아웃 (에볼루션 로딩 고려)

    def auto_detect_websocket_urls(self) -> List[str]:
        """
        Playwright를 이용한 웹소켓 URL 자동 탐지 (동기 wrapper)
        """
        # 기존 브라우저에서 현재 URL 가져오기
        target_url = self._get_target_url()
        if not target_url:
            raise ValueError("기존 브라우저에서 현재 URL을 가져올 수 없습니다.")

        self.logger.info(f"🎯 대상 URL: {target_url}")
        
        # 비동기 함수 실행
        return asyncio.run(self._auto_detect_websocket_urls_with_playwright(target_url))

    def _get_target_url(self) -> Optional[str]:
        """기존 브라우저에서 현재 URL 가져오기"""
        try:
            if not self.devtools or not self.devtools.driver:
                return None
            
            # 에볼루션 창 찾기
            window_handles = self.devtools.driver.window_handles
            if len(window_handles) >= 2:
                # 에볼루션 창으로 전환
                self.devtools.driver.switch_to.window(window_handles[1])
                current_url = self.devtools.driver.current_url
                self.logger.info(f"기존 브라우저 URL: {current_url}")
                return current_url
            else:
                # 현재 창의 URL 사용
                return self.devtools.driver.current_url
                
        except Exception as e:
            self.logger.error(f"기존 브라우저 URL 가져오기 실패: {e}")
            return None

    async def _auto_detect_websocket_urls_with_playwright(self, target_url: str) -> List[str]:
        """Playwright를 이용한 실제 웹소켓 탐지"""
        websocket_urls = []
        
        self.logger.info("🚀 Playwright 브라우저 시작...")
        
        async with async_playwright() as p:
            # Chrome 브라우저 시작 (headless=False로 디버깅 가능)
            browser = await p.chromium.launch(
                headless=False,  # 디버깅을 위해 화면에 표시
                args=[
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            try:
                context = await browser.new_context()
                page = await context.new_page()

                # WebSocket 연결 감지 리스너 등록
                def on_websocket(ws):
                    url = ws.url
                    websocket_urls.append(url)
                    self.logger.info(f"📡 WebSocket 연결 감지: {url}")
                
                page.on("websocket", on_websocket)
                
                # 네트워크 요청 감지 (WebSocket 업그레이드 요청 포함)
                def on_request(request):
                    if 'websocket' in request.headers.get('upgrade', '').lower():
                        websocket_urls.append(request.url)
                        self.logger.info(f"🔌 WebSocket 업그레이드 요청 감지: {request.url}")
                
                page.on("request", on_request)

                self.logger.info(f"🌐 {target_url} 접속 중...")
                
                # 페이지 로드 (타임아웃 설정)
                try:
                    await page.goto(target_url, wait_until="networkidle", timeout=30000)
                    self.logger.info("✅ 페이지 로드 완료")
                except Exception as e:
                    self.logger.warning(f"페이지 로드 중 오류 (계속 진행): {e}")
                
                # 페이지가 완전히 로드될 때까지 대기
                await page.wait_for_timeout(5000)
                
                # 에볼루션 로비가 로드될 때까지 추가 대기
                self.logger.info("🎰 에볼루션 카지노 로딩 대기 중...")
                
                # iframe 확인 및 처리
                await self._handle_iframes(page, websocket_urls)
                
                # 게임 타일 클릭으로 WebSocket 연결 유도
                await self._trigger_websocket_connections(page)
                
                # 추가 대기 시간 (WebSocket 연결 완료 대기)
                await page.wait_for_timeout(10000)
                
                # 페이지 새로고침으로 추가 WebSocket 탐지
                if len(websocket_urls) == 0:
                    self.logger.info("🔄 WebSocket을 찾지 못함. 페이지 새로고침...")
                    await page.reload(wait_until="networkidle")
                    await page.wait_for_timeout(8000)
                    await self._trigger_websocket_connections(page)
                    await page.wait_for_timeout(5000)
                
            finally:
                await browser.close()

        # 중복 제거 후 반환
        unique_urls = self._validate_and_filter_websockets(list(set(websocket_urls)))
        self.logger.info(f"✅ Playwright로 탐지한 WebSocket URL: {len(unique_urls)}개")
        
        for i, url in enumerate(unique_urls, 1):
            self.logger.info(f"   📡 {i}. {url}")
        
        return unique_urls

    async def _handle_iframes(self, page, websocket_urls):
        """iframe 처리 및 WebSocket 탐지"""
        try:
            # iframe이 로드될 때까지 대기
            await page.wait_for_timeout(3000)
            
            # iframe 찾기
            iframes = await page.query_selector_all("iframe")
            self.logger.info(f"🖼️ {len(iframes)}개의 iframe 발견")
            
            for i, iframe in enumerate(iframes):
                try:
                    # iframe 내부로 이동
                    iframe_page = await iframe.content_frame()
                    if iframe_page:
                        self.logger.info(f"iframe {i+1} 내부 탐색 중...")
                        
                        # iframe 내부에서도 WebSocket 리스너 등록
                        def on_iframe_websocket(ws):
                            url = ws.url
                            websocket_urls.append(url)
                            self.logger.info(f"📡 iframe에서 WebSocket 연결 감지: {url}")
                        
                        iframe_page.on("websocket", on_iframe_websocket)
                        
                        # iframe 내부 요소와 상호작용
                        await iframe_page.wait_for_timeout(2000)
                        
                except Exception as e:
                    self.logger.warning(f"iframe {i+1} 처리 중 오류: {e}")
                    
        except Exception as e:
            self.logger.warning(f"iframe 처리 중 오류: {e}")

    async def _trigger_websocket_connections(self, page):
        """다양한 상호작용으로 WebSocket 연결 유도"""
        try:
            self.logger.info("🎮 WebSocket 연결 유도를 위한 상호작용 시작...")
            
            # 1. 페이지 스크롤
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(1000)
            
            # 2. 마우스 이동
            await page.mouse.move(100, 100)
            await page.wait_for_timeout(500)
            await page.mouse.move(300, 300)
            await page.wait_for_timeout(500)
            
            # 3. 에볼루션 관련 요소 클릭 시도
            evolution_selectors = [
                '.game-tile',
                '.lobby-item', 
                '.game-card',
                '[data-game-id]',
                '.tile',
                '.game-button',
                'button',
                'a'
            ]
            
            for selector in evolution_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        # 첫 번째 요소 클릭
                        await elements[0].click()
                        self.logger.info(f"✅ 요소 클릭됨: {selector}")
                        await page.wait_for_timeout(2000)
                        break
                except Exception as e:
                    self.logger.debug(f"요소 클릭 실패 ({selector}): {e}")
                    continue
            
            # 4. 키보드 이벤트
            await page.keyboard.press('Tab')
            await page.wait_for_timeout(500)
            await page.keyboard.press('Enter')
            await page.wait_for_timeout(1000)
            
            self.logger.info("🎮 상호작용 완료")
            
        except Exception as e:
            self.logger.warning(f"상호작용 중 오류: {e}")

    def _validate_and_filter_websockets(self, websocket_urls: List[str]) -> List[str]:
        """웹소켓 URL 검증 및 필터링"""
        valid_urls = []
        
        for url in websocket_urls:
            if not self._is_valid_websocket_url(url):
                continue
            
            # URL 정리
            clean_url = re.sub(r'[)\]}>"\'\`]+$', '', url.strip())
            
            # 중복 확인 (파라미터 제외한 베이스 URL 기준)
            base_url = clean_url.split('?')[0]
            if any(base_url in valid_url for valid_url in valid_urls):
                continue
            
            valid_urls.append(clean_url)
        
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

    def _is_valid_websocket_url(self, url: str) -> bool:
        """웹소켓 URL 유효성 검증"""
        if not url or not isinstance(url, str):
            return False
        
        # 기본 형식 확인 - Python에서는 or 연산자 사용
        if not (url.startswith('ws://') or url.startswith('wss://')):
            return False
        
        # 최소 길이 확인
        if len(url) < 10:
            return False
        
        return True

    def get_best_websocket_url(self) -> Optional[str]:
        """최적의 웹소켓 URL 하나 반환"""
        try:
            urls = self.auto_detect_websocket_urls()
            
            if not urls:
                self.logger.warning("❌ 웹소켓 URL을 찾을 수 없습니다.")
                return None
            
            # 가장 우선순위가 높은 URL 반환
            best_url = urls[0]
            self.logger.info(f"🎯 최적 웹소켓 URL 선택: {best_url}")
            
            return best_url
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 탐지 중 오류: {e}")
            return None

    def monitor_websocket_connections_sync(self, target_url: str, duration_seconds: int = 30) -> List[str]:
        """
        동기 버전: 지정된 시간 동안 웹소켓 연결을 모니터링
        """
        return asyncio.run(self._monitor_websocket_connections_async(target_url, duration_seconds))

    async def _monitor_websocket_connections_async(self, target_url: str, duration_seconds: int) -> List[str]:
        """
        비동기 버전: 지정된 시간 동안 웹소켓 연결을 모니터링
        """
        websocket_urls = []
        
        self.logger.info(f"🔍 {duration_seconds}초 동안 웹소켓 연결 모니터링 시작")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            # WebSocket 연결 감지
            def on_websocket(ws):
                websocket_urls.append(ws.url)
                self.logger.info(f"📡 모니터링 중 WebSocket 감지: {ws.url}")
            
            page.on("websocket", on_websocket)
            
            try:
                await page.goto(target_url)
                
                # 지정된 시간 동안 모니터링
                start_time = time.time()
                while time.time() - start_time < duration_seconds:
                    await page.wait_for_timeout(2000)
                    # 주기적으로 상호작용
                    await self._trigger_websocket_connections(page)
                
            finally:
                await browser.close()
        
        unique_urls = list(set(websocket_urls))
        self.logger.info(f"✅ 모니터링 완료: {len(unique_urls)}개의 웹소켓 URL 발견")
        
        return unique_urls

# requirements.txt에 추가해야 할 패키지:
# playwright==1.40.0

# 설치 명령어:
# pip install playwright
# playwright install chromium