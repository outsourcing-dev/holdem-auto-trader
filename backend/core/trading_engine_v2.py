"""
트레이딩 엔진 V2 - Selenium 기반 실제 베팅
"""
import logging
import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime

from core.selenium_controller import SeleniumController
from core.betting_executor import BettingExecutor
from services.martin_strategy import MartinStrategy
from services.prediction_client import PredictionClient
from api.websocket import WebSocketManager

logger = logging.getLogger(__name__)

class TradingEngineV2:
    """Selenium 기반 트레이딩 엔진"""
    
    def __init__(self, username: str):
        self.username = username
        self.selenium = SeleniumController()
        self.betting = None  # 브라우저 시작 후 초기화
        self.martin_strategy = MartinStrategy()
        self.prediction_client = PredictionClient()
        
        # 상태 변수
        self.is_active = False
        self.current_room = None
        self.game_count = 0
        self.total_bet_amount = 0
        self.current_balance = None
        self.martin_step = 0
        self.consecutive_losses = 0
        
        # 통계
        self.statistics = {
            "total_games": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "total_profit": 0,
            "current_streak": 0
        }
        
        # 제어 플래그
        self._stop_requested = False
        
    async def start_trading(self, site_url: str, min_streak: int, websocket_manager: WebSocketManager):
        """트레이딩 시작"""
        try:
            self.is_active = True
            self._stop_requested = False
            
            # URL 정리
            if not site_url.startswith('http'):
                site_url = f'https://{site_url}'
            
            logger.info(f"트레이딩 시작: {self.username}, URL: {site_url}")
            
            # 브라우저 시작
            if not self.selenium.start_browser(site_url):
                raise Exception("브라우저 시작 실패")
            
            # BettingExecutor 초기화
            self.betting = BettingExecutor(self.selenium.driver)
            
            # WebSocket 상태 전송
            await websocket_manager.send_status_update(self.username, {
                "status": "started",
                "message": "브라우저를 시작했습니다. Evolution 게임에 접속해주세요."
            })
            
            # Evolution iframe 대기
            await self.wait_for_evolution_iframe(websocket_manager)
            
            # 메인 트레이딩 루프
            await self.main_trading_loop(min_streak, websocket_manager)
            
        except Exception as e:
            logger.error(f"트레이딩 시작 오류: {e}")
            await websocket_manager.send_status_update(self.username, {
                "status": "error",
                "message": f"트레이딩 오류: {str(e)}"
            })
        finally:
            await self.stop_trading()
    
    async def wait_for_evolution_iframe(self, websocket_manager: WebSocketManager):
        """Evolution iframe 대기"""
        check_count = 0
        
        while self.is_active and not self._stop_requested:
            check_count += 1
            
            # iframe 찾기 시도
            if self.selenium.find_evolution_iframe():
                logger.info("✅ Evolution iframe 감지됨!")
                await websocket_manager.send_status_update(self.username, {
                    "status": "evolution_detected",
                    "message": "Evolution 게임을 감지했습니다. 트레이딩을 시작합니다."
                })
                return True
            
            # 5초마다 상태 업데이트
            if check_count % 5 == 0:
                await websocket_manager.send_status_update(self.username, {
                    "status": "waiting_evolution",
                    "message": f"Evolution 게임 감지 대기 중... ({check_count}초)"
                })
            
            await asyncio.sleep(1)
            
            # 1분 이상 대기하면 경고
            if check_count > 60:
                logger.warning("Evolution iframe을 1분 이상 감지하지 못했습니다")
                await websocket_manager.send_status_update(self.username, {
                    "status": "warning",
                    "message": "Evolution 게임을 감지하지 못했습니다. 게임에 접속해주세요."
                })
                check_count = 0  # 리셋하고 계속 대기
    
    async def main_trading_loop(self, min_streak: int, websocket_manager: WebSocketManager):
        """메인 트레이딩 루프"""
        while self.is_active and not self._stop_requested:
            try:
                # 1. 연패방 찾기
                streak_room = await self.find_streak_room(min_streak)
                if not streak_room:
                    await asyncio.sleep(5)
                    continue
                
                # 2. 방 입장
                if not self.selenium.enter_room(streak_room):
                    logger.warning(f"방 입장 실패: {streak_room}")
                    await asyncio.sleep(5)
                    continue
                
                self.current_room = streak_room
                await websocket_manager.send_room_change(self.username, {
                    "room": streak_room,
                    "time": datetime.now().isoformat()
                })
                
                # 3. 게임 플레이
                result = await self.play_in_room(websocket_manager)
                
                # 4. 결과 처리
                if result == "WIN":
                    # 승리 - 다른 방 찾기
                    self.martin_step = 0
                    self.consecutive_losses = 0
                    await websocket_manager.send_status_update(self.username, {
                        "status": "win",
                        "message": f"승리! 다른 연패방을 찾습니다."
                    })
                elif result == "LOSE":
                    # 패배 - 마틴게일 진행
                    self.consecutive_losses += 1
                    self.martin_step += 1
                    
                    if self.martin_step >= self.martin_strategy.martin_count:
                        # 마틴 한계 도달
                        await websocket_manager.send_status_update(self.username, {
                            "status": "martin_limit",
                            "message": f"마틴게일 한계 도달. 다른 방을 찾습니다."
                        })
                        self.martin_step = 0
                        self.consecutive_losses = 0
                
                # 5. 방 나가기
                self.selenium.exit_room()
                self.current_room = None
                
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"트레이딩 루프 오류: {e}")
                await asyncio.sleep(5)
    
    async def find_streak_room(self, min_streak: int) -> Optional[str]:
        """연패방 찾기"""
        try:
            logger.info(f"🔍 연패방 검색 시작 (min_streak={min_streak})")
            
            # 예측 서버에서 연패방 목록 가져오기
            streak_response = await self.prediction_client.find_streak_rooms(min_streak)
            
            if not streak_response:
                logger.warning("❌ 서버 응답 없음")
                return None
            
            # 응답에서 방 목록 추출
            rooms = []
            if isinstance(streak_response, dict):
                if "streak_rooms" in streak_response:
                    rooms = streak_response["streak_rooms"]
                elif "data" in streak_response and "rooms" in streak_response["data"]:
                    rooms = streak_response["data"]["rooms"]
            elif isinstance(streak_response, list):
                rooms = streak_response
            
            if not rooms:
                logger.warning("⚠️ 연패방을 찾을 수 없습니다")
                return None
            
            logger.info(f"🏠 연패방 {len(rooms)}개 발견")
            
            # 첫 번째 적합한 방 선택
            for room in rooms:
                room_name = None
                current_streak = 0
                
                if isinstance(room, dict):
                    room_name = room.get("room_name") or room.get("name")
                    current_streak = room.get("current_streak", 0)
                elif isinstance(room, str):
                    room_name = room
                
                if room_name and current_streak >= min_streak:
                    logger.info(f"✅ 적합한 연패방 발견: {room_name} (연패:{current_streak})")
                    return room_name
            
            return None
            
        except Exception as e:
            logger.error(f"연패방 찾기 오류: {e}")
            return None
    
    async def play_in_room(self, websocket_manager: WebSocketManager) -> str:
        """방에서 게임 플레이"""
        try:
            # 베팅할 타입 결정 (연패의 반대)
            bet_type = 'P'  # 기본값: Player
            
            # 마틴게일 금액 결정
            bet_amount = self.martin_strategy.get_bet_amount(self.martin_step)
            
            # 베팅 시간 대기
            while self.is_active and not self._stop_requested:
                is_betting_time, time_remaining = self.betting.check_betting_time()
                
                if is_betting_time and time_remaining > 3:
                    # 베팅 실행
                    if self.betting.execute_bet(bet_type, bet_amount):
                        self.game_count += 1
                        self.total_bet_amount += bet_amount
                        
                        await websocket_manager.send_betting_placed(self.username, {
                            "bet_type": bet_type,
                            "amount": bet_amount,
                            "martin_step": self.martin_step,
                            "game_count": self.game_count
                        })
                        
                        # 결과 대기
                        result = await self.wait_for_result(bet_type, websocket_manager)
                        return result
                    else:
                        logger.error("베팅 실행 실패")
                        return "ERROR"
                
                await asyncio.sleep(1)
                
            return "STOPPED"
            
        except Exception as e:
            logger.error(f"게임 플레이 오류: {e}")
            return "ERROR"
    
    async def wait_for_result(self, bet_type: str, websocket_manager: WebSocketManager) -> str:
        """게임 결과 대기"""
        try:
            # 최대 60초 대기
            for _ in range(60):
                if self._stop_requested:
                    return "STOPPED"
                
                result = self.betting.get_game_result()
                if result:
                    # 통계 업데이트
                    self.statistics["total_games"] += 1
                    
                    if result == 'T':
                        # 무승부
                        self.statistics["ties"] += 1
                        await websocket_manager.send_betting_result(self.username, {
                            "result": "tie",
                            "bet_type": bet_type,
                            "game_result": result
                        })
                        return "TIE"
                    elif result == bet_type:
                        # 승리
                        self.statistics["wins"] += 1
                        await websocket_manager.send_betting_result(self.username, {
                            "result": "win",
                            "bet_type": bet_type,
                            "game_result": result
                        })
                        return "WIN"
                    else:
                        # 패배
                        self.statistics["losses"] += 1
                        await websocket_manager.send_betting_result(self.username, {
                            "result": "lose",
                            "bet_type": bet_type,
                            "game_result": result
                        })
                        return "LOSE"
                
                await asyncio.sleep(1)
            
            logger.warning("결과 대기 시간 초과")
            return "TIMEOUT"
            
        except Exception as e:
            logger.error(f"결과 대기 오류: {e}")
            return "ERROR"
    
    async def stop_trading(self):
        """트레이딩 중지"""
        try:
            self._stop_requested = True
            self.is_active = False
            
            # 브라우저 종료
            if self.selenium:
                self.selenium.close_browser()
            
            logger.info(f"트레이딩 중지: {self.username}")
            
        except Exception as e:
            logger.error(f"트레이딩 중지 오류: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        stats = self.statistics.copy()
        if stats["total_games"] > 0:
            stats["win_rate"] = (stats["wins"] / stats["total_games"]) * 100
        else:
            stats["win_rate"] = 0
        return stats