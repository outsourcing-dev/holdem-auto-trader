# services/balance_service.py
import logging
from utils.parser import HTMLParser

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
                start_amount=balance,
                current_amount=balance
            )
            
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
            
            # 잔액 요소 찾기
            balance_element = self.devtools.driver.find_element("css selector", "span[data-role='balance-label-value']")
            balance_text = balance_element.text
            
            # 숫자만 추출 (₩과 콤마, 특수 문자 제거)
            balance = int(balance_text.replace('₩', '').replace(',', '').replace('⁩', '').replace('⁦', '').strip() or '0')
            
            self.logger.info(f"iframe에서 가져온 잔액: {balance:,}원")
            
            # 기본 컨텐츠로 돌아가기
            self.devtools.driver.switch_to.default_content()
            
            return balance
            
        except Exception as e:
            self.logger.error(f"iframe에서 잔액 가져오기 실패: {e}", exc_info=True)
            
            # 기본 컨텐츠로 돌아가기 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            
            return None