"""
Selenium 기반 브라우저 제어 컨트롤러
실제 베팅을 위한 브라우저 자동화
"""
import logging
import time
import os
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc

logger = logging.getLogger(__name__)

class SeleniumController:
    """Selenium을 사용한 브라우저 제어"""
    
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.current_url: Optional[str] = None
        
    def start_browser(self, url: str) -> bool:
        """브라우저 시작 및 사이트 접속"""
        try:
            # Chrome 옵션 설정
            options = uc.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # 보안 설정 완화 (iframe 접근용)
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-site-isolation-trials')
            options.add_argument('--allow-running-insecure-content')
            
            # undetected-chromedriver 실행
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            self.wait = WebDriverWait(self.driver, 10)
            
            # JavaScript로 자동화 감지 우회
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en']
                });
            """)
            
            # 사이트로 이동
            self.driver.get(url)
            self.current_url = url
            
            logger.info(f"브라우저 시작 성공: {url}")
            return True
            
        except Exception as e:
            logger.error(f"브라우저 시작 실패: {e}")
            return False
    
    def find_evolution_iframe(self) -> bool:
        """Evolution Gaming iframe 찾기"""
        try:
            # 메인 프레임으로 전환
            self.driver.switch_to.default_content()
            
            # Evolution iframe 찾기 (여러 셀렉터 시도)
            iframe_selectors = [
                "iframe[src*='evolution']",
                "iframe[src*='evo']",
                "iframe[title*='Evolution']",
                "iframe[name*='game']",
                "iframe.game-iframe",
                "#game-iframe",
                "iframe"  # 마지막 폴백
            ]
            
            for selector in iframe_selectors:
                try:
                    iframe = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    self.driver.switch_to.frame(iframe)
                    logger.info(f"Evolution iframe 찾기 성공: {selector}")
                    return True
                except:
                    continue
                    
            logger.warning("Evolution iframe을 찾을 수 없습니다")
            return False
            
        except Exception as e:
            logger.error(f"iframe 찾기 오류: {e}")
            return False
    
    def find_game_rooms(self) -> list:
        """게임 룸 목록 가져오기"""
        try:
            rooms = []
            
            # 룸 목록 대기
            room_elements = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".lobby-table"))
            )
            
            for element in room_elements:
                try:
                    room_name = element.find_element(By.CSS_SELECTOR, ".table-name").text
                    rooms.append(room_name)
                except:
                    continue
                    
            logger.info(f"게임 룸 {len(rooms)}개 발견")
            return rooms
            
        except Exception as e:
            logger.error(f"게임 룸 찾기 오류: {e}")
            return []
    
    def enter_room(self, room_name: str) -> bool:
        """특정 게임 룸 입장"""
        try:
            # 룸 찾기
            room_elements = self.driver.find_elements(By.CSS_SELECTOR, ".lobby-table")
            
            for element in room_elements:
                try:
                    name_elem = element.find_element(By.CSS_SELECTOR, ".table-name")
                    if room_name in name_elem.text:
                        # 룸 클릭
                        element.click()
                        time.sleep(2)  # 룸 로딩 대기
                        logger.info(f"룸 입장 성공: {room_name}")
                        return True
                except:
                    continue
                    
            logger.warning(f"룸을 찾을 수 없습니다: {room_name}")
            return False
            
        except Exception as e:
            logger.error(f"룸 입장 오류: {e}")
            return False
    
    def exit_room(self) -> bool:
        """현재 룸에서 나가기"""
        try:
            # 나가기 버튼 찾기
            exit_selectors = [
                ".btn-exit",
                ".exit-button",
                "button[aria-label*='exit']",
                "button[aria-label*='나가기']",
                ".lobby-button"
            ]
            
            for selector in exit_selectors:
                try:
                    exit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    exit_btn.click()
                    time.sleep(2)
                    logger.info("룸 나가기 성공")
                    return True
                except:
                    continue
                    
            logger.warning("나가기 버튼을 찾을 수 없습니다")
            return False
            
        except Exception as e:
            logger.error(f"룸 나가기 오류: {e}")
            return False
    
    def get_game_status(self) -> Dict[str, Any]:
        """현재 게임 상태 가져오기"""
        try:
            status = {
                "is_betting_time": False,
                "current_round": None,
                "time_remaining": None,
                "last_results": []
            }
            
            # 베팅 시간 체크
            try:
                betting_timer = self.driver.find_element(By.CSS_SELECTOR, ".betting-timer")
                if betting_timer.is_displayed():
                    status["is_betting_time"] = True
                    status["time_remaining"] = betting_timer.text
            except:
                pass
            
            # 현재 라운드
            try:
                round_elem = self.driver.find_element(By.CSS_SELECTOR, ".round-number")
                status["current_round"] = round_elem.text
            except:
                pass
            
            # 최근 결과
            try:
                results = self.driver.find_elements(By.CSS_SELECTOR, ".result-item")
                for result in results[:10]:  # 최근 10개만
                    status["last_results"].append(result.text)
            except:
                pass
            
            return status
            
        except Exception as e:
            logger.error(f"게임 상태 가져오기 오류: {e}")
            return {}
    
    def close_browser(self):
        """브라우저 종료"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                logger.info("브라우저 종료")
        except Exception as e:
            logger.error(f"브라우저 종료 오류: {e}")