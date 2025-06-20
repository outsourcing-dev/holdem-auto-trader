# services/websocket_parser.py
"""
WebSocketParser - 최적화된 빠른 웹소켓 URL 추출
"""
import time
import logging
import re
import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright
import threading
import queue

class WebSocketParser:
    def __init__(self, devtools_controller, logger=None):
        self.devtools = devtools_controller
        self.logger = logger or logging.getLogger(__name__)
        self.found_websockets = set()
        self.max_refresh_attempts = 3
        self.detection_timeout = 45
        self.result_queue = queue.Queue()

    def auto_detect_websocket_urls(self) -> List[str]:
        """웹소켓 URL 자동 탐지 - 최적화된 버전"""
        try:
            self.logger.info("⚡ 최적화된 웹소켓 URL 추출 시작")
            
            # 백그라운드에서 웹소켓 추출 시작
            extraction_thread = threading.Thread(
                target=self._extract_websocket_background,
                daemon=True
            )
            extraction_thread.start()
            
            # 최대 15초 대기 (일반적으로 3-5초면 찾음)
            max_wait_time = 15
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                try:
                    # 0.1초마다 결과 확인
                    result = self.result_queue.get(timeout=0.1)
                    if result:
                        elapsed = time.time() - start_time
                        self.logger.info(f"✅ 웹소켓 URL 추출 완료 ({elapsed:.1f}초)")
                        return result
                except queue.Empty:
                    continue
            
            self.logger.warning(f"⏰ 웹소켓 추출 타임아웃 ({max_wait_time}초)")
            # 타임아웃시 폴백 방식 시도
            return self._fallback_websocket_detection()
            
        except Exception as e:
            self.logger.error(f"웹소켓 추출 오류: {e}")
            return []

    def _extract_websocket_background(self):
        """백그라운드에서 웹소켓 추출"""
        try:
            # 비동기 함수를 새 이벤트 루프에서 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(self._auto_detect_websocket_urls_with_playwright())
            
            if result:
                self.result_queue.put(result)
            else:
                self.result_queue.put([])
                
        except Exception as e:
            self.logger.error(f"백그라운드 웹소켓 추출 오류: {e}")
            self.result_queue.put([])

    async def _auto_detect_websocket_urls_with_playwright(self) -> List[str]:
        """Playwright를 이용한 실제 웹소켓 탐지 - 최적화된 버전"""
        websocket_urls = []
        
        # 디버깅 포트 찾기
        debug_port = self._get_debug_port()
        if debug_port:
            # 기존 브라우저에 연결 시도
            urls = await self._connect_to_existing_browser(debug_port)
            if urls:
                return urls
        
        # 폴백: 새 브라우저로 시도
        return await self._fallback_new_browser()

    def _get_debug_port(self) -> Optional[int]:
        """디버깅 포트 가져오기"""
        try:
            # 1. 일반적인 포트들 빠르게 테스트
            common_ports = [9222, 9223, 9224, 9225]
            for port in common_ports:
                if self._test_debug_port(port):
                    return port
            
            # 2. 프로세스에서 포트 찾기
            return self._detect_port_from_process()
            
        except Exception as e:
            self.logger.warning(f"디버깅 포트 감지 실패: {e}")
            return None

    def _test_debug_port(self, port: int) -> bool:
        """디버깅 포트 테스트"""
        try:
            import requests
            response = requests.get(f"http://localhost:{port}/json", timeout=1)
            return response.status_code == 200
        except:
            return False

    def _detect_port_from_process(self) -> Optional[int]:
        """프로세스에서 포트 감지"""
        try:
            import psutil
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'chrome' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline'] or [])
                        match = re.search(r'--remote-debugging-port=(\d+)', cmdline)
                        if match:
                            port = int(match.group(1))
                            if self._test_debug_port(port):
                                self.logger.info(f"✅ 프로세스에서 포트 발견: {port}")
                                return port
                except:
                    continue
                    
            return None
            
        except Exception:
            return None

    async def _connect_to_existing_browser(self, debug_port: int) -> List[str]:
        """기존 브라우저에 연결하여 웹소켓 감지"""
        websocket_urls = []
        
        self.logger.info(f"🔗 기존 브라우저 연결 중... (포트: {debug_port})")
        
        async with async_playwright() as p:
            try:
                # 기존 브라우저에 연결
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{debug_port}")
                contexts = browser.contexts
                
                if not contexts:
                    return []
                
                context = contexts[0]
                pages = context.pages
                
                # 에볼루션 페이지 찾기
                evolution_page = None
                for page in pages:
                    try:
                        url = page.url
                        self.logger.info(f"페이지 확인: {url}")
                        if self._is_evolution_url(url):
                            evolution_page = page
                            self.logger.info(f"✅ 에볼루션 페이지 발견: {url}")
                            break
                    except:
                        continue
                
                if not evolution_page:
                    return []
                
                # 웹소켓 감지 설정
                websocket_found = asyncio.Event()
                
                def on_websocket(ws):
                    url = ws.url
                    if self._is_valid_websocket_url(url):
                        websocket_urls.append(url)
                        self.logger.info(f"📡 WebSocket 연결 감지: {url}")
                        websocket_found.set()  # 즉시 완료 신호
                
                evolution_page.on("websocket", on_websocket)
                
                # 네트워크 요청 감지
                def on_request(request):
                    if 'websocket' in request.headers.get('upgrade', '').lower():
                        websocket_urls.append(request.url)
                        self.logger.info(f"🔌 WebSocket 업그레이드 요청 감지: {request.url}")
                        websocket_found.set()
                
                evolution_page.on("request", on_request)
                
                # 빠른 트리거 (페이지 새로고침)
                await evolution_page.reload(wait_until="domcontentloaded")
                
                # 웹소켓 발견되면 즉시 반환 (최대 12초 대기)
                try:
                    await asyncio.wait_for(websocket_found.wait(), timeout=12.0)
                except asyncio.TimeoutError:
                    self.logger.info("🔄 WebSocket 미발견, 페이지 새로고침...")
                    await evolution_page.reload()
                    await asyncio.wait_for(websocket_found.wait(), timeout=8.0)
                
                # 결과 처리
                unique_urls = self._validate_and_filter_websockets(list(set(websocket_urls)))
                return unique_urls
                
            except Exception as e:
                self.logger.error(f"기존 브라우저 연결 중 오류: {e}")
                return []

    async def _fallback_new_browser(self) -> List[str]:
        """폴백: 새 브라우저로 웹소켓 탐지"""
        websocket_urls = []
        
        # 기존 브라우저에서 URL 가져오기
        target_url = self._get_target_url()
        if not target_url:
            return []
        
        self.logger.info("🚀 새 Playwright 브라우저 시작 (폴백)...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,  # 폴백은 숨김 모드
                args=[
                    '--disable-web-security',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            try:
                context = await browser.new_context()
                page = await context.new_page()

                # WebSocket 감지
                def on_websocket(ws):
                    websocket_urls.append(ws.url)
                    self.logger.info(f"📡 WebSocket 연결 감지: {ws.url}")
                
                page.on("websocket", on_websocket)
                
                # 페이지 로드
                await page.goto(target_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(5000)
                
                # iframe 처리
                iframes = await page.query_selector_all("iframe")
                for iframe in iframes:
                    try:
                        iframe_page = await iframe.content_frame()
                        if iframe_page:
                            iframe_page.on("websocket", on_websocket)
                            await iframe_page.wait_for_timeout(2000)
                    except:
                        continue
                
                await page.wait_for_timeout(8000)
                
            finally:
                await browser.close()

        return self._validate_and_filter_websockets(list(set(websocket_urls)))

    def _fallback_websocket_detection(self) -> List[str]:
        """동기 폴백 웹소켓 탐지"""
        try:
            self.logger.info("🔄 동기 폴백 웹소켓 탐지 시작")
            return asyncio.run(self._fallback_new_browser())
        except Exception as e:
            self.logger.error(f"폴백 웹소켓 탐지 실패: {e}")
            return []

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

    def _is_evolution_url(self, url: str) -> bool:
        """에볼루션 URL 확인"""
        if not url:
            return False
        
        url_lower = url.lower()
        evolution_keywords = [
            'evolution',
            'evo-games',
            'casino_game_start',
            'vendor_key=evolution',
            'lobby500'
        ]
        
        return any(keyword in url_lower for keyword in evolution_keywords)

    def _is_valid_websocket_url(self, url: str) -> bool:
        """웹소켓 URL 유효성 검증"""
        if not url or not isinstance(url, str):
            return False
        
        if not (url.startswith('ws://') or url.startswith('wss://')):
            return False
        
        if len(url) < 10:
            return False
        
        # 에볼루션 웹소켓인지 확인
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in [
            'evo-games.com', 'evolution', 'lobby', 'socket'
        ])

    def _validate_and_filter_websockets(self, websocket_urls: List[str]) -> List[str]:
        """웹소켓 URL 검증 및 필터링"""
        valid_urls = []
        
        for url in websocket_urls:
            if not self._is_valid_websocket_url(url):
                continue
            
            clean_url = re.sub(r'[)\]}>"\'\`]+$', '', url.strip())
            base_url = clean_url.split('?')[0]
            
            if any(base_url in valid_url for valid_url in valid_urls):
                continue
            
            valid_urls.append(clean_url)
        
        # 에볼루션 우선순위 정렬
        def evolution_priority(url):
            priority = 0
            url_lower = url.lower()
            
            if 'evo-games.com' in url_lower:
                priority += 1000
            if 'evolution' in url_lower:
                priority += 500
            if 'lobby' in url_lower:
                priority += 300
            if 'socket' in url_lower:
                priority += 100
            if url.startswith('wss://'):
                priority += 50
                
            return -priority
        
        valid_urls.sort(key=evolution_priority)
        return valid_urls

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