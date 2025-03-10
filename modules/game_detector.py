# modules/game_detector.py
"""
게임 상태 감지 및 결과 추적 모듈
"""
from bs4 import BeautifulSoup
import re

class GameDetector:
    def __init__(self):
        self.current_round = 0  # 현재 게임 판수
        self.pb_history = []  # P/B 기록 (T 제외)
        self.all_results = []  # P/B/T 모든 결과 기록

    def parse_game_board(self, html_content):
        """
        게임 결과 보드를 파싱합니다.
        
        Args:
            html_content (str): HTML 소스 코드
                
        Returns:
            dict: 게임 정보 (판수, 최신 결과 등)
        """
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 게임 결과 보드 찾기
        bead_road = soup.find("svg", attrs={"data-role": "Bead-road"})
        if not bead_road:
            return {
                "game_count": 0,
                "latest_result": None,
                "recent_results": []
            }
            
        # 좌표 요소 찾기
        coord_elements = bead_road.find_all("svg", attrs={"data-type": "coordinates"})
        results = []
        
        # Y축 길이 (한 열에 몇 개의 결과가 들어가는지)
        Y_MAX = 6  # 기본값, 실제 값으로 조정 필요
        
        for element in coord_elements:
            try:
                # x, y 좌표 추출
                x = int(element.get("data-x", 0))
                y = int(element.get("data-y", 0))
                
                # 게임 번호 계산 (y축으로 먼저 채우고, 다음 x축으로 이동)
                game_number = x * Y_MAX + y + 1
                
                # 결과 유형 파싱 - HTML 소스에서 직접 확인
                result_type = "unknown"
                
                # 요소 내용에 <text> 태그 내용 찾기
                element_str = str(element)
                
                # 정규식으로 <text> 태그 내용 추출 시도
                text_match = re.search(r'<text[^>]*>([^<]+)</text>', element_str)
                
                if text_match:
                    # <text> 태그 내용 직접 사용
                    text_content = text_match.group(1).strip()
                    if text_content == "P":
                        result_type = "P"
                    elif text_content == "B":
                        result_type = "B"
                    elif text_content == "T":
                        result_type = "T"
                else:
                    # <text> 태그를 찾지 못한 경우 기존 방식으로 백업
                    name_match = re.search(r'name="([^"]+)"', element_str)
                    if name_match:
                        item_name = name_match.group(1).lower()
                        if "tie" in item_name:
                            result_type = "T"
                        elif "player" in item_name:
                            result_type = "P"
                        elif "banker" in item_name:
                            result_type = "B"
                
                results.append((x, y, result_type, game_number))
                
            except Exception as e:
                print(f"결과 파싱 중 오류: {e}")
        
        # 게임 번호 기준으로 정렬
        results.sort(key=lambda r: r[3])
        
        # 게임 수
        game_count = len(results)
        
        if not results:
            return {
                "game_count": 0,
                "latest_result": None,
                "recent_results": []
            }
            
        # 최신 결과 및 최근 결과 목록
        latest_result = results[-1]
        recent_results = [r[2] for r in results]  # 모든 결과 가져오기
        
        # 게임 번호와 결과 매핑 (디버깅용)
        game_results = [(r[3], r[2]) for r in results]
        
        return {
            "game_count": game_count,
            "latest_result": latest_result,
            "recent_results": recent_results,
            "game_results": game_results
        }
        
    def detect_game_state(self, html_content):
        """
        현재 게임 상태를 감지합니다.
        
        Args:
            html_content (str): HTML 소스 코드
                
        Returns:
            dict: 게임 상태 정보
        """
        game_info = self.parse_game_board(html_content)
        
        # 게임 수 업데이트
        self.current_round = game_info["game_count"]
        
        # 최신 결과 추출
        latest_result = game_info["latest_result"]
        latest_result_type = latest_result[2] if latest_result else None
        
        # 배팅 가능 상태 확인 (여기서는 간단하게 결과가 있으면 배팅 가능으로 가정)
        betting_available = self.current_round > 0
        
        # 최신 결과가 있으면 기록
        if latest_result_type and latest_result_type not in self.all_results:
            self.all_results.append(latest_result_type)
            if latest_result_type in ['P', 'B']:
                self.pb_history.append(latest_result_type)
        
        # 최근 결과 가져오기
        recent_results = game_info["recent_results"] if game_info["recent_results"] else []
        
        # TIE를 제외한 결과를 정확히 10개 얻기 위한 처리
        desired_pb_count = 10  # P와 B를 합쳐 10개 필요
        
        # 결과에서 TIE를 제외한 P/B만의 결과 필터링
        filtered_results = []
        
        # 뒤에서부터(최신 결과부터) 개수 세기 - TIE 완전히 제외
        for result in reversed(recent_results):
            if result in ['P', 'B']:
                filtered_results.insert(0, result)  # 최신 결과를 앞에 추가
            
            # TIE 제외 결과가 10개면 충분
            if len(filtered_results) >= desired_pb_count:
                break
        
        # 최신 게임의 좌표 정보
        latest_coords = None
        if latest_result:
            latest_coords = (latest_result[0], latest_result[1])
        
        return {
            'round': self.current_round,
            'betting_available': betting_available,
            'latest_result': latest_result_type,
            'latest_game_coords': latest_coords,
            'recent_results': recent_results,             # 모든 결과(TIE 포함)
            'filtered_results': filtered_results,         # TIE를 제외한 결과 (최대 10개)
            'game_results': game_info.get("game_results", [])  # 게임 번호별 결과
        }
        
    def record_pb(self, result):
        """
        P(플레이어) 또는 B(뱅커)만 기록 (T 제외)
        
        Args:
            result (str): 게임 결과 ('P', 'B', 'T' 중 하나)
        """
        if result in ['P', 'B']:
            self.pb_history.append(result)
            
        # 모든 결과는 항상 기록
        self.all_results.append(result)
        
    def get_streak(self, result_type='P'):
        """
        특정 결과의 연속 횟수를 확인합니다.
        
        Args:
            result_type (str): 확인할 결과 타입 ('P' 또는 'B')
            
        Returns:
            int: 연속 횟수
        """
        if not self.pb_history:
            return 0
            
        count = 0
        for result in reversed(self.pb_history):
            if result == result_type:
                count += 1
            else:
                break
        return count
        
    def get_win_rate(self, last_n=0):
        """
        최근 N판의 승률을 계산합니다.
        
        Args:
            last_n (int): 확인할 최근 게임 수 (0이면 전체)
            
        Returns:
            float: 승률 (0.0 ~ 1.0)
        """
        if not self.pb_history:
            return 0.0
            
        history = self.pb_history[-last_n:] if last_n > 0 else self.pb_history
        if not history:
            return 0.0
            
        p_count = history.count('P')
        return p_count / len(history)