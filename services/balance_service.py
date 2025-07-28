# services/balance_service.py - UI 블로킹 해결
import logging
import time
from utils.parser import HTMLParser
from utils.settings_manager import SettingsManager
from PyQt6.QtWidgets import QMessageBox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
from utils.iframe_utils import IframeManager, switch_to_iframe_with_retry

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
        
        # iframe 매니저 초기화
        self.iframe_manager = None

    def get_lobby_balance(self):
        """
        카지노 로비 페이지의 iframe에서 잔액을 가져옵니다.
        UI 블로킹 문제 해결을 위해 간소화된 버전
        
        Returns:
            int: 현재 잔액 또는 None (실패 시)
        """
        try:
            # iframe 매니저 초기화
            self.iframe_manager = IframeManager(self.devtools.driver)
            
            # 기본 컨텐츠로 전환
            self.devtools.driver.switch_to.default_content()
            
            # 간단한 iframe 전환 (성능 최적화)
            iframe_switched = self._simple_iframe_switch()
            
            if not iframe_switched:
                self.logger.error("iframe 전환 실패")
                return None
            
            # 우선순위별로 잔액 요소 찾기 (성공률이 높은 것부터)
            balance = self._get_balance_with_priority()
            
            # 기본 컨텐츠로 돌아가기
            self.devtools.driver.switch_to.default_content()
            
            return balance
            
        except Exception as e:
            self.logger.error(f"로비 iframe에서 잔액 가져오기 실패: {e}", exc_info=True)
            
            # 기본 컨텐츠로 돌아가기 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            
            return None

    def _simple_iframe_switch(self):
        """
        간단하고 빠른 iframe 전환 - UI 블로킹 방지
        
        Returns:
            bool: 전환 성공 여부
        """
        try:
            # 방법 1: 첫 번째 iframe으로 빠른 전환
            iframes = self.devtools.driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                self.devtools.driver.switch_to.frame(iframes[0])
                
                # 중첩된 iframe 확인 (최소한만)
                nested_iframes = self.devtools.driver.find_elements(By.TAG_NAME, "iframe")
                if nested_iframes:
                    self.devtools.driver.switch_to.frame(nested_iframes[0])
                    self.logger.info("잔액 확인: 중첩된 iframe으로 전환 완료")
                else:
                    self.logger.info("잔액 확인: 단일 iframe으로 전환 완료")
                return True
            
            # 방법 2: 유틸리티 함수 사용 (빠른 설정)
            return switch_to_iframe_with_retry(self.devtools.driver, max_retries=2, max_depth=2)
            
        except Exception as e:
            self.logger.warning(f"iframe 전환 중 오류: {e}")
            return False

    def _get_balance_with_priority(self):
        """
        우선순위에 따라 잔액 요소 찾기 - 성능 최적화
        
        Returns:
            int: 잔액 또는 None
        """
        # 우선순위 1: header-balance (가장 성공률 높음)
        balance = self._try_header_balance()
        if balance is not None:
            return balance
        
        # 우선순위 2: balance-label-value
        balance = self._try_balance_label_value()
        if balance is not None:
            return balance
        
        # 우선순위 3: Typography 클래스
        balance = self._try_typography_balance()
        if balance is not None:
            return balance
        
        # 우선순위 4: 전체 span 검색 (최후의 수단)
        balance = self._try_all_spans()
        if balance is not None:
            return balance
        
        self.logger.error("모든 방법으로 잔액을 찾을 수 없습니다.")
        return None

    def _try_header_balance(self):
        """header-balance 방식으로 잔액 가져오기"""
        try:
            balance_element = self.devtools.driver.find_element(
                By.CSS_SELECTOR, "[data-role='header-balance']"
            )
            if balance_element:
                balance_text = balance_element.text
                self.logger.info(f"header-balance에서 잔액 텍스트: {balance_text}")
                balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                self.logger.info(f"로비 iframe에서 가져온 잔액: {balance:,}원 (header-balance)")
                return balance
        except Exception:
            pass
        return None

    def _try_balance_label_value(self):
        """balance-label-value 방식으로 잔액 가져오기"""
        try:
            balance_element = self.devtools.driver.find_element(
                By.CSS_SELECTOR, "span[data-role='balance-label-value']"
            )
            if balance_element:
                balance_text = balance_element.text
                balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                self.logger.info(f"로비 iframe에서 가져온 잔액: {balance:,}원 (balance-label-value)")
                return balance
        except Exception:
            pass
        return None

    def _try_typography_balance(self):
        """Typography 클래스로 잔액 가져오기"""
        try:
            typography_selector = "span.Typography--d2c9a[data-role='header-balance']"
            balance_element = self.devtools.driver.find_element(By.CSS_SELECTOR, typography_selector)
            if balance_element:
                balance_text = balance_element.text
                balance = int(re.sub(r'[^\d]', '', balance_text) or '0')
                self.logger.info(f"로비 iframe에서 가져온 잔액: {balance:,}원 (Typography header-balance)")
                return balance
        except Exception:
            pass
        return None

    def _try_all_spans(self):
        """모든 span 요소에서 잔액 찾기 (최후의 수단)"""
        try:
            # 시간 제한을 두고 검색 (UI 블로킹 방지)
            all_spans = self.devtools.driver.find_elements(By.TAG_NAME, "span")
            
            # 최대 20개만 검사 (성능 최적화)
            spans_to_check = all_spans[:20]
            
            for span in spans_to_check:
                try:
                    span_text = span.text
                    if '₩' in span_text or '원' in span_text:
                        balance = int(re.sub(r'[^\d]', '', span_text) or '0')
                        if balance > 100:  # 잔액은 보통 큰 숫자
                            self.logger.info(f"로비 iframe에서 가져온 잔액: {balance:,}원 (span 태그)")
                            return balance
                except Exception:
                    continue
        except Exception:
            pass
        return None
        
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
            
            # 목표 금액 확인 - 중앙 집중식 체커 사용
            self.check_target_amount(balance, source="최초 입장")
            
            return True
                
        except Exception as e:
            self.logger.error(f"잔액 정보 업데이트 실패: {e}", exc_info=True)
            return False
        
    def get_iframe_balance(self):
        """
        iframe 내에서 잔액을 가져옵니다.
        간소화된 버전 - get_lobby_balance와 동일한 로직 사용
        
        Returns:
            int: 현재 잔액 또는 None (실패 시)
        """
        return self.get_lobby_balance()

    def check_target_amount(self, current_balance, source="BalanceService"):
        """
        현재 잔액이 목표 금액에 도달했는지 확인하고, 도달했으면 자동 매매를 중지합니다.
        도달했을 경우 카지노 창을 닫고 메인 창으로 포커싱을 변경합니다.
        """
        # 자동 매매가 활성화된 상태일 때만 확인
        if not hasattr(self.main_window, 'trading_manager') or not self.main_window.trading_manager.is_trading_active:
            return False
            
        # 이미 목표 금액에 도달했다고 알림을 표시했는지 확인하는 플래그 추가
        if hasattr(self, '_target_amount_reached') and self._target_amount_reached:
            self.logger.info(f"[{source}] 이미 목표 금액 도달 알림이 표시되었습니다. 추가 알림 방지.")
            return True
            
        # 목표 금액 항상 새로 가져오기 (캐시된 값 대신 파일에서 직접 읽기)
        target_amount = self.settings_manager.get_target_amount()
        self.logger.info(f"[{source}] 현재 목표 금액: {target_amount:,}원, 현재 잔액: {current_balance:,}원")
        
        # 목표 금액이 설정되어 있고(0보다 큼), 현재 잔액이 목표 금액 이상이면
        if target_amount > 0 and current_balance >= target_amount:
            self.logger.info(f"[{source}] 목표 금액({target_amount:,}원)에 도달했습니다! 현재 잔액: {current_balance:,}원")
            
            # 중복 알림 방지를 위해 플래그 설정
            self._target_amount_reached = True
            
            # 중요: 즉시 모든 스레드와 진행 중인 작업 중지
            if hasattr(self.main_window, 'trading_manager'):
                # 중지 플래그 설정
                self.main_window.trading_manager.stop_all_processes = True
                self.logger.info("목표 금액 도달: 모든 프로세스 중지 플래그 설정")
                
                # 타이머 즉시 중지
                if hasattr(self.main_window, 'timer') and self.main_window.timer.isActive():
                    self.main_window.timer.stop()
                    self.logger.info("타이머 중지됨")
                
                # 자동 매매 중지 즉시 호출
                self.main_window.trading_manager.stop_trading()
                self.logger.info("자동 매매 종료 메서드 호출됨")
                
                # 간단하게 웹페이지만 종료하는 코드 추가
                try:
                    # 현재 열린 창 모두 가져오기
                    window_handles = self.devtools.driver.window_handles
                    
                    # 2개 이상의 창이 열려 있는 경우 (카지노 창이 있는 경우)
                    if len(window_handles) >= 2:
                        # 메인 창으로 전환 (1번 창)
                        self.devtools.driver.switch_to.window(window_handles[0])
                        self.logger.info("메인 창(1번 창)으로 포커싱 전환 완료")
                        
                        # 카지노 창(2번 창부터) 닫기
                        for i in range(1, len(window_handles)):
                            # 카지노 창으로 전환
                            self.devtools.driver.switch_to.window(window_handles[i])
                            # 창 닫기
                            self.devtools.driver.close()
                            self.logger.info(f"{i+1}번 창(카지노 창) 닫기 완료")
                        
                        # 다시 메인 창으로 전환
                        self.devtools.driver.switch_to.window(window_handles[0])
                        self.logger.info("모든 카지노 창 닫기 후 메인 창으로 포커싱 전환 완료")
                except Exception as e:
                    self.logger.error(f"카지노 창 닫기 중 오류 발생: {e}")
            
            # 빵빠레 사운드 재생
            try:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
                import os
                import sys
                
                # 사운드 파일 경로 지정 (실행 경로에 따라 다르게 처리)
                if getattr(sys, 'frozen', False):
                    # PyInstaller로 실행된 경우
                    base_dir = os.path.dirname(sys.executable)
                    sound_paths = [
                        os.path.join(base_dir, "_internal", "bbang.mp3"),
                        os.path.join(base_dir, "_internal", "bbang.wav"),
                        os.path.join(base_dir, "bbang.mp3"),
                        os.path.join(base_dir, "bbang.wav")
                    ]
                else:
                    # 개발 환경에서 실행된 경우
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    sound_paths = [
                        os.path.join(base_dir, "bbang.mp3"),
                        os.path.join(base_dir, "bbang.wav"),
                        os.path.join(os.path.dirname(base_dir), "bbang.mp3"),
                        os.path.join(os.path.dirname(base_dir), "bbang.wav"),
                    ]
                
                # 존재하는 첫 번째 파일 사용
                sound_file = None
                for path in sound_paths:
                    if os.path.exists(path):
                        sound_file = path
                        break
                
                self.logger.info(f"빵빠레 사운드 재생 시도: {sound_file}")
                
                if sound_file and os.path.exists(sound_file):
                    # QMediaPlayer 초기화
                    self.player = QMediaPlayer()
                    self.audio_output = QAudioOutput()
                    self.player.setAudioOutput(self.audio_output)
                    
                    # 볼륨 설정 (0.0 ~ 1.0)
                    self.audio_output.setVolume(0.8)
                    
                    # 미디어 설정 및 재생
                    self.player.setSource(QUrl.fromLocalFile(os.path.abspath(sound_file)))
                    self.player.play()
                    
                    self.logger.info("목표 금액 달성 빵빠레 사운드 재생 중...")
                else:
                    self.logger.warning(f"빵빠레 사운드 파일을 찾을 수 없습니다: {sound_file}")
            except Exception as e:
                self.logger.error(f"빵빠레 사운드 재생 중 오류 발생: {e}")
            
            # 메시지 박스 표시
            QMessageBox.information(
                self.main_window, 
                "목표 금액 달성", 
                f"축하합니다! 목표 금액({target_amount:,}원)에 도달했습니다.\n현재 잔액: {current_balance:,}원\n자동 매매를 종료합니다."
            )
            
            return True
        
        # 목표 금액 접근 중인 경우 로그 표시 (80% 이상이면)
        if target_amount > 0 and current_balance >= target_amount * 0.8:
            progress = current_balance / target_amount * 100
            self.logger.info(f"목표 금액 접근 중: {progress:.1f}% (현재: {current_balance:,}원, 목표: {target_amount:,}원)")
        
        return False