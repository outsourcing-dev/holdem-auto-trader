# modules/game_board_parser.py
"""
게임 결과 보드를 파싱하여 현재 게임 수와 결과를 얻는 모듈
"""
from bs4 import BeautifulSoup
import re

class GameBoardParser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, "html.parser")
        
    def parse_game_results(self):
        """
        게임 결과 보드를 파싱하여 좌표와 결과 값을 반환합니다.
        
        Returns:
            list: [(x, y, result_type), ...] 형태의 게임 결과 목록
        """
        results = []
        
        # SVG 내부의 좌표 데이터 검색
        bead_road = self.soup.find("svg", attrs={"data-role": "Bead-road"})
        if not bead_road:
            return results
            
        # 각 결과 좌표 요소 검색
        coord_elements = bead_road.find_all("svg", attrs={"data-type": "coordinates"})
        
        for element in coord_elements:
            try:
                # x, y 좌표 추출
                x = int(element.get("data-x", 0))
                y = int(element.get("data-y", 0))
                
                # 결과 유형 추출 (색상 또는 다른 속성으로 판단)
                # 여기서는 간단하게 클래스 이름으로 구분한다고 가정
                result_type = "unknown"
                if "player" in element.get("class", []):
                    result_type = "P"
                elif "banker" in element.get("class", []):
                    result_type = "B"
                elif "tie" in element.get("class", []):
                    result_type = "T"
                    
                results.append((x, y, result_type))
            except Exception as e:
                print(f"결과 파싱 중 오류: {e}")
                
        return results
    
    def get_current_game_count(self):
        """
        현재까지 진행된 게임 수를 계산합니다.
        
        Returns:
            int: 총 게임 수
        """
        results = self.parse_game_results()
        
        if not results:
            return 0
            
        # 단순히 결과 개수로 계산
        return len(results)
    
    def get_latest_result(self):
        """
        가장 최근 게임 결과를 가져옵니다.
        
        Returns:
            tuple: (x, y, result_type) 또는 None
        """
        results = self.parse_game_results()
        
        if not results:
            return None
            
        # 가장 마지막 결과 반환
        return results[-1]
    
    def get_result_sequence(self, count=15):
        """
        최근 N개의 게임 결과 시퀀스를 가져옵니다.
        
        Args:
            count (int): 가져올 결과 개수
            
        Returns:
            list: 최근 게임의 결과 목록 (P, B, T)
        """
        results = self.parse_game_results()
        
        if not results:
            return []
            
        # 결과 목록에서 타입만 추출하여 최신 순으로 반환
        result_types = [r[2] for r in results]
        return result_types[-count:]