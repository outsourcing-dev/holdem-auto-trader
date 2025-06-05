# services/game_monitoring_service.py (단순화)
import logging
from selenium.webdriver.common.by import By
from modules.game_detector import GameDetector
import time
from utils.iframe_utils import switch_to_iframe_with_retry

class GameMonitoringService:
    """
    게임 모니터링 서비스 - 서버 기반으로 단순화
    복잡한 분석은 서버에서 처리하고, 기본적인 게임 상태 확인만 담당
    """
    
    def __init__(self, devtools, main_window, logger=None):
        """게임 모니터링 서비스 초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.devtools = devtools
        self.main_window = main_window
        self.game_detector = GameDetector()
        
        self.logger.info("단순화된 GameMonitoringService 초기화 완료")

    def get_current_game_state(self, log_always=True, desired_pb_count=15):
        """현재 게임 상태 분석 - 단순화"""
        try:
            if log_always:
                self.logger.debug("현재 게임 상태 분석 중...")
            
            # 기본 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            
            # iframe 전환 시도
            if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=3, max_depth=2):
                self.logger.warning("iframe 전환 실패")
                return None
            
            # 페이지 소스 가져오기
            try:
                html_content = self.devtools.driver.page_source
            except Exception as e:
                self.logger.error(f"페이지 소스 가져오기 실패: {e}")
                return None
            
            # 게임 상태 감지 (단순화된 버전)
            game_state = self.game_detector.detect_game_state(
                html_content, 
                desired_pb_count=min(desired_pb_count, 20)  # 최대 20개로 제한
            )
            
            if game_state and log_always:
                round_num = game_state.get('round', 0)
                result_count = len(game_state.get('filtered_results', []))
                self.logger.debug(f"게임 상태: 라운드 {round_num}, 결과 {result_count}개")
            
            return game_state
            
        except Exception as e:
            self.logger.error(f"게임 상태 분석 중 오류: {e}")
            
            # 오류 발생 시 기본 프레임으로 복귀
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            
            return None

    def close_current_room(self):
        """현재 방 종료 - 단순화"""
        try:
            self.logger.info("현재 방 종료 시도")
            
            # 현재 창 개수 확인
            window_handles = self.devtools.driver.window_handles
            
            # 종료 버튼 찾기 시도
            if self._try_close_room():
                self.logger.info("방 종료 버튼 클릭 완료")
                time.sleep(2)  # 종료 대기
            else:
                self.logger.warning("방 종료 버튼을 찾을 수 없음")
            
            # 로비 창으로 전환
            return self._switch_to_lobby_window(window_handles)
            
        except Exception as e:
            self.logger.error(f"방 종료 중 오류: {e}")
            
            # 오류 발생 시에도 로비 창으로 복귀 시도
            try:
                window_handles = self.devtools.driver.window_handles
                return self._switch_to_lobby_window(window_handles)
            except:
                return False

    def _try_close_room(self):
        """방 종료 버튼 찾기 및 클릭 시도"""
        try:
            # 기본 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            
            # iframe으로 전환
            if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=2):
                return False
            
            # 종료 버튼 선택자들 (단순화)
            close_selectors = [
                "button[data-role='close-button']",
                ".close-button",
                "[aria-label='Close']",
                "[title='Close']"
            ]
            
            # 종료 버튼 찾기
            for selector in close_selectors:
                try:
                    close_button = self.devtools.driver.find_element(By.CSS_SELECTOR, selector)
                    if close_button:
                        close_button.click()
                        return True
                except:
                    continue
            
            # JavaScript로 시도
            try:
                js_script = """
                var buttons = document.querySelectorAll('button, [role="button"]');
                for (var i = 0; i < buttons.length; i++) {
                    var btn = buttons[i];
                    if (btn.textContent.includes('Close') || 
                        btn.textContent.includes('Exit') ||
                        btn.getAttribute('aria-label') === 'Close') {
                        btn.click();
                        return true;
                    }
                }
                return false;
                """
                
                if self.devtools.driver.execute_script(js_script):
                    return True
                    
            except Exception as e:
                self.logger.warning(f"JavaScript 종료 시도 실패: {e}")
            
            return False
            
        except Exception as e:
            self.logger.warning(f"방 종료 시도 중 오류: {e}")
            return False

    def _switch_to_lobby_window(self, window_handles):
        """로비 창으로 전환 - 단순화"""
        try:
            # 창이 2개 이상 있으면 두 번째 창(로비)으로 전환
            if len(window_handles) >= 2:
                self.devtools.driver.switch_to.window(window_handles[1])
                self.logger.info("로비 창으로 전환 완료")
                
                # 로비 페이지인지 간단히 확인
                try:
                    current_url = self.devtools.driver.current_url
                    if "game" not in current_url.lower():
                        self.logger.debug("로비 페이지 확인됨")
                    else:
                        self.logger.warning("로비 페이지가 아닐 수 있음")
                except:
                    pass
                
                return True
                
            # 창이 하나만 있으면 그 창 사용
            elif len(window_handles) == 1:
                self.devtools.driver.switch_to.window(window_handles[0])
                self.logger.info("단일 창으로 전환")
                return True
                
            else:
                self.logger.warning("열린 창이 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"창 전환 실패: {e}")
            return False

    def is_in_game_room(self):
        """현재 게임방에 있는지 확인 - 단순화"""
        try:
            current_url = self.devtools.driver.current_url
            
            # URL에 게임 관련 키워드가 있는지 확인
            game_keywords = ["game", "live", "table"]
            
            for keyword in game_keywords:
                if keyword in current_url.lower():
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"게임방 확인 중 오류: {e}")
            return False

    def get_simple_game_info(self):
        """간단한 게임 정보만 반환 - 새로 추가"""
        try:
            game_state = self.get_current_game_state(log_always=False, desired_pb_count=5)
            
            if game_state:
                return {
                    'round': game_state.get('round', 0),
                    'latest_result': game_state.get('latest_result'),
                    'in_game': True
                }
            else:
                return {
                    'round': 0,
                    'latest_result': None,
                    'in_game': False
                }
                
        except Exception as e:
            self.logger.error(f"간단한 게임 정보 확인 중 오류: {e}")
            return {
                'round': 0,
                'latest_result': None,
                'in_game': False
            }