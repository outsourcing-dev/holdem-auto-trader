# utils/target_amount_checker.py
from PyQt6.QtWidgets import QMessageBox
from utils.settings_manager import SettingsManager
import logging

class TargetAmountChecker:
    def __init__(self, main_window):
        self.main_window = main_window
        self.settings_manager = SettingsManager()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
    # utils/target_amount_checker.py의 check_target_amount 메서드 수정
    def check_target_amount(self, current_amount, source="일반"):
        """
        현재 금액이 목표 금액에 도달했는지 확인하고, 도달했으면 자동 매매를 중지합니다.
        
        Args:
            current_amount (int): 현재 금액
            source (str): 호출 출처 (로깅용)
                
        Returns:
            bool: 목표 금액 도달 여부
        """
        # 자동 매매가 활성화된 상태가 아니면 확인 불필요
        if not hasattr(self.main_window, 'trading_manager') or not self.main_window.trading_manager.is_trading_active:
            return False
                
        # 목표 금액 가져오기
        target_amount = self.settings_manager.get_target_amount()
            
        # 목표 금액이 설정되어 있지 않으면 확인 불필요
        if target_amount <= 0:
            return False
                
        # 현재 금액이 목표 금액에 도달했는지 확인
        if current_amount >= target_amount:
            self.logger.info(f"[{source}] 목표 금액({target_amount:,}원)에 도달! 현재 금액: {current_amount:,}원")
                
            # 메시지 박스 표시
            QMessageBox.information(
                self.main_window, 
                "목표 금액 달성", 
                f"축하합니다! 목표 금액({target_amount:,}원)에 도달했습니다.\n현재 금액: {current_amount:,}원\n자동 매매를 종료합니다."
            )
                
            # 자동 매매 중지 (이 함수에서 방 나가기와 로비로 돌아가기가 수행됨)
            self.main_window.trading_manager.stop_trading()
            return True
                
        return False