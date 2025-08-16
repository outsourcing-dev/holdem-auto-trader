"""
베팅 실행 모듈
칩 선택, 베팅 위치 클릭, 결과 확인
"""
import logging
import time
from typing import Optional, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

class BettingExecutor:
    """베팅 실행 클래스"""
    
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)
        self.last_bet_amount = None
        self.last_bet_type = None
        
    def select_chip(self, amount: int) -> bool:
        """베팅 칩 선택"""
        try:
            # 칩 매핑
            chip_mapping = {
                10000: ["chip-10k", "chip-10000", ".chip[data-value='10000']"],
                20000: ["chip-20k", "chip-20000", ".chip[data-value='20000']"],
                30000: ["chip-30k", "chip-30000", ".chip[data-value='30000']"],
                50000: ["chip-50k", "chip-50000", ".chip[data-value='50000']"],
                100000: ["chip-100k", "chip-100000", ".chip[data-value='100000']"]
            }
            
            if amount not in chip_mapping:
                logger.error(f"지원하지 않는 칩 금액: {amount}")
                return False
            
            # 칩 선택 시도
            for selector in chip_mapping[amount]:
                try:
                    # ID로 시도
                    try:
                        chip = self.driver.find_element(By.ID, selector)
                    except:
                        # CSS 셀렉터로 시도
                        chip = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    # 칩 클릭
                    chip.click()
                    self.last_bet_amount = amount
                    logger.info(f"칩 선택 성공: {amount:,}원")
                    return True
                    
                except:
                    continue
            
            # 대체 방법: 칩 이미지나 텍스트로 찾기
            try:
                chips = self.driver.find_elements(By.CSS_SELECTOR, ".chip, .chip-selector")
                for chip in chips:
                    chip_text = chip.text or chip.get_attribute("data-value") or ""
                    if str(amount) in chip_text:
                        chip.click()
                        self.last_bet_amount = amount
                        logger.info(f"칩 선택 성공 (대체): {amount:,}원")
                        return True
            except:
                pass
                
            logger.error(f"칩 선택 실패: {amount:,}원")
            return False
            
        except Exception as e:
            logger.error(f"칩 선택 오류: {e}")
            return False
    
    def place_bet(self, bet_type: str) -> bool:
        """베팅 위치 클릭 (P: Player, B: Banker)"""
        try:
            # 베팅 영역 매핑
            bet_areas = {
                'P': [
                    ".player-bet-area",
                    ".bet-spot-player",
                    "div[data-bet='player']",
                    "#player-bet"
                ],
                'B': [
                    ".banker-bet-area", 
                    ".bet-spot-banker",
                    "div[data-bet='banker']",
                    "#banker-bet"
                ],
                'T': [
                    ".tie-bet-area",
                    ".bet-spot-tie",
                    "div[data-bet='tie']",
                    "#tie-bet"
                ]
            }
            
            if bet_type not in bet_areas:
                logger.error(f"잘못된 베팅 타입: {bet_type}")
                return False
            
            # 베팅 영역 클릭 시도
            for selector in bet_areas[bet_type]:
                try:
                    bet_area = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    
                    # 클릭 (ActionChains 사용)
                    actions = ActionChains(self.driver)
                    actions.move_to_element(bet_area).click().perform()
                    
                    self.last_bet_type = bet_type
                    logger.info(f"베팅 성공: {bet_type} - {self.last_bet_amount:,}원")
                    return True
                    
                except:
                    continue
            
            # 대체 방법: 텍스트로 찾기
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, ".bet-area, .betting-spot")
                for elem in elements:
                    elem_text = elem.text.upper()
                    if (bet_type == 'P' and 'PLAYER' in elem_text) or \
                       (bet_type == 'B' and 'BANKER' in elem_text) or \
                       (bet_type == 'T' and 'TIE' in elem_text):
                        actions = ActionChains(self.driver)
                        actions.move_to_element(elem).click().perform()
                        self.last_bet_type = bet_type
                        logger.info(f"베팅 성공 (대체): {bet_type} - {self.last_bet_amount:,}원")
                        return True
            except:
                pass
                
            logger.error(f"베팅 영역 찾기 실패: {bet_type}")
            return False
            
        except Exception as e:
            logger.error(f"베팅 실행 오류: {e}")
            return False
    
    def execute_bet(self, bet_type: str, amount: int) -> bool:
        """완전한 베팅 실행 (칩 선택 + 베팅)"""
        try:
            # 1. 칩 선택
            if not self.select_chip(amount):
                return False
            
            time.sleep(0.5)  # 짧은 대기
            
            # 2. 베팅 위치 클릭
            if not self.place_bet(bet_type):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"베팅 실행 오류: {e}")
            return False
    
    def check_betting_time(self) -> Tuple[bool, int]:
        """베팅 가능 시간 체크"""
        try:
            # 타이머 찾기
            timer_selectors = [
                ".betting-timer",
                ".timer",
                ".countdown",
                ".time-remaining"
            ]
            
            for selector in timer_selectors:
                try:
                    timer = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if timer.is_displayed():
                        timer_text = timer.text
                        
                        # 숫자 추출
                        import re
                        numbers = re.findall(r'\d+', timer_text)
                        if numbers:
                            seconds = int(numbers[0])
                            is_betting_time = seconds > 2  # 2초 이상 남았을 때만 베팅
                            return is_betting_time, seconds
                except:
                    continue
            
            # 베팅 영역이 활성화되어 있는지 체크
            try:
                bet_area = self.driver.find_element(By.CSS_SELECTOR, ".bet-area:not(.disabled)")
                if bet_area:
                    return True, 10  # 기본값
            except:
                pass
                
            return False, 0
            
        except Exception as e:
            logger.error(f"베팅 시간 체크 오류: {e}")
            return False, 0
    
    def get_game_result(self) -> Optional[str]:
        """게임 결과 가져오기"""
        try:
            # 결과 표시 대기 (최대 30초)
            result_selectors = [
                ".game-result",
                ".winner",
                ".result-display",
                ".round-result"
            ]
            
            for selector in result_selectors:
                try:
                    result_elem = WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    
                    result_text = result_elem.text.upper()
                    
                    # 결과 파싱
                    if 'PLAYER' in result_text:
                        return 'P'
                    elif 'BANKER' in result_text:
                        return 'B'
                    elif 'TIE' in result_text:
                        return 'T'
                        
                except TimeoutException:
                    continue
            
            logger.warning("게임 결과를 찾을 수 없습니다")
            return None
            
        except Exception as e:
            logger.error(f"게임 결과 가져오기 오류: {e}")
            return None
    
    def get_balance(self) -> Optional[int]:
        """현재 잔액 가져오기"""
        try:
            balance_selectors = [
                ".balance",
                ".player-balance",
                ".credit",
                ".money"
            ]
            
            for selector in balance_selectors:
                try:
                    balance_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    balance_text = balance_elem.text
                    
                    # 숫자만 추출
                    import re
                    numbers = re.findall(r'[\d,]+', balance_text)
                    if numbers:
                        balance = int(numbers[0].replace(',', ''))
                        return balance
                except:
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"잔액 가져오기 오류: {e}")
            return None