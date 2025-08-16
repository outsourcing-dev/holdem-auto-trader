"""
Playwright 브라우저 매니저 - CDP 대체
"""
import logging
import asyncio
import sys
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Frame
import nest_asyncio

# Windows에서 asyncio 호환성 문제 해결
if sys.platform.startswith('win'):
    # Windows에서는 ProactorEventLoop 대신 SelectorEventLoop 사용
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    nest_asyncio.apply()

logger = logging.getLogger(__name__)

class PlaywrightManager:
    """Playwright를 사용한 브라우저 자동화 관리"""
    
    def __init__(self, username: str):
        self.username = username
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_connected = False
        
    async def initialize(self):
        """Playwright 초기화"""
        try:
            self.playwright = await async_playwright().start()
            logger.info(f"Playwright 초기화 완료: {self.username}")
        except Exception as e:
            logger.error(f"Playwright 초기화 실패: {e}")
            raise
    
    async def launch_browser(self, headless: bool = False):
        """브라우저 실행"""
        try:
            if not self.playwright:
                await self.initialize()
            
            # Chrome 브라우저 실행
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            
            # 브라우저 컨텍스트 생성 (쿠키, 로컬 스토리지 격리)
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # 새 페이지 생성
            self.page = await self.context.new_page()
            self.is_connected = True
            
            logger.info(f"브라우저 실행 완료: {self.username}")
            
        except Exception as e:
            logger.error(f"브라우저 실행 실패: {e}")
            raise
    
    async def navigate_to(self, url: str):
        """URL로 이동"""
        try:
            if not self.page:
                raise Exception("브라우저가 실행되지 않았습니다")
            
            await self.page.goto(url, wait_until='networkidle')
            logger.info(f"페이지 이동: {url}")
            
        except Exception as e:
            logger.error(f"페이지 이동 실패: {e}")
            raise
    
    async def wait_for_element(self, selector: str, timeout: int = 30000):
        """요소 대기"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except:
            return False
    
    async def click_element(self, selector: str):
        """요소 클릭"""
        try:
            await self.page.click(selector)
            logger.debug(f"요소 클릭: {selector}")
        except Exception as e:
            logger.error(f"클릭 실패: {e}")
            raise
    
    async def type_text(self, selector: str, text: str):
        """텍스트 입력"""
        try:
            await self.page.fill(selector, text)
            logger.debug(f"텍스트 입력: {selector}")
        except Exception as e:
            logger.error(f"텍스트 입력 실패: {e}")
            raise
    
    async def get_iframe(self, name_or_index: str = None) -> Optional[Frame]:
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
    
    async def execute_script(self, script: str, frame: Frame = None):
        """JavaScript 실행"""
        try:
            target = frame if frame else self.page
            result = await target.evaluate(script)
            return result
        except Exception as e:
            logger.error(f"스크립트 실행 실패: {e}")
            return None
    
    async def find_and_click_chip(self, amount: int, frame: Frame = None) -> bool:
        """칩 찾아서 클릭"""
        try:
            target = frame if frame else self.page
            
            # 칩 선택자들
            chip_selectors = [
                f'[data-value="{amount}"]',
                f'.chip[data-amount="{amount}"]',
                f'.chip-item:has-text("{amount}")',
                f'button:has-text("{amount:,}")'
            ]
            
            for selector in chip_selectors:
                try:
                    if await target.locator(selector).is_visible():
                        await target.click(selector)
                        logger.info(f"칩 클릭 성공: {amount:,}원")
                        return True
                except:
                    continue
            
            logger.warning(f"칩을 찾을 수 없음: {amount:,}원")
            return False
            
        except Exception as e:
            logger.error(f"칩 클릭 실패: {e}")
            return False
    
    async def click_betting_spot(self, bet_type: str, frame: Frame = None) -> bool:
        """베팅 위치 클릭 (P/B)"""
        try:
            target = frame if frame else self.page
            
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
                    if await target.locator(selector).is_visible():
                        await target.click(selector)
                        logger.info(f"베팅 위치 클릭: {bet_type}")
                        return True
                except:
                    continue
            
            logger.warning(f"베팅 위치를 찾을 수 없음: {bet_type}")
            return False
            
        except Exception as e:
            logger.error(f"베팅 위치 클릭 실패: {e}")
            return False
    
    async def get_game_results(self, frame: Frame = None) -> List[str]:
        """게임 결과 가져오기"""
        try:
            target = frame if frame else self.page
            
            # 결과 로드맵 파싱
            script = """
            () => {
                const results = [];
                
                // 다양한 선택자 시도
                const selectors = [
                    '.roadmap-item',
                    '.result-bead',
                    '.game-result',
                    '[class*="result"]'
                ];
                
                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        elements.forEach(el => {
                            const text = el.textContent.trim().toUpperCase();
                            if (text === 'P' || text === 'B' || text === 'T') {
                                results.push(text);
                            } else if (text.includes('PLAYER')) {
                                results.push('P');
                            } else if (text.includes('BANKER')) {
                                results.push('B');
                            } else if (text.includes('TIE')) {
                                results.push('T');
                            }
                        });
                        break;
                    }
                }
                
                return results;
            }
            """
            
            results = await target.evaluate(script)
            return results if results else []
            
        except Exception as e:
            logger.error(f"게임 결과 가져오기 실패: {e}")
            return []
    
    async def get_current_balance(self, frame: Frame = None) -> Optional[int]:
        """현재 잔액 가져오기"""
        try:
            target = frame if frame else self.page
            
            script = """
            () => {
                const selectors = [
                    '.balance',
                    '.user-balance',
                    '.player-balance',
                    '[class*="balance"]'
                ];
                
                for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    if (el) {
                        const text = el.textContent.replace(/[^0-9]/g, '');
                        const balance = parseInt(text);
                        if (!isNaN(balance)) {
                            return balance;
                        }
                    }
                }
                
                return null;
            }
            """
            
            balance = await target.evaluate(script)
            return balance
            
        except Exception as e:
            logger.error(f"잔액 가져오기 실패: {e}")
            return None
    
    async def check_betting_available(self, frame: Frame = None) -> bool:
        """베팅 가능 상태 확인"""
        try:
            target = frame if frame else self.page
            
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
            
            is_available = await target.evaluate(script)
            return is_available if is_available else False
            
        except Exception as e:
            logger.error(f"베팅 가능 상태 확인 실패: {e}")
            return False
    
    async def wait_for_betting_phase(self, frame: Frame = None, timeout: int = 30):
        """베팅 페이즈 대기"""
        try:
            target = frame if frame else self.page
            
            for _ in range(timeout):
                if await self.check_betting_available(target):
                    logger.info("베팅 페이즈 시작")
                    return True
                await asyncio.sleep(1)
            
            logger.warning("베팅 페이즈 대기 시간 초과")
            return False
            
        except Exception as e:
            logger.error(f"베팅 페이즈 대기 실패: {e}")
            return False
    
    async def take_screenshot(self, filename: str = None):
        """스크린샷 캡처"""
        try:
            if not filename:
                from datetime import datetime
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            await self.page.screenshot(path=filename)
            logger.info(f"스크린샷 저장: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"스크린샷 실패: {e}")
            return None
    
    async def close(self):
        """브라우저 종료"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            self.is_connected = False
            logger.info(f"브라우저 종료: {self.username}")
            
        except Exception as e:
            logger.error(f"브라우저 종료 실패: {e}")
    
    async def enter_room(self, room_name: str, frame: Frame = None) -> bool:
        """방 입장"""
        try:
            target = frame if frame else self.page
            
            # 방 찾기 및 클릭
            room_selectors = [
                f'[title="{room_name}"]',
                f'.room-item:has-text("{room_name}")',
                f'button:has-text("{room_name}")'
            ]
            
            for selector in room_selectors:
                try:
                    if await target.locator(selector).is_visible():
                        await target.click(selector)
                        logger.info(f"방 입장: {room_name}")
                        
                        # 로딩 대기
                        await asyncio.sleep(3)
                        return True
                except:
                    continue
            
            logger.warning(f"방을 찾을 수 없음: {room_name}")
            return False
            
        except Exception as e:
            logger.error(f"방 입장 실패: {e}")
            return False
    
    async def exit_room(self, frame: Frame = None) -> bool:
        """방 나가기"""
        try:
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
                    if await target.locator(selector).is_visible():
                        await target.click(selector)
                        logger.info("방 나가기 완료")
                        await asyncio.sleep(2)
                        return True
                except:
                    continue
            
            # 뒤로가기로 시도
            await self.page.go_back()
            logger.info("뒤로가기로 방 나가기")
            return True
            
        except Exception as e:
            logger.error(f"방 나가기 실패: {e}")
            return False