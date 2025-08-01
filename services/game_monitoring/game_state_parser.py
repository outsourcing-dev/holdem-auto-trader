"""
게임 상태 파싱 전용 모듈
game_monitoring_service.py에서 분리된 게임 상태 관련 로직
"""
import logging
from selenium.webdriver.common.by import By
from utils.common_iframe import IframeNavigator


class GameStateParser:
    """게임 상태 파싱 전담 클래스"""
    
    def __init__(self, devtools, logger=None):
        self.devtools = devtools
        self.logger = logger or logging.getLogger(__name__)
        
        # iframe 네비게이터 안전한 초기화
        try:
            if devtools and devtools.driver:
                self.iframe_navigator = IframeNavigator(devtools.driver, self.logger)
            else:
                self.logger.warning("GameStateParser: driver가 None - iframe 네비게이터 없이 초기화")
                self.iframe_navigator = None
        except Exception as e:
            self.logger.error(f"GameStateParser iframe 네비게이터 초기화 실패: {e}")
            self.iframe_navigator = None
    
    def parse_game_results_from_iframe(self, desired_count=None):
        """iframe에서 게임 결과 파싱"""
        try:
            # 게임 테이블 찾기
            game_tables = self.devtools.driver.find_elements(By.CSS_SELECTOR, 
                "table, .game-table, .result-table, [class*='table'], [class*='result']")
            
            if not game_tables:
                self.logger.warning("게임 테이블을 찾을 수 없음")
                return None
            
            # 첫 번째 테이블에서 결과 파싱
            table = game_tables[0]
            return self._extract_game_results(table, desired_count)
            
        except Exception as e:
            self.logger.error(f"게임 결과 파싱 중 오류: {e}")
            return None
    
    def _extract_game_results(self, table, desired_count):
        """테이블에서 게임 결과 추출"""
        try:
            results = []
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:  # 최소 2개 셀이 있어야 함
                    # 게임 결과 추출 로직
                    result_text = cells[1].text.strip() if len(cells) > 1 else cells[0].text.strip()
                    if result_text and result_text in ['P', 'B', 'T']:
                        results.append({
                            'result': result_text,
                            'round': len(results) + 1
                        })
            
            # 원하는 개수만큼 자르기
            if desired_count and len(results) > desired_count:
                results = results[-desired_count:]
            
            return {
                'results': results,
                'total_count': len(results),
                'last_result': results[-1]['result'] if results else None
            }
            
        except Exception as e:
            self.logger.error(f"게임 결과 추출 중 오류: {e}")
            return None
    
    def get_current_round_info(self):
        """현재 라운드 정보 추출"""
        try:
            # 라운드 정보 요소 찾기
            round_element = self.iframe_navigator.get_cached_element(
                By.CSS_SELECTOR, 
                ".round-info, .game-round, [class*='round']"
            )
            
            if round_element:
                round_text = round_element.text.strip()
                # 숫자 추출
                import re
                round_match = re.search(r'(\d+)', round_text)
                if round_match:
                    return int(round_match.group(1))
            
            return None
            
        except Exception as e:
            self.logger.error(f"라운드 정보 추출 중 오류: {e}")
            return None
    
    def get_game_balance(self):
        """게임 잔액 정보 추출"""
        try:
            balance_element = self.iframe_navigator.get_cached_element(
                By.CSS_SELECTOR,
                ".balance, .money, [class*='balance'], [class*='money']"
            )
            
            if balance_element:
                balance_text = balance_element.text.strip()
                # 숫자만 추출
                import re
                balance_match = re.search(r'[\d,]+', balance_text.replace(',', ''))
                if balance_match:
                    return int(balance_match.group().replace(',', ''))
            
            return None
            
        except Exception as e:
            self.logger.error(f"잔액 정보 추출 중 오류: {e}")
            return None