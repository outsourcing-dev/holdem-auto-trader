"""
Evolution Gaming iframe 내용을 로깅하는 서비스
Playwright를 사용하여 게임 상태와 베팅 정보를 캡처
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from playwright.sync_api import sync_playwright, Page, Browser
import asyncio


class IframeLogger:
    """Evolution Gaming iframe 내용을 로깅하는 서비스"""
    
    def __init__(self, logger=None):
        """초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.playwright = None
        self.browser = None
        self.page = None
        self.log_dir = Path("betting_logs")
        self.log_dir.mkdir(exist_ok=True)
        self.current_log_file = None
        self.is_logging = False
        
    def start_logging(self, devtools_url: Optional[str] = None):
        """로깅 시작"""
        try:
            self.logger.info("🎬 iframe 로깅 시작")
            
            # 로그 파일 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_log_file = self.log_dir / f"betting_log_{timestamp}.txt"
            
            # 초기 로그 작성
            with open(self.current_log_file, "w", encoding="utf-8") as f:
                f.write(f"=== Evolution Gaming Betting Log ===\n")
                f.write(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*50}\n\n")
            
            self.is_logging = True
            self.logger.info(f"📝 로그 파일 생성: {self.current_log_file}")
            
            # Playwright 연결 (기존 브라우저 사용)
            if devtools_url:
                self._connect_to_browser(devtools_url)
            
        except Exception as e:
            self.logger.error(f"iframe 로깅 시작 실패: {e}")
            
    def _connect_to_browser(self, devtools_url: str):
        """기존 브라우저에 연결"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(devtools_url)
            contexts = self.browser.contexts
            if contexts:
                self.page = contexts[0].pages[0] if contexts[0].pages else None
                self.logger.info("✅ 브라우저 연결 성공")
        except Exception as e:
            self.logger.error(f"브라우저 연결 실패: {e}")
            
    def log_iframe_content(self, game_state: Dict[str, Any], betting_info: Optional[Dict] = None):
        """iframe 내용을 파일에 로깅"""
        if not self.is_logging or not self.current_log_file:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            with open(self.current_log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{timestamp}] Game State Update\n")
                f.write("-" * 40 + "\n")
                
                # 게임 상태 정보
                f.write("Game State:\n")
                f.write(f"  Round: {game_state.get('round', 'N/A')}\n")
                f.write(f"  Current Game: {game_state.get('current_game', 'N/A')}\n")
                f.write(f"  Total Results: {game_state.get('total_results', 0)}\n")
                f.write(f"  Latest Result: {game_state.get('latest_result', 'N/A')}\n")
                
                # 결과 히스토리
                if 'filtered_results' in game_state:
                    results = game_state['filtered_results']
                    f.write(f"  Result History ({len(results)}): ")
                    if len(results) <= 20:
                        f.write(''.join(results))
                    else:
                        f.write(''.join(results[-20:]) + f" (showing last 20 of {len(results)})")
                    f.write("\n")
                
                # 베팅 정보
                if betting_info:
                    f.write("\nBetting Info:\n")
                    f.write(f"  Pick: {betting_info.get('pick', 'N/A')}\n")
                    f.write(f"  Amount: {betting_info.get('amount', 'N/A')}\n")
                    f.write(f"  Round: {betting_info.get('betting_round', 'N/A')}\n")
                    f.write(f"  Martin Step: {betting_info.get('martin_step', 'N/A')}\n")
                    f.write(f"  Room: {betting_info.get('room_name', 'N/A')}\n")
                
                # iframe JavaScript 정보 수집 (Playwright 사용)
                if self.page:
                    self._log_iframe_javascript(f)
                    
                f.write("-" * 40 + "\n")
                
        except Exception as e:
            self.logger.error(f"iframe 로깅 중 오류: {e}")
            
    def _log_iframe_javascript(self, file_handle):
        """iframe 내 JavaScript 정보 수집"""
        try:
            # iframe 찾기
            iframe_element = self.page.query_selector("iframe#game-iframe")
            if not iframe_element:
                return
                
            # iframe 내부 접근
            frame = iframe_element.content_frame()
            if not frame:
                return
                
            # JavaScript 실행하여 게임 정보 수집
            game_info = frame.evaluate("""
                () => {
                    const info = {};
                    
                    // 게임 테이블 정보
                    const gameTable = document.querySelector('.game-table');
                    if (gameTable) {
                        info.tableId = gameTable.getAttribute('data-table-id') || 'N/A';
                    }
                    
                    // 베팅 칩 정보
                    const chips = document.querySelectorAll('.chip-stack');
                    info.chipCount = chips.length;
                    
                    // 타이머 정보
                    const timer = document.querySelector('.betting-timer');
                    if (timer) {
                        info.timer = timer.textContent || 'N/A';
                    }
                    
                    // 결과 보드
                    const resultBoard = document.querySelector('.result-board');
                    if (resultBoard) {
                        const results = [];
                        resultBoard.querySelectorAll('.result-item').forEach(item => {
                            results.push(item.textContent);
                        });
                        info.resultBoard = results.slice(0, 10); // 최근 10개
                    }
                    
                    // 통계 정보
                    const stats = document.querySelector('.game-statistics');
                    if (stats) {
                        info.statistics = {
                            player: stats.querySelector('.player-wins')?.textContent || '0',
                            banker: stats.querySelector('.banker-wins')?.textContent || '0',
                            tie: stats.querySelector('.tie-wins')?.textContent || '0'
                        };
                    }
                    
                    return info;
                }
            """)
            
            if game_info:
                file_handle.write("\niframe JavaScript Info:\n")
                file_handle.write(f"  Table ID: {game_info.get('tableId', 'N/A')}\n")
                file_handle.write(f"  Chip Count: {game_info.get('chipCount', 0)}\n")
                file_handle.write(f"  Timer: {game_info.get('timer', 'N/A')}\n")
                
                if 'resultBoard' in game_info:
                    file_handle.write(f"  Result Board: {', '.join(game_info['resultBoard'])}\n")
                    
                if 'statistics' in game_info:
                    stats = game_info['statistics']
                    file_handle.write(f"  Statistics: P={stats['player']}, B={stats['banker']}, T={stats['tie']}\n")
                    
        except Exception as e:
            self.logger.debug(f"iframe JavaScript 정보 수집 실패: {e}")
            
    def log_betting_action(self, action: str, details: Dict[str, Any]):
        """베팅 액션 로깅"""
        if not self.is_logging or not self.current_log_file:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            with open(self.current_log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{timestamp}] Betting Action: {action}\n")
                f.write(json.dumps(details, indent=2, ensure_ascii=False))
                f.write("\n")
                
        except Exception as e:
            self.logger.error(f"베팅 액션 로깅 실패: {e}")
            
    def capture_iframe_snapshot(self):
        """iframe 스냅샷 캡처 (스크린샷 + DOM)"""
        if not self.is_logging or not self.page:
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 스크린샷 저장
            screenshot_path = self.log_dir / f"snapshot_{timestamp}.png"
            iframe_element = self.page.query_selector("iframe#game-iframe")
            if iframe_element:
                iframe_element.screenshot(path=str(screenshot_path))
                self.logger.info(f"📸 스크린샷 저장: {screenshot_path}")
                
            # DOM 구조 저장
            dom_path = self.log_dir / f"dom_{timestamp}.html"
            if iframe_element:
                frame = iframe_element.content_frame()
                if frame:
                    html_content = frame.content()
                    with open(dom_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    self.logger.info(f"📄 DOM 저장: {dom_path}")
                    
        except Exception as e:
            self.logger.error(f"iframe 스냅샷 캡처 실패: {e}")
            
    def stop_logging(self):
        """로깅 중지"""
        try:
            if self.is_logging and self.current_log_file:
                # 종료 로그 작성
                with open(self.current_log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*50}\n")
                    f.write(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"=== End of Log ===\n")
                    
                self.logger.info(f"📝 로그 파일 저장 완료: {self.current_log_file}")
                
            self.is_logging = False
            
            # Playwright 정리
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
                
        except Exception as e:
            self.logger.error(f"iframe 로깅 중지 실패: {e}")
            
    def get_log_file_path(self) -> Optional[Path]:
        """현재 로그 파일 경로 반환"""
        return self.current_log_file if self.is_logging else None