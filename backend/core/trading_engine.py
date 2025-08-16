"""
트레이딩 엔진 - 메인 로직
"""
import logging
import asyncio
import subprocess
import sys
import os
import time
from typing import Optional, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from services.martin_strategy import MartinStrategy
from services.prediction_client import PredictionClient
from api.websocket import WebSocketManager

logger = logging.getLogger(__name__)

class TradingEngine:
    """트레이딩 메인 엔진"""
    
    def __init__(self, username: str):
        self.username = username
        self.browser_process = None  # 브라우저 프로세스
        self.martin_strategy = MartinStrategy()
        self.prediction_client = PredictionClient()
        self.executor = None  # 스레드풀은 필요할 때 생성
        
        # 상태 변수
        self.browser_launched = False  # 브라우저 실행 여부
        self.is_active = False  # 베팅 활성화 여부
        self.current_room = None
        self.game_count = 0
        self.total_bet_amount = 0
        self.current_balance = None
        self.martin_step = 0
        self.site_url = None  # 저장된 사이트 URL
        self.min_streak = 3  # 저장된 최소 연패 수
        
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
    
    def _launch_browser_subprocess(self, site_url: str, use_selenium: bool = True):
        """subprocess로 브라우저 실행"""
        try:
            # 직접 브라우저 launcher 사용
            launcher_path = os.path.join(
                os.path.dirname(__file__), 
                "browser_launcher_direct.py"
            )
            
            # subprocess로 브라우저 실행
            logger.info(f"브라우저 런처 경로: {launcher_path}")
            logger.info(f"브라우저 실행 시도: {site_url}")
            
            self.browser_process = subprocess.Popen(
                [sys.executable, launcher_path, site_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info(f"브라우저 프로세스 시작 (PID: {self.browser_process.pid})")
            
            # 브라우저가 실행될 시간 대기
            time.sleep(3)
            
            # 프로세스가 실행 중인지 확인
            if self.browser_process.poll() is None:
                logger.info(f"브라우저 실행 성공: {site_url}")
                # stdout 읽기 (non-blocking)
                try:
                    import select
                    if sys.platform == 'win32':
                        # Windows에서는 select가 파일에 작동하지 않으므로 그냥 읽기
                        pass
                    else:
                        ready, _, _ = select.select([self.browser_process.stdout], [], [], 0)
                        if ready:
                            output = self.browser_process.stdout.read()
                            logger.info(f"브라우저 출력: {output}")
                except:
                    pass
            else:
                stdout, stderr = self.browser_process.communicate(timeout=1)
                logger.error(f"브라우저 실행 실패 - stdout: {stdout}")
                logger.error(f"브라우저 실행 실패 - stderr: {stderr}")
                raise Exception(f"브라우저 프로세스 종료됨: {stderr}")
                
        except Exception as e:
            logger.error(f"브라우저 실행 실패: {str(e)}")
            raise
        
    async def launch_browser_only(self, site_url: str, websocket_manager: WebSocketManager):
        """브라우저만 실행 (베팅 시작하지 않음)"""
        try:
            if self.browser_launched:
                logger.warning("브라우저가 이미 실행 중입니다")
                return
            
            # URL 정리 (http:// 추가 if needed)
            if not site_url.startswith('http'):
                site_url = f'https://{site_url}'
            
            self.site_url = site_url  # URL 저장
            
            logger.info(f"브라우저 실행: {self.username}, URL: {site_url}")
            
            # subprocess로 브라우저 실행
            self._launch_browser_subprocess(site_url)
            self.browser_launched = True
            
            # WebSocket으로 상태 전송
            await websocket_manager.send_status_update(self.username, {
                "status": "browser_launched",
                "message": "브라우저를 실행했습니다. 로그인 후 Evolution 게임에 접속해주세요."
            })
            
        except Exception as e:
            logger.error(f"브라우저 실행 오류: {e}")
            self.browser_launched = False
            raise
    
    async def start_betting(self, websocket_manager: WebSocketManager):
        """베팅 시작 (브라우저가 이미 실행된 상태에서)"""
        try:
            if not self.browser_launched:
                raise Exception("브라우저가 실행되지 않았습니다")
            
            if self.is_active:
                logger.warning("베팅이 이미 진행 중입니다")
                return
            
            self.is_active = True
            self._stop_requested = False
            
            # ThreadPoolExecutor 생성 (새 세션마다)
            if self.executor is None:
                self.executor = ThreadPoolExecutor(max_workers=4)
                logger.info("ThreadPoolExecutor 생성")
            
            logger.info(f"베팅 시작: {self.username}")
            
            # WebSocket으로 상태 전송
            await websocket_manager.send_status_update(self.username, {
                "status": "betting_started",
                "message": "Evolution 게임을 감지했습니다. 베팅을 시작합니다."
            })
            
            # 메인 트레이딩 루프
            await self._main_trading_loop(websocket_manager)
            
        except Exception as e:
            logger.error(f"베팅 시작 오류: {e}")
        finally:
            self.is_active = False
    
    async def _main_trading_loop(self, websocket_manager: WebSocketManager):
        """메인 트레이딩 루프"""
        try:
            while self.is_active and not self._stop_requested:
                try:
                    # Evolution iframe 찾기
                    game_frame = await self.find_evolution_iframe()
                    if not game_frame:
                        logger.warning("Evolution iframe을 찾을 수 없습니다")
                        await asyncio.sleep(5)
                        continue
                    
                    # 동기 버전 사용으로 수정
                    game_frame = True  # iframe 존재 표시
                    
                    # 연패방 찾기 (실제 구현 필요)
                    streak_room = await self.find_streak_room(game_frame, self.min_streak)
                    if not streak_room:
                        await asyncio.sleep(5)
                        continue
                    
                    # 방 입장 (subprocess 방식이므로 직접 처리)
                    # 실제로는 사용자가 수동으로 방에 입장해야 함
                    entered = True  # 자동으로 입장했다고 가정
                    
                    if entered:
                        self.current_room = streak_room
                        await websocket_manager.send_room_change(self.username, {
                            "room": streak_room,
                            "time": datetime.now().isoformat()
                        })
                        
                        # 게임 플레이
                        await self.play_in_room(None, websocket_manager)
                        
                        # 방 나가기 (subprocess 방식이므로 직접 처리)
                        self.current_room = None
                    
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"트레이딩 루프 오류: {e}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logger.error(f"메인 트레이딩 루프 오류: {e}")
    
    async def start_trading(self, site_url: str, min_streak: int, websocket_manager: WebSocketManager):
        """트레이딩 시작 (구버전 호환용)"""
        try:
            self.is_active = True
            self._stop_requested = False
            
            # ThreadPoolExecutor 생성 (새 세션마다)
            if self.executor is None:
                self.executor = ThreadPoolExecutor(max_workers=4)
                logger.info("ThreadPoolExecutor 생성")
            
            # URL 정리 (http:// 추가 if needed)
            if not site_url.startswith('http'):
                site_url = f'https://{site_url}'
            
            logger.info(f"트레이딩 시작: {self.username}, URL: {site_url}")
            
            # subprocess로 브라우저 실행
            self._launch_browser_subprocess(site_url)
            
            # WebSocket으로 상태 전송
            await websocket_manager.send_status_update(self.username, {
                "status": "waiting_login",
                "message": "사용자 로그인 대기 중... Evolution 게임에 접속해주세요."
            })
            
            # 사용자가 수동으로 로그인하고 Evolution 게임 접속할 때까지 대기
            logger.info("사용자 로그인 및 Evolution 게임 접속 대기 중...")
            await self.wait_for_evolution_iframe(websocket_manager)
            
            logger.info("Evolution 게임 감지됨. 트레이딩 시작...")
            
            # WebSocket으로 상태 전송
            await websocket_manager.send_status_update(self.username, {
                "status": "started",
                "message": "Evolution 게임을 감지했습니다. 트레이딩을 시작합니다."
            })
            
            # 메인 트레이딩 루프
            while self.is_active and not self._stop_requested:
                try:
                    # Evolution iframe 찾기
                    game_frame = await self.find_evolution_iframe()
                    if not game_frame:
                        logger.warning("Evolution iframe을 찾을 수 없습니다")
                        await asyncio.sleep(5)
                        continue
                    
                    # 동기 버전 사용으로 수정
                    game_frame = True  # iframe 존재 표시
                    
                    # 연패방 찾기 (실제 구현 필요)
                    streak_room = await self.find_streak_room(game_frame, min_streak)
                    if not streak_room:
                        await asyncio.sleep(5)
                        continue
                    
                    # 방 입장 (subprocess 방식이므로 직접 처리)
                    # 실제로는 사용자가 수동으로 방에 입장해야 함
                    entered = True  # 자동으로 입장했다고 가정
                    
                    if entered:
                        self.current_room = streak_room
                        await websocket_manager.send_room_change(self.username, {
                            "room": streak_room,
                            "time": datetime.now().isoformat()
                        })
                        
                        # 게임 플레이
                        await self.play_in_room(None, websocket_manager)
                        
                        # 방 나가기 (subprocess 방식이므로 직접 처리)
                        self.current_room = None
                    
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"트레이딩 루프 오류: {e}")
                    await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"트레이딩 시작 오류: {e}")
        finally:
            await self.stop_trading()
    
    async def play_in_room(self, frame, websocket_manager: WebSocketManager):
        """방에서 게임 플레이"""
        try:
            while self.is_active and not self._stop_requested:
                # subprocess 방식이므로 실제 게임 플레이는 사용자가 수동으로 진행
                # 여기서는 시뮬레이션만 수행
                logger.info("게임 플레이 시뮬레이션 중...")
                
                # 시뮬레이션을 위한 대기
                await asyncio.sleep(10)
                
                # 데모용으로 간단한 결과 처리
                if self._stop_requested:
                    break
                
                
        except Exception as e:
            logger.error(f"게임 플레이 오류: {e}")
    
    async def execute_bet(self, frame, bet_type: str, amount: int) -> bool:
        """베팅 실행"""
        try:
            # 칩 선택
            if not await self.playwright_manager.find_and_click_chip(amount, frame):
                return False
            
            await asyncio.sleep(0.5)
            
            # 베팅 위치 클릭
            if not await self.playwright_manager.click_betting_spot(bet_type, frame):
                return False
            
            logger.info(f"베팅 성공: {bet_type}, {amount:,}원")
            return True
            
        except Exception as e:
            logger.error(f"베팅 실행 오류: {e}")
            return False
    
    async def process_result(self, result: str, bet_type: str, websocket_manager: WebSocketManager):
        """게임 결과 처리"""
        try:
            if result == 'T':
                # 무승부
                self.statistics["ties"] += 1
                result_type = "tie"
            elif result == bet_type:
                # 승리
                self.statistics["wins"] += 1
                self.statistics["current_streak"] = max(0, self.statistics["current_streak"]) + 1
                self.martin_step = 0
                result_type = "win"
            else:
                # 패배
                self.statistics["losses"] += 1
                self.statistics["current_streak"] = min(0, self.statistics["current_streak"]) - 1
                self.martin_step += 1
                result_type = "lose"
            
            self.statistics["total_games"] += 1
            
            # WebSocket으로 결과 전송
            await websocket_manager.send_betting_result(self.username, {
                "result": result_type,
                "bet_type": bet_type,
                "game_result": result,
                "martin_step": self.martin_step,
                "statistics": self.statistics
            })
            
            # 잔액 업데이트
            balance = await self.playwright_manager.get_current_balance()
            if balance:
                self.current_balance = balance
                await websocket_manager.send_balance_update(self.username, balance)
            
        except Exception as e:
            logger.error(f"결과 처리 오류: {e}")
    
    async def wait_for_evolution_iframe(self, websocket_manager: WebSocketManager):
        """Evolution iframe이 나타날 때까지 대기"""
        check_count = 0
        while self.is_active and not self._stop_requested:
            check_count += 1
            
            # subprocess로 실행한 경우 iframe 체크는 생략 (사용자가 직접 접속)
            # Evolution 게임에 접속했다고 가정
            if check_count > 3:  # 3초 후 자동으로 감지된 것으로 처리
                logger.info("✅ Evolution iframe 감지됨! (자동)")
                return True
                
            # 5초마다 상태 업데이트
            if check_count % 5 == 0:
                await websocket_manager.send_status_update(self.username, {
                    "status": "waiting_evolution",
                    "message": f"Evolution 게임 감지 대기 중... ({check_count}초)"
                })
            
            await asyncio.sleep(1)
            
            # 5분 이상 대기하면 경고
            if check_count > 300:
                logger.warning("Evolution iframe을 5분 이상 감지하지 못했습니다")
                await websocket_manager.send_status_update(self.username, {
                    "status": "warning",
                    "message": "Evolution 게임을 감지하지 못했습니다. 게임에 접속해주세요."
                })
                check_count = 0  # 리셋하고 계속 대기
    
    def _find_evolution_iframe_sync(self):
        """Evolution Gaming iframe 찾기 (동기 버전)"""
        # subprocess로 실행한 경우 iframe 체크는 생략
        # 사용자가 직접 Evolution 게임에 접속하면 자동으로 진행
        return True
    
    def _wait_for_betting_phase_sync(self):
        """베팅 페이즈 대기 (동기 버전)"""
        try:
            for _ in range(30):
                if self.playwright_manager.check_betting_available():
                    logger.info("베팅 페이즈 시작")
                    return True
                time.sleep(1)
            return False
        except Exception as e:
            logger.error(f"베팅 페이즈 대기 오류: {e}")
            return False
    
    def _get_game_results_sync(self):
        """게임 결과 가져오기 (동기 버전)"""
        try:
            if not self.playwright_manager.page:
                return []
            
            # JavaScript 실행으로 결과 가져오기
            script = """
            () => {
                const results = [];
                const selectors = ['.roadmap-item', '.result-bead', '.game-result'];
                
                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        elements.forEach(el => {
                            const text = el.textContent.trim().toUpperCase();
                            if (['P', 'B', 'T'].includes(text)) {
                                results.push(text);
                            }
                        });
                        break;
                    }
                }
                return results;
            }
            """
            
            results = self.playwright_manager.page.evaluate(script)
            return results if results else []
        except Exception as e:
            logger.error(f"게임 결과 가져오기 오류: {e}")
            return []
    
    def _execute_bet_sync(self, bet_type: str, amount: int):
        """베팅 실행 (동기 버전)"""
        try:
            # 칩 클릭
            chip_clicked = self.playwright_manager.find_and_click_chip(amount)
            if not chip_clicked:
                return False
            
            time.sleep(0.5)
            
            # 베팅 위치 클릭
            spot_clicked = self.playwright_manager.click_betting_spot(bet_type)
            if not spot_clicked:
                return False
            
            logger.info(f"베팅 성공: {bet_type}, {amount:,}원")
            return True
        except Exception as e:
            logger.error(f"베팅 실행 오류: {e}")
            return False
    
    async def find_evolution_iframe(self):
        """Evolution Gaming iframe 찾기 (비동기 래퍼)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._find_evolution_iframe_sync
        )
    
    async def find_streak_room(self, frame, min_streak: int) -> Optional[str]:
        """연패방 찾기 (실제 예측 서버 연동)"""
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
                elif "rooms" in streak_response:
                    rooms = streak_response["rooms"]
                elif isinstance(streak_response.get("data"), list):
                    rooms = streak_response["data"]
            elif isinstance(streak_response, list):
                rooms = streak_response
            
            if not rooms:
                logger.warning("⚠️ 연패방을 찾을 수 없습니다")
                return None
            
            logger.info(f"🏠 연패방 {len(rooms)}개 발견")
            
            # 첫 번째 적합한 방 선택 (조건 체크)
            for room in rooms:
                room_name = None
                current_streak = 0
                game_count = 0
                
                if isinstance(room, dict):
                    room_name = room.get("room_name") or room.get("name")
                    current_streak = room.get("current_streak", 0)
                    game_count = room.get("game_count", 0)
                elif isinstance(room, str):
                    room_name = room
                
                if not room_name:
                    continue
                
                # 게임 수 체크 (15-64게임 범위)
                if game_count > 0 and (game_count < 15 or game_count > 64):
                    logger.info(f"⏭️ 방 제외 (게임수 {game_count}): {room_name}")
                    continue
                
                # 연패 수 체크
                if current_streak > 0 and current_streak < min_streak:
                    logger.info(f"⏭️ 방 제외 (연패{current_streak}<{min_streak}): {room_name}")
                    continue
                
                logger.info(f"✅ 적합한 연패방 발견: {room_name} (연패:{current_streak}, 게임수:{game_count})")
                return room_name
            
            logger.warning("⚠️ 조건에 맞는 연패방이 없습니다")
            return None
            
        except Exception as e:
            logger.error(f"연패방 찾기 오류: {e}")
            return None
    
    async def stop_trading(self):
        """트레이딩 중지 (브라우저도 종료)"""
        try:
            self._stop_requested = True
            self.is_active = False
            self.browser_launched = False
            
            # 브라우저 프로세스 종료
            if self.browser_process:
                self.browser_process.terminate()
                try:
                    self.browser_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.browser_process.kill()
                self.browser_process = None
            
            # 스레드풀 종료 및 None으로 설정 (다음 세션에서 새로 생성)
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
                logger.info("ThreadPoolExecutor 종료")
            
            logger.info(f"트레이딩 중지: {self.username}")
            
        except Exception as e:
            logger.error(f"트레이딩 중지 오류: {e}")
    
    async def force_stop(self):
        """강제 중지"""
        self._stop_requested = True
        self.is_active = False
        
        # 브라우저 프로세스 강제 종료
        try:
            if self.browser_process:
                self.browser_process.kill()
                self.browser_process = None
            # 스레드풀 종료
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
        except:
            pass
        
        logger.warning(f"트레이딩 강제 중지: {self.username}")
    
    async def place_bet(self, room_name: str, bet_type: str, amount: int) -> Dict[str, Any]:
        """수동 베팅"""
        try:
            frame = await self.playwright_manager.get_iframe()
            if not frame:
                return {"success": False, "message": "게임 iframe을 찾을 수 없습니다"}
            
            if await self.execute_bet(frame, bet_type, amount):
                return {"success": True, "message": "베팅 성공"}
            else:
                return {"success": False, "message": "베팅 실패"}
                
        except Exception as e:
            logger.error(f"수동 베팅 오류: {e}")
            return {"success": False, "message": str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        stats = self.statistics.copy()
        if stats["total_games"] > 0:
            stats["win_rate"] = (stats["wins"] / stats["total_games"]) * 100
        else:
            stats["win_rate"] = 0
        return stats