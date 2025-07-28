# modules/game_detector.py - 대폭 단순화된 버전
"""
게임 상태 감지 모듈 - 서버 기반으로 단순화
복잡한 분석은 서버에서 처리하고, 기본적인 상태 확인만 담당
"""
import logging
from bs4 import BeautifulSoup

class GameDetector:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 기본 상태 변수만 유지
        self.current_round = 0
        
        # 복잡한 분석 관련 변수들 제거
        # self.pb_history = []  # 제거됨
        # self.all_results = []  # 제거됨  
        # self.results = []  # 제거됨
        
        self.reset()

    def reset(self):
        """게임 감지기 상태 초기화 - 단순화"""
        self.current_round = 0
        self._last_processed_game = None
        self._last_processed_result = None
        
    def detect_game_state(self, html_content, desired_pb_count=15):
        """
        현재 게임 상태를 감지합니다 - 단순화된 버전
        복잡한 분석은 서버에서 처리하므로 기본적인 상태만 확인
        
        Args:
            html_content (str): HTML 소스 코드
            desired_pb_count (int): 호환성을 위해 유지 (사용하지 않음)
                
        Returns:
            dict: 기본적인 게임 상태 정보만 반환
        """
        try:
            # 기본적인 게임 정보만 파싱
            game_info = self._parse_basic_game_info(html_content)
            
            # 게임 수 업데이트
            self.current_round = game_info["game_count"]
            
            # 베팅 가능 상태 확인 (간단한 로직만)
            betting_available = self._check_betting_available(html_content)
            
            return {
                'round': self.current_round,
                'betting_available': betting_available,
                'latest_result': game_info.get("latest_result"),
                'latest_game_coords': game_info.get("latest_coords"),
                'recent_results': [],  # 서버에서 처리하므로 빈 배열
                'filtered_results': [],  # 서버에서 처리하므로 빈 배열
                'game_results': []  # 서버에서 처리하므로 빈 배열
            }
            
        except Exception as e:
            self.logger.error(f"게임 상태 감지 오류: {e}")
            return {
                'round': 0,
                'betting_available': False,
                'latest_result': None,
                'latest_game_coords': None,
                'recent_results': [],
                'filtered_results': [],
                'game_results': []
            }

    def _parse_basic_game_info(self, html_content):
        """기본적인 게임 정보만 파싱 - 대폭 단순화"""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            
            # 게임 결과 보드 찾기 (기본적인 정보만)
            bead_road = soup.find("svg", attrs={"data-role": "Bead-road"})
            if not bead_road:
                return {"game_count": 0, "latest_result": None, "latest_coords": None}
                
            # 좌표 요소 개수만 확인 (복잡한 분석 제거)
            coord_elements = bead_road.find_all("svg", attrs={"data-type": "coordinates"})
            game_count = len(coord_elements)
            
            # 최신 결과만 간단히 확인
            latest_result = None
            latest_coords = None
            
            if coord_elements:
                try:
                    last_element = coord_elements[-1]
                    x = int(last_element.get("data-x", 0))
                    y = int(last_element.get("data-y", 0))
                    latest_coords = (x, y)
                    
                    # 간단한 결과 타입 확인
                    element_str = str(last_element)
                    if '"P"' in element_str or '>P<' in element_str:
                        latest_result = "P"
                    elif '"B"' in element_str or '>B<' in element_str:
                        latest_result = "B"
                    elif '"T"' in element_str or '>T<' in element_str:
                        latest_result = "T"
                        
                except Exception as e:
                    self.logger.warning(f"최신 결과 파싱 오류: {e}")
            
            return {
                "game_count": game_count,
                "latest_result": latest_result,
                "latest_coords": latest_coords
            }
            
        except Exception as e:
            self.logger.error(f"기본 게임 정보 파싱 오류: {e}")
            return {"game_count": 0, "latest_result": None, "latest_coords": None}

    def _check_betting_available(self, html_content):
        """베팅 가능 상태 확인 - 단순화"""
        try:
            # 간단한 키워드 기반 확인
            html_lower = html_content.lower()
            
            # 베팅 불가능한 상태 키워드들
            if any(keyword in html_lower for keyword in [
                'dealing', 'no more bets', 'game closed', 'round finished'
            ]):
                return False
                
            # 베팅 가능한 상태로 기본 추정
            return True
            
        except Exception as e:
            self.logger.warning(f"베팅 상태 확인 오류: {e}")
            return False