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
