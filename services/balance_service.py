# services/balance_service.py
import logging
import time
from utils.parser import HTMLParser
from utils.settings_manager import SettingsManager
from PyQt6.QtWidgets import QMessageBox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

class BalanceService:
    def __init__(self, devtools, main_window, logger=None):
        """
        잔액 관리 서비스 초기화
        
        Args:
            devtools (DevToolsController): 브라우저 제어 객체
            main_window (QMainWindow): 메인 윈도우 객체
            logger (logging.Logger, optional): 로깅을 위한 로거 객체
        """
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.devtools = devtools
        self.main_window = main_window
        self.settings_manager = SettingsManager()

    def get_lobby_balance(self):
        """
        카지노 로비 페이지의 iframe에서 잔액을 가져옵니다.
        
        Returns:
            int: 현재 잔액 또는 None (실패 시)
        """
        try:
            # 현재 페이지 소스 가져오기
            html = self.devtools.get_page_source()
            
            if not html:
                self.logger.error("페이지 소스를 가져올 수 없습니다.")
                return None
            
            # iframe 찾기 및 전환
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element("css selector", "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # iframe 내부 소스 가져오기
            iframe_html = self.devtools.driver.page_source
            
            # 방법 1: data-role="header-balance" 속성을 가진 요소 찾기
            try:
                balance_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "[data-role='header-balance']")
                if balance_element:
                    balance_text = balance_element.text
                    self.logger.info(f"data-role='header-balance' 속성을 가진 요소에서 잔액 텍스트: {balance_text}")
                    # 숫자만 추출 (₩과 콤마, 특수 문자 제거)
                    balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                    self.logger.info(f"로비 iframe에서 가져온 잔액: {balance:,}원 (header-balance)")
                    
                    # 기본 컨텐츠로 돌아가기
                    self.devtools.driver.switch_to.default_content()
                    return balance
            except Exception as e:
                self.logger.warning(f"header-balance로 잔액 가져오기 실패: {e}")
            
            # 방법 2: Typography 클래스를 가진 header-balance 요소 찾기 (추가된 방법)
            try:
                typography_selector = "span.Typography--d2c9a[data-role='header-balance']"
                balance_element = self.devtools.driver.find_element(By.CSS_SELECTOR, typography_selector)
                if balance_element:
                    balance_text = balance_element.text
                    self.logger.info(f"Typography 클래스의 header-balance에서 잔액 텍스트: {balance_text}")
                    # 숫자만 추출
                    balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                    self.logger.info(f"로비 iframe에서 가져온 잔액: {balance:,}원 (Typography header-balance)")
                    
                    # 기본 컨텐츠로 돌아가기
                    self.devtools.driver.switch_to.default_content()
                    return balance
            except Exception as e:
                self.logger.warning(f"Typography header-balance로 잔액 가져오기 실패: {e}")
            
            # 방법 3: 기존 balance-label-value 방식 (백업)
            try:
                # 잔액 요소 찾기 (iframe 내부에서 잔액을 표시하는 요소)
                balance_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "span[data-role='balance-label-value']")
                if balance_element:
                    balance_text = balance_element.text
                    # 숫자만 추출 (₩과 콤마, 특수 문자 제거)
                    balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                    self.logger.info(f"로비 iframe에서 가져온 잔액: {balance:,}원 (balance-label-value)")
                    
                    # 기본 컨텐츠로 돌아가기
                    self.devtools.driver.switch_to.default_content()
                    return balance
            except Exception as e:
                self.logger.warning(f"balance-label-value로 잔액 가져오기 실패: {e}")
            
            # 방법 4: 클래스 이름으로 Typography 요소 찾기
            try:
                # 클래스 이름으로 잔액 요소 찾기 시도
                balance_elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, ".Typography--d2c9a")
                for element in balance_elements:
                    balance_text = element.text
                    if '₩' in balance_text or '원' in balance_text:
                        self.logger.info(f"Typography 클래스에서 잔액 후보 텍스트: {balance_text}")
                        # 숫자만 추출
                        balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                        self.logger.info(f"로비 iframe에서 가져온 잔액: {balance:,}원 (Typography)")
                        
                        # 기본 컨텐츠로 돌아가기
                        self.devtools.driver.switch_to.default_content()
                        return balance
            except Exception as e:
                self.logger.warning(f"Typography 클래스로 잔액 가져오기 실패: {e}")
            
            # 방법 5: 내용에 '₩' 또는 '원'이 있는 모든 요소 검색
            try:
                # XPath로 검색
                xpath_expr = "//*[contains(text(), '₩') or contains(text(), '원')]"
                balance_candidates = self.devtools.driver.find_elements(By.XPATH, xpath_expr)
                
                for element in balance_candidates:
                    balance_text = element.text
                    self.logger.info(f"₩/원 포함 요소 발견: {balance_text}")
                    # 숫자만 추출
                    numbers = re.findall(r'\d+', re.sub(r'[,\.]', '', balance_text))
                    if numbers:
                        largest_number = max([int(num) for num in numbers])
                        if largest_number > 100:  # 잔액은 보통 큰 숫자이므로 필터링
                            self.logger.info(f"로비 iframe에서 가져온 잔액: {largest_number:,}원 (XPath)")
                            
                            # 기본 컨텐츠로 돌아가기
                            self.devtools.driver.switch_to.default_content()
                            return largest_number
            except Exception as e:
                self.logger.warning(f"XPath로 잔액 가져오기 실패: {e}")
            
            # 기본 컨텐츠로 돌아가기
            self.devtools.driver.switch_to.default_content()
            
            self.logger.error("모든 방법으로 잔액을 찾을 수 없습니다.")
            return None
            
        except Exception as e:
            self.logger.error(f"로비 iframe에서 잔액 가져오기 실패: {e}", exc_info=True)
            
            # 기본 컨텐츠로 돌아가기 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            
            return None
        
    def get_current_balance_and_username(self):
        """
        현재 잔액과 사용자 이름을 가져옵니다.
        
        Returns:
            tuple: (balance, username) 또는 (None, None) (실패 시)
        """
        try:
            # 페이지 소스 가져오기
            html = self.devtools.get_page_source()
            
            if not html:
                self.logger.error("페이지 소스를 가져올 수 없습니다.")
                return None, None
                
            # 잔액 및 사용자 이름 파싱
            parser = HTMLParser(html)
            balance = parser.get_balance()
            username = parser.get_username()
            
            if balance is not None:
                self.logger.info(f"현재 잔액: {balance}원")
                
            if username:
                self.logger.info(f"유저명: {username}")
                
            return balance, username
            
        except Exception as e:
            self.logger.error(f"잔액 정보 가져오기 실패: {e}", exc_info=True)
            return None, None
            
    def update_balance_and_user_data(self, balance, username):
        """
        UI에 잔액 및 사용자 정보를 업데이트합니다.
        
        Args:
            balance (int): 현재 잔액
            username (str): 사용자 이름
                
        Returns:
            bool: 성공 여부
        """
        try:
            if balance is None:
                return False
                
            # UI 업데이트
            self.main_window.update_user_data(
                username=username,
                start_amount=balance,  # 시작 금액 업데이트
                current_amount=balance  # 현재 금액 업데이트
            )
            
            # 목표 금액 확인 - 중앙 집중식 체커 사용
            self.check_target_amount(balance, source="최초 입장")
            
            return True
                
        except Exception as e:
            self.logger.error(f"잔액 정보 업데이트 실패: {e}", exc_info=True)
            return False
        
    def get_iframe_balance(self):
        """
        iframe 내에서 잔액을 가져옵니다.
        
        Returns:
            int: 현재 잔액 또는 None (실패 시)
        """
        try:
            # iframe으로 전환
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element("css selector", "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # 방법 1: 기본 잔액 요소 찾기
            try:
                balance_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "span[data-role='balance-label-value']")
                balance_text = balance_element.text
                
                # 숫자만 추출 (₩과 콤마, 특수 문자 제거)
                balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                
                self.logger.info(f"iframe에서 가져온 잔액: {balance:,}원 (balance-label-value)")
                
                # 기본 컨텐츠로 돌아가기
                self.devtools.driver.switch_to.default_content()
                
                return balance
            except Exception as e:
                self.logger.warning(f"balance-label-value로 iframe 잔액 가져오기 실패: {e}")
            
            # 방법 2: 다른 속성 찾기
            try:
                # 다른 속성으로 시도
                balance_element = self.devtools.driver.find_element(By.CSS_SELECTOR, "[data-role='header-balance']")
                balance_text = balance_element.text
                
                # 숫자만 추출 (₩과 콤마, 특수 문자 제거)
                balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                
                self.logger.info(f"iframe에서 가져온 잔액: {balance:,}원 (header-balance)")
                
                # 기본 컨텐츠로 돌아가기
                self.devtools.driver.switch_to.default_content()
                
                return balance
            except Exception as e:
                self.logger.warning(f"header-balance로 iframe 잔액 가져오기 실패: {e}")
            
            # 방법 3: 내용에 '₩' 또는 '원'이 있는 모든 요소 검색
            try:
                # XPath로 검색
                xpath_expr = "//*[contains(text(), '₩') or contains(text(), '원')]"
                balance_candidates = self.devtools.driver.find_elements(By.XPATH, xpath_expr)
                
                for element in balance_candidates:
                    balance_text = element.text
                    self.logger.info(f"₩/원 포함 요소 발견: {balance_text}")
                    # 숫자만 추출
                    numbers = re.findall(r'\d+', re.sub(r'[,\.]', '', balance_text))
                    if numbers:
                        largest_number = max([int(num) for num in numbers])
                        if largest_number > 100:  # 잔액은 보통 큰 숫자이므로 필터링
                            self.logger.info(f"iframe에서 가져온 잔액: {largest_number:,}원 (XPath)")
                            
                            # 기본 컨텐츠로 돌아가기
                            self.devtools.driver.switch_to.default_content()
                            return largest_number
            except Exception as e:
                self.logger.warning(f"XPath로 iframe 잔액 가져오기 실패: {e}")
            
            # 기본 컨텐츠로 돌아가기
            self.devtools.driver.switch_to.default_content()
            
            self.logger.error("모든 방법으로 iframe 잔액을 찾을 수 없습니다.")
            return None
            
        except Exception as e:
            self.logger.error(f"iframe에서 잔액 가져오기 실패: {e}", exc_info=True)
            
            # 기본 컨텐츠로 돌아가기 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            
            return None
        
    def update_balance_after_bet_result(self, is_win=False):
        """
        베팅 결과 확인 후 잔액을 업데이트합니다.
        
        Args:
            is_win (bool): 베팅 성공 여부 (성공 시 지연 적용)
        
        Returns:
            int: 업데이트된 잔액 또는 None (실패 시)
        """
        try:
            # 성공 시 3~4초 지연
            if is_win:
                self.logger.info("베팅 성공! 잔액 업데이트 전 3초 대기...")
                time.sleep(2)
            
            self.logger.info("베팅 결과 후 잔액 확인")
            
            # iframe 내에서 잔액 가져오기
            balance = self.get_iframe_balance()
            
            if balance is None:
                self.logger.error("iframe에서 잔액을 가져올 수 없습니다.")
                return None
            
            self.logger.info(f"현재 잔액: {balance:,}원")
            
            # UI 업데이트
            self.main_window.update_user_data(current_amount=balance)
            
            # 목표 금액 확인하여 도달 시 자동 매매 중지
            self.check_target_amount(balance, source="베팅 결과")
            
            return balance
            
        except Exception as e:
            self.logger.error(f"잔액 확인 중 오류 발생: {e}")
            return None
        
    def check_target_amount(self, current_balance, source="BalanceService"):
        """
        현재 잔액이 목표 금액에 도달했는지 확인하고, 도달했으면 자동 매매를 중지합니다.
        
        Args:
            current_balance (int): 현재 잔액
            source (str): 호출 출처 (로깅용)
        
        Returns:
            bool: 목표 금액 도달 여부
        """
        # 자동 매매가 활성화된 상태일 때만 확인
        if not hasattr(self.main_window, 'trading_manager') or not self.main_window.trading_manager.is_trading_active:
            return False
        
        # 목표 금액 항상 새로 가져오기 (캐시된 값 대신 파일에서 직접 읽기)
        target_amount = self.settings_manager.get_target_amount()
        self.logger.info(f"[{source}] 현재 목표 금액: {target_amount:,}원, 현재 잔액: {current_balance:,}원")
        
        # 목표 금액이 설정되어 있고(0보다 큼), 현재 잔액이 목표 금액 이상이면
        if target_amount > 0 and current_balance >= target_amount:
            self.logger.info(f"[{source}] 목표 금액({target_amount:,}원)에 도달했습니다! 현재 잔액: {current_balance:,}원")
            
            # 메시지 박스 표시
            QMessageBox.information(
                self.main_window, 
                "목표 금액 달성", 
                f"축하합니다! 목표 금액({target_amount:,}원)에 도달했습니다.\n현재 잔액: {current_balance:,}원\n자동 매매를 종료합니다."
            )
            
            # 자동 매매 중지
            self.main_window.trading_manager.stop_trading()
            return True
        
        # 목표 금액 접근 중인 경우 로그 표시 (80% 이상이면)
        if target_amount > 0 and current_balance >= target_amount * 0.8:
            progress = current_balance / target_amount * 100
            self.logger.info(f"목표 금액 접근 중: {progress:.1f}% (현재: {current_balance:,}원, 목표: {target_amount:,}원)")
        
        return False