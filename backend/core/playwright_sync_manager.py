"""
Playwright 동기 브라우저 매니저 - asyncio 문제 해결
"""
import logging
import time
from typing import Optional, Dict, Any, List
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Frame
import threading

logger = logging.getLogger(__name__)

class PlaywrightSyncManager:
    """Playwright를 사용한 브라우저 자동화 관리 (동기 버전)"""
    
    def __init__(self, username: str):
        self.username = username
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_connected = False
        self._thread = None
        
    def initialize(self):
        """Playwright 초기화"""
        try:
            self.playwright = sync_playwright().start()
            logger.info(f"Playwright 초기화 완료: {self.username}")
        except Exception as e:
            logger.error(f"Playwright 초기화 실패: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def launch_browser(self, headless: bool = False):
        """브라우저 실행"""
        try:
            if not self.playwright:
                self.initialize()
            
            # Chrome 브라우저 실행
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            
            # 브라우저 컨텍스트 생성
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # 새 페이지 생성
            self.page = self.context.new_page()
            self.is_connected = True
            
            logger.info(f"브라우저 실행 완료: {self.username}")
            return True
            
        except Exception as e:
            logger.error(f"브라우저 실행 실패: {e}")
            return False
    
    def navigate_to(self, url: str):
        """URL로 이동"""
        try:
            if not self.page:
                raise Exception("브라우저가 실행되지 않았습니다")
            
            self.page.goto(url, wait_until='networkidle')
            logger.info(f"페이지 이동: {url}")
            return True
            
        except Exception as e:
            logger.error(f"페이지 이동 실패: {e}")
            return False
    
    def get_iframe(self, name_or_index: str = None) -> Optional[Frame]:
        """iframe 가져오기"""
        try:
            frames = self.page.frames
            
            if name_or_index is None:
                # Evolution Gaming iframe 찾기
                for frame in frames:
                    url = frame.url
                    if 'evolution' in url.lower() or 'evo' in url.lower():
                        return frame
            elif isinstance(name_or_index, int):
                return frames[name_or_index] if name_or_index < len(frames) else None
            else:
                for frame in frames:
                    if frame.name == name_or_index:
                        return frame
            
            return None
            
        except Exception as e:
            logger.error(f"iframe 가져오기 실패: {e}")
            return None
    
    def close(self):
        """브라우저 종료"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            
            self.is_connected = False
            logger.info(f"브라우저 종료: {self.username}")
            
        except Exception as e:
            logger.error(f"브라우저 종료 실패: {e}")
    
    def check_betting_available(self) -> bool:
        """베팅 가능 상태 확인"""
        try:
            if not self.page:
                return False
            
            script = """
            () => {
                // 칩이 활성화되어 있는지 확인
                const chips = document.querySelectorAll('.chip:not(.disabled), .chip-item:not(.disabled)');
                if (chips.length === 0) return false;
                
                // No more bets 메시지 확인
                const body = document.body.innerText.toUpperCase();
                if (body.includes('NO MORE BETS') || body.includes('BETTING CLOSED')) {
                    return false;
                }
                
                return true;
            }
            """
            
            is_available = self.page.evaluate(script)
            return is_available if is_available else False
            
        except Exception as e:
            logger.error(f"베팅 가능 상태 확인 실패: {e}")
            return False
    
    def find_and_click_chip(self, amount: int) -> bool:
        """칩 찾아서 클릭"""
        try:
            # 칩 선택자들
            chip_selectors = [
                f'[data-value="{amount}"]',
                f'.chip[data-amount="{amount}"]',
                f'.chip-item:has-text("{amount}")',
                f'button:has-text("{amount:,}")'
            ]
            
            for selector in chip_selectors:
                try:
                    if self.page.locator(selector).is_visible():
                        self.page.click(selector)
                        logger.info(f"칩 클릭 성공: {amount:,}원")
                        return True
                except:
                    continue
            
            logger.warning(f"칩을 찾을 수 없음: {amount:,}원")
            return False
            
        except Exception as e:
            logger.error(f"칩 클릭 실패: {e}")
            return False
    
    def click_betting_spot(self, bet_type: str) -> bool:
        """베팅 위치 클릭 (P/B)"""
        try:
            # 베팅 스팟 선택자
            if bet_type == 'P':
                selectors = [
                    '[data-bet-spot="player"]',
                    '.bet-spot-player',
                    '.player-betting-area',
                    'div:has-text("플레이어")'
                ]
            else:  # 'B'
                selectors = [
                    '[data-bet-spot="banker"]',
                    '.bet-spot-banker',
                    '.banker-betting-area',
                    'div:has-text("뱅커")'
                ]
            
            for selector in selectors:
                try:
                    if self.page.locator(selector).is_visible():
                        self.page.click(selector)
                        logger.info(f"베팅 위치 클릭: {bet_type}")
                        return True
                except:
                    continue
            
            logger.warning(f"베팅 위치를 찾을 수 없음: {bet_type}")
            return False
            
        except Exception as e:
            logger.error(f"베팅 위치 클릭 실패: {e}")
            return False
    
    def enter_room(self, room_name: str) -> bool:
        """방 입장"""
        try:
            # iframe이 있으면 그 안에서 찾기
            frame = self.get_iframe()
            target = frame if frame else self.page
            
            # 방 찾기 및 클릭
            room_selectors = [
                f'[title="{room_name}"]',
                f'.room-item:has-text("{room_name}")',
                f'button:has-text("{room_name}")'
            ]
            
            for selector in room_selectors:
                try:
                    if target.locator(selector).is_visible():
                        target.click(selector)
                        logger.info(f"방 입장: {room_name}")
                        time.sleep(3)  # 로딩 대기
                        return True
                except:
                    continue
            
            logger.warning(f"방을 찾을 수 없음: {room_name}")
            return False
            
        except Exception as e:
            logger.error(f"방 입장 실패: {e}")
            return False
    
    def exit_room(self) -> bool:
        """방 나가기"""
        try:
            frame = self.get_iframe()
            target = frame if frame else self.page
            
            # 나가기 버튼 클릭
            exit_selectors = [
                '.exit-button',
                '.close-button',
                'button:has-text("나가기")',
                'button:has-text("Exit")'
            ]
            
            for selector in exit_selectors:
                try:
                    if target.locator(selector).is_visible():
                        target.click(selector)
                        logger.info("방 나가기 완료")
                        time.sleep(2)
                        return True
                except:
                    continue
            
            # 뒤로가기로 시도
            self.page.go_back()
            logger.info("뒤로가기로 방 나가기")
            return True
            
        except Exception as e:
            logger.error(f"방 나가기 실패: {e}")
            return False