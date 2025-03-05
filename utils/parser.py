from bs4 import BeautifulSoup
import re

class HTMLParser:
    def __init__(self, html):
        self.soup = BeautifulSoup(html, "html.parser")

    def get_balance(self):
        """잔액 정보 추출"""

        # 1️⃣ 기존 방식: 특정 클래스명을 가진 요소에서 잔액 찾기
        balance_element = self.soup.find("span", class_="balance")  
        if not balance_element:
            balance_element = self.soup.find("div", class_="user-balance") 
        
        if balance_element:
            balance_text = balance_element.text.strip()
            balance = re.sub(r"[^\d]", "", balance_text)  # 숫자만 추출
            if balance.isdigit():
                return int(balance)

        # 2️⃣ 새로운 방식: 1번 사이트의 "캐쉬 :" 부분에서 잔액 찾기
        nav_link = self.soup.find("a", class_="nav-link", href="#ModalDeposit")
        if nav_link:
            strong_tag = nav_link.find("strong", class_="fontcolor_yellow")
            if strong_tag:
                balance_text = strong_tag.text.strip()
                balance = re.sub(r"[^\d]", "", balance_text)  # 숫자만 추출
                if balance.isdigit():
                    return int(balance)

        # 3️⃣ 정규식 방식: "캐쉬 : 숫자" 패턴 찾기
        cash_pattern = re.search(r"캐쉬\s*:\s*([\d,]+)", self.soup.text)
        if cash_pattern:
            balance_text = cash_pattern.group(1)
            balance = re.sub(r"[^\d]", "", balance_text)  # 숫자만 추출
            if balance.isdigit():
                return int(balance)

        return None  # 잔액을 찾을 수 없는 경우
        
    def get_username(self):
        """사용자 이름 추출"""
        
        # 1️⃣ 기존 방식: 특정 클래스명을 가진 요소에서 사용자 이름 찾기
        username_element = self.soup.find("span", class_="username")
        if username_element:
            return username_element.text.strip()
            
        # 2️⃣ 1번 사이트의 "회원님 환영합니다!" 부분에서 사용자 이름 찾기
        try:
            welcome_text = self.soup.find(text=lambda text: "회원님 환영합니다" in str(text) if text else False)
            if welcome_text:
                welcome_element = welcome_text.parent
                strong_tag = welcome_element.find("strong")
                if strong_tag:
                    return strong_tag.text.strip()
        except:
            pass
            
        # 3️⃣ 정규식 방식: 사용자 이름 찾기 패턴
        username_pattern = re.search(r"<strong>([^<]+)</strong>\s*회원님\s*환영합니다", str(self.soup))
        if username_pattern:
            return username_pattern.group(1).strip()
            
        return None  # 사용자 이름을 찾을 수 없는 경우
    
class CasinoParser:
    """카지노 페이지 파싱을 위한 클래스"""
    
    def __init__(self, html):
        self.soup = BeautifulSoup(html, "html.parser")
        
    def get_room_name(self):
        """현재 방 이름 파싱"""
        # 예: 클래스, ID 또는 특정 요소 구조를 기반으로 방 이름 찾기
        room_element = self.soup.find(class_="room-name")
        if room_element:
            return room_element.text.strip()
            
        # 다른 방식으로 시도
        title_element = self.soup.find("title")
        if title_element:
            title_text = title_element.text.strip()
            # 제목에서 방 이름 추출 (예: "바카라 A - Live Casino")
            match = re.search(r"(.+?)(?:\s*-\s*|$)", title_text)
            if match:
                return match.group(1).strip()
                
        return "알 수 없는 방"
        
    def get_game_status(self):
        """현재 게임 상태 파싱 (대기 중, 베팅 중, 결과 발표 등)"""
        # 예시 - 실제 구현은 사이트 구조에 따라 조정 필요
        status_element = self.soup.find(class_="game-status")
        if status_element:
            return status_element.text.strip()
        return None
        
    def get_betting_options(self):
        """사용 가능한 베팅 옵션 파싱 (예: Player, Banker, Tie)"""
        options = []
        # 베팅 옵션 요소 찾기 (실제 구현은 사이트 구조에 따라 조정 필요)
        option_elements = self.soup.find_all(class_="betting-option")
        for element in option_elements:
            option_name = element.get("data-name", element.text.strip())
            options.append(option_name)
        return options
        
    def get_last_results(self):
        """최근 게임 결과 파싱 (예: 최근 10판의 결과)"""
        results = []
        # 결과 요소 찾기 (실제 구현은 사이트 구조에 따라 조정 필요)
        result_elements = self.soup.find_all(class_="game-result")
        for element in result_elements:
            result_text = element.text.strip()
            result_class = element.get("class", [])
            
            # 클래스 이름으로 Player/Banker/Tie 구분 예시
            if "player-win" in result_class:
                result = "P"
            elif "banker-win" in result_class:
                result = "B"
            elif "tie" in result_class:
                result = "T"
            else:
                result = result_text
                
            results.append(result)
        return results
        
    def get_current_bet_amounts(self):
        """현재 베팅 금액 파싱 (각 옵션별)"""
        bet_amounts = {}
        # 베팅 금액 요소 찾기 (실제 구현은 사이트 구조에 따라 조정 필요)
        amount_elements = self.soup.find_all(class_="bet-amount")
        for element in amount_elements:
            option_name = element.get("data-option", "unknown")
            amount_text = element.text.strip()
            amount = re.sub(r"[^\d]", "", amount_text)  # 숫자만 추출
            if amount.isdigit():
                bet_amounts[option_name] = int(amount)
        return bet_amounts

# 메인 윈도우 클래스에 코드 추가 예시
def parse_casino_page(self):
    """카지노 페이지 파싱 및 정보 추출"""
    if not self.devtools.driver:
        print("[ERROR] 브라우저가 실행되지 않음")
        return None
        
    try:
        html = self.devtools.get_page_source()
        if not html:
            print("[ERROR] 페이지 소스를 가져올 수 없음")
            return None
            
        parser = CasinoParser(html)
        
        # 정보 추출
        room_name = parser.get_room_name()
        game_status = parser.get_game_status()
        betting_options = parser.get_betting_options()
        last_results = parser.get_last_results()
        bet_amounts = parser.get_current_bet_amounts()
        
        # 결과 출력
        print(f"[INFO] 방 이름: {room_name}")
        print(f"[INFO] 게임 상태: {game_status}")
        print(f"[INFO] 베팅 옵션: {betting_options}")
        print(f"[INFO] 최근 결과: {last_results}")
        print(f"[INFO] 베팅 금액: {bet_amounts}")
        
        # UI 업데이트
        self.update_betting_status(room_name=room_name)
        
        return {
            "room_name": room_name,
            "game_status": game_status,
            "betting_options": betting_options,
            "last_results": last_results,
            "bet_amounts": bet_amounts
        }
        
    except Exception as e:
        print(f"[ERROR] 카지노 페이지 파싱 중 오류 발생: {e}")
        return None