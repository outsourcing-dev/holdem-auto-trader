"""
자동 로그인 모듈
사이트 자동 로그인 및 Evolution 게임 접속
"""
import logging
import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

class AutoLogin:
    """자동 로그인 클래스"""
    
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)
        
    def login_to_site(self, username: str, password: str) -> bool:
        """사이트 로그인"""
        try:
            logger.info(f"로그인 시도: {username}")
            
            # 로그인 버튼 찾기 및 클릭
            login_button_selectors = [
                "a[href='#none']:contains('로그인')",
                "a.login-btn",
                "button:contains('로그인')",
                "//a[contains(text(), '로그인')]",
                "//button[contains(text(), '로그인')]"
            ]
            
            login_clicked = False
            for selector in login_button_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath
                        element = self.driver.find_element(By.XPATH, selector)
                    else:
                        # CSS Selector
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    element.click()
                    login_clicked = True
                    logger.info("로그인 버튼 클릭 성공")
                    time.sleep(2)  # 로그인 폼 로딩 대기
                    break
                except:
                    continue
            
            if not login_clicked:
                # JavaScript로 로그인 링크 찾기
                try:
                    self.driver.execute_script("""
                        var links = document.querySelectorAll('a');
                        for(var i=0; i<links.length; i++) {
                            if(links[i].textContent.includes('로그인')) {
                                links[i].click();
                                break;
                            }
                        }
                    """)
                    time.sleep(2)
                    logger.info("JavaScript로 로그인 버튼 클릭")
                except:
                    logger.error("로그인 버튼을 찾을 수 없습니다")
                    return False
            
            # 아이디 입력
            id_selectors = [
                "input[placeholder*='아이디']",
                "input[name='user_id']",
                "input[name='username']",
                "input[name='id']",
                "#user_id",
                "#username"
            ]
            
            id_entered = False
            for selector in id_selectors:
                try:
                    id_field = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    id_field.clear()
                    id_field.send_keys(username)
                    id_entered = True
                    logger.info("아이디 입력 성공")
                    break
                except:
                    continue
            
            if not id_entered:
                logger.error("아이디 입력 필드를 찾을 수 없습니다")
                return False
            
            # 비밀번호 입력
            pw_selectors = [
                "input[placeholder*='비밀번호']",
                "input[name='user_pw']",
                "input[name='password']",
                "input[type='password']",
                "#user_pw",
                "#password"
            ]
            
            pw_entered = False
            for selector in pw_selectors:
                try:
                    pw_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    pw_field.clear()
                    pw_field.send_keys(password)
                    pw_entered = True
                    logger.info("비밀번호 입력 성공")
                    break
                except:
                    continue
            
            if not pw_entered:
                logger.error("비밀번호 입력 필드를 찾을 수 없습니다")
                return False
            
            # 로그인 버튼 클릭
            login_submit_selectors = [
                "button.btn-login",
                "button:contains('로그인')",
                "input[type='submit']",
                "button[type='submit']",
                ".login-form button"
            ]
            
            for selector in login_submit_selectors:
                try:
                    submit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    submit_btn.click()
                    logger.info("로그인 제출 버튼 클릭")
                    break
                except:
                    continue
            
            # JavaScript로 로그인 버튼 클릭
            try:
                self.driver.execute_script("""
                    var buttons = document.querySelectorAll('button');
                    for(var i=0; i<buttons.length; i++) {
                        if(buttons[i].textContent.includes('로그인')) {
                            buttons[i].click();
                            break;
                        }
                    }
                """)
            except:
                pass
            
            time.sleep(3)  # 로그인 처리 대기
            
            # 로그인 성공 확인
            if self.check_login_success():
                logger.info("✅ 로그인 성공!")
                return True
            else:
                logger.error("❌ 로그인 실패")
                return False
            
        except Exception as e:
            logger.error(f"로그인 오류: {e}")
            return False
    
    def check_login_success(self) -> bool:
        """로그인 성공 여부 확인"""
        try:
            # 로그아웃 버튼이 있으면 로그인 성공
            logout_selectors = [
                "button:contains('로그아웃')",
                "a:contains('로그아웃')",
                ".logout-btn",
                "#logout"
            ]
            
            for selector in logout_selectors:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, selector)
                    return True
                except:
                    continue
            
            # 사용자 정보가 표시되면 로그인 성공
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
                if "LV." in page_text or "캐쉬" in page_text or "포인트" in page_text:
                    return True
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"로그인 확인 오류: {e}")
            return False
    
    def navigate_to_evolution(self) -> bool:
        """Evolution 게임으로 이동"""
        try:
            logger.info("Evolution 게임으로 이동 시작")
            
            # LIVE CASINO 버튼 클릭
            live_casino_selectors = [
                "button:contains('LIVE CASINO')",
                ".live-casino-btn",
                "button.btn-live",
                "a:contains('LIVE CASINO')"
            ]
            
            for selector in live_casino_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    element.click()
                    logger.info("LIVE CASINO 버튼 클릭")
                    time.sleep(2)
                    break
                except:
                    continue
            
            # JavaScript로 LIVE CASINO 클릭
            try:
                self.driver.execute_script("""
                    var buttons = document.querySelectorAll('button');
                    for(var i=0; i<buttons.length; i++) {
                        if(buttons[i].textContent.includes('LIVE CASINO')) {
                            buttons[i].click();
                            break;
                        }
                    }
                """)
                time.sleep(2)
            except:
                pass
            
            # Evolution 링크 클릭
            evolution_selectors = [
                "a:contains('에볼루션')",
                "a[href*='evolution']",
                ".evolution-link",
                "img[alt*='에볼루션']"
            ]
            
            for selector in evolution_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    element.click()
                    logger.info("Evolution 링크 클릭")
                    time.sleep(3)
                    break
                except:
                    continue
            
            # JavaScript로 Evolution 클릭
            try:
                self.driver.execute_script("""
                    var links = document.querySelectorAll('a');
                    for(var i=0; i<links.length; i++) {
                        if(links[i].textContent.includes('에볼루션')) {
                            links[i].click();
                            break;
                        }
                    }
                """)
            except:
                pass
            
            # 새 탭이 열렸는지 확인
            if len(self.driver.window_handles) > 1:
                # 새 탭으로 전환
                self.driver.switch_to.window(self.driver.window_handles[-1])
                logger.info("Evolution 게임 탭으로 전환")
                
                # Evolution 페이지 로딩 대기
                time.sleep(5)
                
                # Evolution 페이지인지 확인
                if "evo-games" in self.driver.current_url or "evolution" in self.driver.current_url.lower():
                    logger.info("✅ Evolution 게임 페이지 접속 성공!")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Evolution 이동 오류: {e}")
            return False
    
    def perform_auto_login(self, site_url: str, username: str, password: str) -> bool:
        """전체 자동 로그인 프로세스"""
        try:
            logger.info(f"자동 로그인 프로세스 시작: {site_url}")
            
            # 1. 사이트 접속
            if not site_url.startswith('http'):
                site_url = f'https://{site_url}'
            
            self.driver.get(site_url)
            time.sleep(3)
            
            # 2. 로그인
            if not self.login_to_site(username, password):
                logger.error("로그인 실패")
                return False
            
            # 3. Evolution 게임으로 이동
            if not self.navigate_to_evolution():
                logger.error("Evolution 게임 이동 실패")
                return False
            
            logger.info("✅ 자동 로그인 프로세스 완료!")
            return True
            
        except Exception as e:
            logger.error(f"자동 로그인 프로세스 오류: {e}")
            return False