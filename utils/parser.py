from bs4 import BeautifulSoup
import re

class HTMLParser:
    def __init__(self, html):
        self.soup = BeautifulSoup(html, "html.parser")

    def get_balance(self):
        """잔액 정보 추출"""
        balance_element = self.soup.find("span", class_="balance")  # 클래스명은 실제 HTML 구조에 맞게 변경
        if not balance_element:
            balance_element = self.soup.find("div", class_="user-balance")  # 예비 탐색
        
        if balance_element:
            balance_text = balance_element.text.strip()
            balance = re.sub(r"[^\d]", "", balance_text)  # 숫자만 추출 (₩, $, , 제거)
            return int(balance) if balance.isdigit() else 0
        
        return None  # 잔액을 찾을 수 없는 경우
