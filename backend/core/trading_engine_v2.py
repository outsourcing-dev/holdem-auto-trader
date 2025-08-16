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
from core.websocket_monitor import WebSocketMonitor
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
        self.websocket_monitor = None  # WebSocket 모니터 (브라우저 시작 후 초기화)
        self.martin_strategy = MartinStrategy()
        self.prediction_client = PredictionClient()
        
        # 상태 변수
        self.is_active = False
        self.browser_launched = False  # 브라우저 실행 상태
        self.current_room = None
        self.game_count = 0
        self.total_bet_amount = 0
        self.current_balance = None
        self.martin_step = 0
        self.consecutive_losses = 0
        self.min_streak = 3  # 기본값
        self.websocket_manager = None
        
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
        """브라우저만 시작 (베팅은 나중에)"""
        try:
            # is_active는 베팅이 시작될 때만 True로 설정
            self._stop_requested = False
            self.min_streak = min_streak  # 저장
            self.websocket_manager = websocket_manager  # 저장
            
            # URL 정리
            if not site_url.startswith('http'):
                site_url = f'https://{site_url}'
            
            logger.info(f"브라우저 시작: {self.username}, URL: {site_url}")
            
            # 브라우저 시작
            if not self.selenium.start_browser(site_url):
                raise Exception("브라우저 시작 실패")
            
            self.browser_launched = True  # 브라우저 실행 상태 추가
            
            # WebSocket 상태 전송
            await websocket_manager.send_status_update(self.username, {
                "status": "browser_launched",
                "message": "브라우저가 실행되었습니다. 로그인 후 Evolution 게임에 접속해주세요."
            })
            
            logger.info("브라우저 실행 완료. 사용자 로그인 대기 중...")
            
        except Exception as e:
            logger.error(f"브라우저 시작 오류: {e}")
            await websocket_manager.send_status_update(self.username, {
                "status": "error",
                "message": f"브라우저 시작 오류: {str(e)}"
            })
            await self.stop_trading()
    
    async def start_betting(self, websocket_manager: WebSocketManager):
        """베팅 시작 (사용자가 Evolution 게임에 접속한 후)"""
        try:
            if not self.browser_launched:
                raise Exception("브라우저가 실행되지 않았습니다")
            
            # 베팅 시작 시 is_active를 True로 설정
            self.is_active = True
            
            # BettingExecutor 초기화
            self.betting = BettingExecutor(self.selenium.driver)
            
            # WebSocket 모니터 초기화 및 시작
            self.websocket_monitor = WebSocketMonitor(self.selenium.driver)
            await self.websocket_monitor.start_monitoring(self.min_streak)
            
            logger.info("베팅 시작. Evolution iframe 감지 시도...")
            
            # WebSocket 상태 전송
            await websocket_manager.send_status_update(self.username, {
                "status": "betting_started",
                "message": "베팅을 시작합니다. Evolution 게임을 감지하는 중..."
            })
            
            # Evolution iframe 대기
            found = await self.wait_for_evolution_iframe(websocket_manager)
            if not found:
                raise Exception("Evolution 게임을 찾을 수 없습니다")
            
            # 메인 트레이딩 루프
            await self.main_trading_loop(self.min_streak, websocket_manager)
            
        except Exception as e:
            logger.error(f"베팅 시작 오류: {e}")
            await websocket_manager.send_status_update(self.username, {
                "status": "error",
                "message": f"베팅 오류: {str(e)}"
            })
        finally:
            # 베팅만 중지, 브라우저는 유지
            self.is_active = False
    
    async def wait_for_evolution_iframe(self, websocket_manager: WebSocketManager):
        """Evolution iframe 대기"""
        check_count = 0
        max_wait = 120  # 최대 2분 대기
        
        while self.is_active and not self._stop_requested and check_count < max_wait:
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
            
            # 30초마다 알림
            if check_count % 30 == 0:
                logger.info(f"Evolution iframe 대기 중... ({check_count}초)")
        
        # 타임아웃
        logger.warning(f"Evolution iframe을 {max_wait}초 동안 감지하지 못했습니다")
        await websocket_manager.send_status_update(self.username, {
            "status": "timeout",
            "message": f"Evolution 게임을 감지하지 못했습니다. 게임 창이 열렸는지 확인해주세요."
        })
        return False
    
    async def main_trading_loop(self, min_streak: int, websocket_manager: WebSocketManager):
        """메인 트레이딩 루프"""
        
        # 연패방 정보 업데이트 태스크 시작
        import asyncio
        update_task = asyncio.create_task(self._update_streak_rooms_periodically(websocket_manager))
        
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
        """연패방 찾기 - WebSocket 모니터링 우선 사용"""
        try:
            logger.info(f"🔍 연패방 검색 시작 (min_streak={min_streak})")
            
            # 1. WebSocket 모니터에서 연패방 확인
            if self.websocket_monitor:
                best_room = self.websocket_monitor.get_best_streak_room()
                if best_room:
                    room_name = best_room.get('room_name')
                    current_streak = best_room.get('current_streak', 0)
                    verified = best_room.get('verified', False)
                    
                    if verified:
                        logger.info(f"✅ WebSocket에서 검증된 연패방 발견: {room_name} (연패:{current_streak})")
                        return room_name
                    else:
                        logger.info(f"🎯 WebSocket에서 연패방 발견 (미검증): {room_name} (연패:{current_streak})")
                        # 미검증 방도 사용 가능
                        return room_name
            
            # 2. WebSocket에서 못 찾은 경우 예측 서버 직접 호출 (폴백)
            logger.info("📡 예측 서버에서 연패방 검색...")
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
                            "game_result": result,
                            "martin_step": self.martin_step,
                            "statistics": self.get_statistics()
                        })
                        return "TIE"
                    elif result == bet_type:
                        # 승리
                        self.statistics["wins"] += 1
                        await websocket_manager.send_betting_result(self.username, {
                            "result": "win",
                            "bet_type": bet_type,
                            "game_result": result,
                            "martin_step": self.martin_step,
                            "statistics": self.get_statistics()
                        })
                        return "WIN"
                    else:
                        # 패배
                        self.statistics["losses"] += 1
                        await websocket_manager.send_betting_result(self.username, {
                            "result": "lose",
                            "bet_type": bet_type,
                            "game_result": result,
                            "martin_step": self.martin_step,
                            "statistics": self.get_statistics()
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
            self.browser_launched = False
            
            # WebSocket 모니터 중지
            if self.websocket_monitor:
                await self.websocket_monitor.stop_monitoring()
                self.websocket_monitor = None
            
            # 브라우저 종료
            if self.selenium:
                self.selenium.close_browser()
            
            logger.info(f"트레이딩 중지: {self.username}")
            
        except Exception as e:
            logger.error(f"트레이딩 중지 오류: {e}")
    
    async def force_stop(self):
        """강제 종료"""
        await self.stop_trading()
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        stats = self.statistics.copy()
        if stats["total_games"] > 0:
            stats["win_rate"] = (stats["wins"] / stats["total_games"]) * 100
        else:
            stats["win_rate"] = 0
            
        # WebSocket 모니터링 상태 추가
        if self.websocket_monitor:
            stats['websocket_status'] = self.websocket_monitor.get_monitoring_status()
        else:
            stats['websocket_status'] = {'is_monitoring': False}
            
        return stats
    
    async def _update_streak_rooms_periodically(self, websocket_manager: WebSocketManager):
        """주기적으로 연패방 정보를 UI에 업데이트"""
        while self.is_active and not self._stop_requested:
            try:
                if self.websocket_monitor:
                    # 현재 감지된 연패방 정보 가져오기
                    streak_rooms = self.websocket_monitor.get_streak_rooms()
                    monitoring_status = self.websocket_monitor.get_monitoring_status()
                    
                    # WebSocket으로 UI에 전송
                    await websocket_manager.send_streak_rooms_update(self.username, {
                        "rooms": streak_rooms,
                        "is_monitoring": monitoring_status.get('is_monitoring', False),
                        "total_rooms": monitoring_status.get('total_rooms', 0),
                        "min_streak": monitoring_status.get('min_streak', 3)
                    })
                    
                await asyncio.sleep(3)  # 3초마다 업데이트
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"연패방 업데이트 오류: {e}")
                await asyncio.sleep(5)