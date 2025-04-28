# services/game_monitoring_service.py
import logging
from selenium.webdriver.common.by import By
from modules.game_detector import GameDetector
import time
from utils.iframe_utils import switch_to_iframe_with_retry

class GameMonitoringService:
    def __init__(self, devtools, main_window, logger=None):
        """게임 모니터링 서비스 초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.devtools = devtools
        self.main_window = main_window
        self.game_detector = GameDetector()

    def get_current_game_state(self, log_always=True, desired_pb_count=15):
        """현재 게임 상태를 분석"""
        try:
            if log_always:
                self.logger.info("현재 게임 상태 분석 중...")
            
            # 기본 프레임으로 전환
            self.devtools.driver.switch_to.default_content()
            
            # iframe 전환
            if not switch_to_iframe_with_retry(self.devtools.driver, max_retries=5, max_depth=2):
                self.logger.error("게임 상태 확인: iframe 전환 실패")
                return None
            
            # 페이지 소스 가져오기
            html_content = self.devtools.driver.page_source
            
            # 게임 상태 감지
            game_state = self.game_detector.detect_game_state(html_content, desired_pb_count=desired_pb_count)
            
            # 여기서 게임 상태를 반환하기 전에 `results` 상태를 확인
            # self.logger.info(f"[DEBUG] 게임 상태에서 받은 결과: {game_state['filtered_results']}")
            
            return game_state
            
        except Exception as e:
            self.logger.error(f"게임 상태 분석 중 오류 발생: {e}", exc_info=True)
            
            # 오류 발생 시 기본 프레임으로 복귀 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            
            return None

    def close_current_room(self):
            """현재 열린 방을 종료하고 카지노 로비 창으로 포커싱 전환"""
            try:
                # 방 나가기 전 최종 잔액 업데이트 시도
                # try:
                #     balance = self.main_window.trading_manager.balance_service.update_balance_after_bet_result()
                #     self.logger.info(f"방 나가기 전 최종 잔액: {balance:,}원")
                # except Exception as e:
                #     self.logger.warning(f"방 나가기 전 잔액 확인 실패: {e}")
                
                # 현재 창 개수 확인
                window_handles = self.devtools.driver.window_handles
                # self.logger.info(f"현재 열린 창 개수: {len(window_handles)}")
                
                # iframe 내부로 이동하여 종료 버튼 찾기
                try:
                    # 기본 프레임으로 전환
                    self.devtools.driver.switch_to.default_content()
                    
                    # 개선된 iframe 전환
                    iframe_switched = switch_to_iframe_with_retry(self.devtools.driver, max_retries=3)
                    
                    if iframe_switched:
                        self.logger.info("iframe 내부로 이동 성공, 종료 버튼 찾는 중...")
                        
                        # 종료 버튼 찾기 위한 선택자 목록
                        close_button_selectors = [
                            "button[data-role='close-button']",
                            ".close-button",
                            "[aria-label='Close']",
                            "[aria-label='Exit']",
                            "[title='Close']"
                        ]
                        
                        # 종료 버튼 찾기 (다중 선택자 접근)
                        close_button = None
                        for selector in close_button_selectors:
                            try:
                                close_button = self.devtools.driver.find_element(By.CSS_SELECTOR, selector)
                                break
                            except:
                                continue
                        
                        # 버튼 클릭 시도
                        if close_button:
                            try:
                                close_button.click()
                                # self.logger.info("방 종료 버튼 클릭 완료!")
                                time.sleep(2)
                            except Exception as e:
                                self.logger.warning(f"종료 버튼 클릭 실패: {e}")
                                # JavaScript로 시도 (실패한 경우)
                                try:
                                    self.devtools.driver.execute_script(
                                        f"document.querySelector('{close_button_selectors[0]}').click();"
                                    )
                                    # self.logger.info("JavaScript로 종료 버튼 클릭 완료!")
                                    time.sleep(1)
                                except:
                                    self.logger.warning("모든 종료 버튼 클릭 시도 실패")
                        else:
                            self.logger.warning("종료 버튼을 찾을 수 없음")
                    else:
                        self.logger.warning("iframe 전환 실패, 종료 버튼을 찾을 수 없음")
                except Exception as e:
                    self.logger.warning(f"iframe 전환 또는 종료 버튼 찾기 실패: {e}")
                
                # 메인 프레임으로 전환 시도
                try:
                    self.devtools.driver.switch_to.default_content()
                except:
                    self.logger.warning("메인 프레임 전환 실패")
                
                # 로비 창으로 전환
                return self._switch_to_lobby_window(window_handles)
            except Exception as e:
                self.logger.error(f"방 종료 시도 중 오류: {e}", exc_info=True)
                
                # 오류 발생 시에도 최대한 로비 창으로 복귀 시도
                try:
                    self.devtools.driver.switch_to.default_content()
                    window_handles = self.devtools.driver.window_handles
                    return self._switch_to_lobby_window(window_handles)
                except:
                    pass
                    
                return False
            
    def _is_lobby_page(self):
        """
        현재 페이지가 로비 페이지인지 확인
        
        Returns:
            bool: 로비 페이지 여부
        """
        try:
            # URL 확인
            current_url = self.devtools.driver.current_url
            
            # URL에 'game' 또는 'live'가 포함되어 있지 않으면 로비 페이지로 간주
            if "game" not in current_url.lower() and "live" not in current_url.lower():
                return True
                
            # 페이지 제목 확인
            title = self.devtools.driver.title
            if "lobby" in title.lower():
                return True
                
            # 로비 페이지 특정 요소 확인
            try:
                # 로비에만 있는 요소들
                lobby_elements = self.devtools.driver.find_elements(By.CSS_SELECTOR, 
                    "div.lobby, .lobby-container, [data-role='game-tile'], .search-input")
                
                if len(lobby_elements) > 0:
                    return True
            except:
                pass
                
            return False
        except Exception as e:
            self.logger.warning(f"로비 페이지 확인 중 오류: {e}")
            return False
        
    def _switch_to_lobby_window(self, window_handles):
        """로비 창으로 전환 (메소드 추출)"""
        try:
            # 로비 창으로 전환 (일반적으로 두 번째 창)
            if len(window_handles) >= 2:
                self.devtools.driver.switch_to.window(window_handles[1])
                self.logger.info("카지노 로비 창으로 포커싱 전환 완료")
                return True
            elif len(window_handles) == 1:
                # 창이 하나만 있으면 그 창을 사용
                self.devtools.driver.switch_to.window(window_handles[0])
                self.logger.info("단일 창으로 포커싱 전환")
                return True
            else:
                self.logger.warning("열린 창이 없습니다.")
                return False
        except Exception as e:
            self.logger.error(f"창 전환 실패: {e}")
            return False