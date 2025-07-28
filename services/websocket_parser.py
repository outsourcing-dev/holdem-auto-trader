# services/websocket_parser.py
"""
WebSocketParser - 멀티스레드 최적화된 빠른 웹소켓 URL 추출
"""
import time
import logging
import re
import asyncio
from typing import List, Optional, Callable
from playwright.async_api import async_playwright
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass

@dataclass
class WebSocketResult:
    """웹소켓 추출 결과"""
    urls: List[str]
    success: bool
    error: Optional[str] = None
    elapsed_time: float = 0.0

class WebSocketParser:
    def __init__(self, devtools_controller, logger=None):
        self.devtools = devtools_controller
        self.logger = logger or logging.getLogger(__name__)
        self.found_websockets = set()
        self.max_refresh_attempts = 3
        self.detection_timeout = 45
        self.result_queue = queue.Queue()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="websocket")
        self._current_future: Optional[Future] = None
        self._shutdown = False

    def auto_detect_websocket_urls_async(self, callback: Optional[Callable[[WebSocketResult], None]] = None) -> Future[WebSocketResult]:
        """비동기 웹소켓 URL 추출 - 콜백 지원"""
        if self._current_future and not self._current_future.done():
            self._current_future.cancel()
        
        self._current_future = self._executor.submit(self._extract_websocket_sync_wrapper, callback)
        return self._current_future

    def auto_detect_websocket_urls(self) -> List[str]:
        """동기 웹소켓 URL 추출 (기존 호환성 유지)"""
        try:
            future = self.auto_detect_websocket_urls_async()
            result = future.result(timeout=30)  # 최대 30초 대기
            return result.urls if result.success else []
        except Exception as e:
            self.logger.error(f"웹소켓 추출 오류: {e}")
            return []

    def _extract_websocket_sync_wrapper(self, callback: Optional[Callable[[WebSocketResult], None]] = None) -> WebSocketResult:
        """동기 래퍼 - 별도 스레드에서 실행"""
        start_time = time.time()
        
        try:
            self.logger.info("⚡ 멀티스레드 웹소켓 URL 추출 시작")
            
            # 새 이벤트 루프에서 비동기 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                urls = loop.run_until_complete(self._extract_websocket_async())
                elapsed = time.time() - start_time
                
                result = WebSocketResult(
                    urls=urls,
                    success=True,
                    elapsed_time=elapsed
                )
                
                self.logger.info(f"✅ 웹소켓 URL 추출 완료 ({elapsed:.1f}초, {len(urls)}개 발견)")
                
                if callback:
                    try:
                        callback(result)
                    except Exception as e:
                        self.logger.error(f"콜백 실행 중 오류: {e}")
                
                return result
                
            finally:
                loop.close()
                
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"웹소켓 추출 중 오류: {e}"
            self.logger.error(error_msg)
            
            result = WebSocketResult(
                urls=[],
                success=False,
                error=error_msg,
                elapsed_time=elapsed
            )
            
            if callback:
                try:
                    callback(result)
                except Exception as cb_error:
                    self.logger.error(f"에러 콜백 실행 중 오류: {cb_error}")
            
            return result

    async def _extract_websocket_async(self) -> List[str]:
        """실제 비동기 웹소켓 추출 로직"""
        # 기존 브라우저 연결 시도
        debug_port = await self._get_debug_port_async()
        if debug_port:
            urls = await self._connect_to_existing_browser(debug_port)
            if urls:
                return urls
        
        # 폴백: 새 브라우저
        return await self._fallback_new_browser()

    async def _get_debug_port_async(self) -> Optional[int]:
        """비동기 디버깅 포트 탐지"""
        try:
            # 백그라운드에서 포트 테스트
            loop = asyncio.get_event_loop()
            
            # 일반적인 포트들 병렬 테스트
            common_ports = [9222, 9223, 9224, 9225]
            tasks = [
                loop.run_in_executor(None, self._test_debug_port, port)
                for port in common_ports
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for port, result in zip(common_ports, results):
                if result is True:
                    self.logger.info(f"✅ 디버깅 포트 발견: {port}")
                    return port
            
            # 프로세스에서 포트 찾기
            port = await loop.run_in_executor(None, self._detect_port_from_process)
            return port
            
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
                        websocket_found.set()
                
                evolution_page.on("websocket", on_websocket)
                
                def on_request(request):
                    if 'websocket' in request.headers.get('upgrade', '').lower():
                        websocket_urls.append(request.url)
                        self.logger.info(f"🔌 WebSocket 업그레이드 요청 감지: {request.url}")
                        websocket_found.set()
                
                evolution_page.on("request", on_request)
                
                # 빠른 트리거
                await evolution_page.reload(wait_until="domcontentloaded")
                
                # 웹소켓 감지 대기
                try:
                    await asyncio.wait_for(websocket_found.wait(), timeout=12.0)
                except asyncio.TimeoutError:
                    self.logger.info("🔄 WebSocket 미발견, 페이지 새로고침...")
                    await evolution_page.reload()
                    await asyncio.wait_for(websocket_found.wait(), timeout=8.0)
                
                return self._validate_and_filter_websockets(list(set(websocket_urls)))
                
            except Exception as e:
                self.logger.error(f"기존 브라우저 연결 중 오류: {e}")
                return []

    async def _fallback_new_browser(self) -> List[str]:
        """폴백: 새 브라우저로 웹소켓 탐지"""
        websocket_urls = []
        
        target_url = self._get_target_url()
        if not target_url:
            return []
        
        self.logger.info("🚀 새 Playwright 브라우저 시작 (폴백)...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-web-security',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            try:
                context = await browser.new_context()
                page = await context.new_page()

                def on_websocket(ws):
                    websocket_urls.append(ws.url)
                    self.logger.info(f"📡 WebSocket 연결 감지: {ws.url}")
                
                page.on("websocket", on_websocket)
                
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

    def _get_target_url(self) -> Optional[str]:
        """기존 브라우저에서 현재 URL 가져오기"""
        try:
            if not self.devtools or not self.devtools.driver:
                return None
            
            window_handles = self.devtools.driver.window_handles
            if len(window_handles) >= 2:
                self.devtools.driver.switch_to.window(window_handles[1])
                current_url = self.devtools.driver.current_url
                self.logger.info(f"기존 브라우저 URL: {current_url}")
                return current_url
            else:
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

    def get_best_websocket_url_async(self, callback: Optional[Callable[[Optional[str]], None]] = None) -> Future[Optional[str]]:
        """비동기로 최적의 웹소켓 URL 하나 반환"""
        def process_result(result: WebSocketResult) -> Optional[str]:
            if result.success and result.urls:
                best_url = result.urls[0]
                self.logger.info(f"🎯 최적 웹소켓 URL 선택: {best_url}")
                if callback:
                    callback(best_url)
                return best_url
            else:
                self.logger.warning("❌ 웹소켓 URL을 찾을 수 없습니다.")
                if callback:
                    callback(None)
                return None
        
        def wrapper_callback(result: WebSocketResult):
            process_result(result)
        
        future = self.auto_detect_websocket_urls_async(wrapper_callback)
        
        # Future를 반환하되, 결과를 최적 URL로 변환
        def transform_future():
            try:
                result = future.result()
                return process_result(result)
            except Exception as e:
                self.logger.error(f"웹소켓 URL 탐지 중 오류: {e}")
                return None
        
        return self._executor.submit(transform_future)

    def get_best_websocket_url(self) -> Optional[str]:
        """동기 최적의 웹소켓 URL 반환 (기존 호환성)"""
        try:
            future = self.get_best_websocket_url_async()
            return future.result(timeout=30)
        except Exception as e:
            self.logger.error(f"웹소켓 URL 탐지 중 오류: {e}")
            return None

    def cancel_current_operation(self):
        """현재 진행 중인 작업 취소"""
        if self._current_future and not self._current_future.done():
            self.logger.info("🛑 웹소켓 추출 작업 취소 중...")
            self._current_future.cancel()

    def shutdown(self):
        """리소스 정리"""
        self._shutdown = True
        self.cancel_current_operation()
        self._executor.shutdown(wait=False)
        self.logger.info("🔚 WebSocketParser 종료됨")

    def __del__(self):
        """소멸자에서 리소스 정리"""
        if not self._shutdown:
            self.shutdown()