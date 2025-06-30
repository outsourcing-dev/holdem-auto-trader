# services/websocket_direct_client.py
"""
웹소켓 직접 통신 클라이언트
- 추출된 웹소켓 URL로 직접 연결
- 실시간 바카라 게임 데이터 수신
- JSON 메시지 파싱 및 게임 상태 추출
"""
import asyncio
import websockets
import json
import logging
import time
import re
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from urllib.parse import urlparse, parse_qs
import ssl

@dataclass
class GameData:
    """게임 데이터 구조체"""
    room_name: str = ""
    round_number: int = 0
    latest_result: str = ""  # P, B, T
    game_status: str = ""  # betting, dealing, result 등
    player_cards: List[str] = None
    banker_cards: List[str] = None
    recent_results: List[str] = None
    timestamp: float = 0.0
    raw_data: dict = None

    def __post_init__(self):
        if self.player_cards is None:
            self.player_cards = []
        if self.banker_cards is None:
            self.banker_cards = []
        if self.recent_results is None:
            self.recent_results = []
        if self.timestamp == 0.0:
            self.timestamp = time.time()

class WebSocketDirectClient(QObject):
    """웹소켓 직접 통신 클라이언트"""
    
    # Qt 시그널 정의
    game_data_received = pyqtSignal(GameData)
    connection_status_changed = pyqtSignal(bool)  # 연결 상태
    error_occurred = pyqtSignal(str)  # 오류 메시지
    room_data_updated = pyqtSignal(dict)  # 방 데이터 업데이트
    
    def __init__(self, logger=None):
        super().__init__()
        self.logger = logger or logging.getLogger(__name__)
        
        # 연결 상태
        self.websocket = None
        self.is_connected = False
        self.is_running = False
        self.websocket_url = None
        
        # 데이터 처리
        self.message_count = 0
        self.last_game_data = None
        self.current_room_name = ""
        
        # 비동기 처리용
        self.loop = None
        self.connection_task = None
        
        self.logger.info("WebSocketDirectClient 초기화 완료")

    async def connect_and_listen(self, websocket_url: str):
        """웹소켓 연결 및 메시지 수신 시작"""
        try:
            self.websocket_url = websocket_url
            self.logger.info(f"🔌 웹소켓 연결 시도: {websocket_url[:50]}...")
            
            # SSL 컨텍스트 설정 (인증서 검증 비활성화)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # 웹소켓 연결
            async with websockets.connect(
                websocket_url,
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                self.websocket = websocket
                self.is_connected = True
                self.connection_status_changed.emit(True)
                
                self.logger.info("✅ 웹소켓 연결 성공")
                
                # 메시지 수신 루프
                await self._message_receive_loop()
                
        except Exception as e:
            self.logger.error(f"❌ 웹소켓 연결 오류: {e}")
            self.error_occurred.emit(f"웹소켓 연결 실패: {str(e)}")
        finally:
            self.is_connected = False
            self.websocket = None
            self.connection_status_changed.emit(False)

    async def _message_receive_loop(self):
        """메시지 수신 루프"""
        try:
            self.logger.info("📡 웹소켓 메시지 수신 시작")
            
            async for message in self.websocket:
                if not self.is_running:
                    break
                
                try:
                    self.message_count += 1
                    await self._process_message(message)
                    
                    # 너무 많은 메시지 로그 방지
                    if self.message_count % 100 == 0:
                        self.logger.debug(f"📊 처리된 메시지 수: {self.message_count}")
                        
                except Exception as e:
                    self.logger.warning(f"메시지 처리 오류: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"메시지 수신 루프 오류: {e}")
            self.error_occurred.emit(f"메시지 수신 오류: {str(e)}")

    async def _process_message(self, message: str):
        """개별 메시지 처리"""
        try:
            # JSON 파싱 시도
            if message.startswith('{') or message.startswith('['):
                data = json.loads(message)
                await self._handle_json_message(data)
            else:
                # 텍스트 메시지 처리
                await self._handle_text_message(message)
                
        except json.JSONDecodeError:
            # JSON이 아닌 경우 텍스트로 처리
            await self._handle_text_message(message)
        except Exception as e:
            self.logger.debug(f"메시지 처리 중 오류: {e}")

    async def _handle_json_message(self, data: dict):
        """JSON 메시지 처리"""
        try:
            # 바카라 게임 관련 데이터인지 확인
            if self._is_baccarat_game_message(data):
                game_data = self._extract_game_data_from_json(data)
                
                if game_data and self._is_valid_game_data(game_data):
                    # 중복 데이터 필터링
                    if self._is_new_game_data(game_data):
                        self.last_game_data = game_data
                        self.game_data_received.emit(game_data)
                        
                        # 상세 로그 출력 (중요한 데이터만)
                        if game_data.latest_result:
                            self.logger.info(f"🎯 게임 데이터: {game_data.room_name} - 라운드 {game_data.round_number}, 결과: {game_data.latest_result}")
                        
                        # 방 데이터 업데이트 시그널
                        self.room_data_updated.emit({
                            'room_name': game_data.room_name,
                            'round': game_data.round_number,
                            'latest_result': game_data.latest_result,
                            'status': game_data.game_status,
                            'timestamp': game_data.timestamp
                        })
                
        except Exception as e:
            self.logger.debug(f"JSON 메시지 처리 오류: {e}")

    async def _handle_text_message(self, message: str):
        """텍스트 메시지 처리"""
        try:
            # 바카라 관련 키워드 확인
            if self._contains_baccarat_keywords(message):
                game_data = self._extract_game_data_from_text(message)
                
                if game_data and self._is_valid_game_data(game_data):
                    if self._is_new_game_data(game_data):
                        self.last_game_data = game_data
                        self.game_data_received.emit(game_data)
                        
                        if game_data.latest_result:
                            self.logger.info(f"🎯 텍스트 게임 데이터: {game_data.room_name} - 결과: {game_data.latest_result}")
                
        except Exception as e:
            self.logger.debug(f"텍스트 메시지 처리 오류: {e}")

    def _is_baccarat_game_message(self, data: dict) -> bool:
        """바카라 게임 메시지인지 확인"""
        try:
            data_str = str(data).lower()
            
            # 바카라 관련 키워드
            baccarat_keywords = [
                'baccarat', 'player', 'banker', 'tie',
                'game_result', 'round', 'table',
                'cards', 'score', 'winner'
            ]
            
            return any(keyword in data_str for keyword in baccarat_keywords)
            
        except Exception:
            return False

    def _contains_baccarat_keywords(self, message: str) -> bool:
        """텍스트에 바카라 키워드가 있는지 확인"""
        try:
            message_lower = message.lower()
            
            baccarat_keywords = [
                'baccarat', 'player', 'banker', 'tie',
                'p', 'b', 't', 'round', 'game',
                'result', 'winner', 'cards'
            ]
            
            return any(keyword in message_lower for keyword in baccarat_keywords)
            
        except Exception:
            return False

    def _extract_game_data_from_json(self, data: dict) -> Optional[GameData]:
        """JSON 데이터에서 게임 정보 추출"""
        try:
            game_data = GameData()
            game_data.raw_data = data
            
            # 다양한 JSON 구조에 대응하여 데이터 추출
            possible_keys = {
                'room_name': ['table_name', 'room_name', 'table_id', 'roomName', 'tableName'],
                'round_number': ['round', 'game_number', 'round_number', 'gameNumber', 'roundNumber'],
                'latest_result': ['result', 'winner', 'game_result', 'outcome', 'lastResult'],
                'game_status': ['status', 'game_status', 'state', 'phase', 'gameState'],
                'player_cards': ['player_cards', 'playerCards', 'player', 'playerHand'],
                'banker_cards': ['banker_cards', 'bankerCards', 'banker', 'bankerHand']
            }
            
            # 키별로 값 추출
            for target_attr, source_keys in possible_keys.items():
                value = self._extract_value_from_keys(data, source_keys)
                if value is not None:
                    setattr(game_data, target_attr, value)
            
            # 최근 결과 추출 (배열인 경우)
            recent_results = self._extract_value_from_keys(data, ['recent_results', 'history', 'results'])
            if recent_results and isinstance(recent_results, list):
                game_data.recent_results = recent_results
            
            # 결과 값 정규화 (P, B, T로 변환)
            if game_data.latest_result:
                game_data.latest_result = self._normalize_result(game_data.latest_result)
            
            return game_data
            
        except Exception as e:
            self.logger.debug(f"JSON 게임 데이터 추출 오류: {e}")
            return None

    def _extract_game_data_from_text(self, message: str) -> Optional[GameData]:
        """텍스트 메시지에서 게임 정보 추출"""
        try:
            game_data = GameData()
            
            # 정규식 패턴으로 데이터 추출
            patterns = {
                'room_name': r'(?:room|table)[_\s]*[:\-]?\s*([^\s,]+)',
                'round_number': r'(?:round|game)[_\s]*[:\-]?\s*(\d+)',
                'latest_result': r'(?:result|winner)[_\s]*[:\-]?\s*([PBT])',
            }
            
            for attr, pattern in patterns.items():
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    if attr == 'round_number':
                        setattr(game_data, attr, int(value))
                    elif attr == 'latest_result':
                        setattr(game_data, attr, self._normalize_result(value))
                    else:
                        setattr(game_data, attr, value)
            
            return game_data if game_data.room_name or game_data.latest_result else None
            
        except Exception as e:
            self.logger.debug(f"텍스트 게임 데이터 추출 오류: {e}")
            return None

    def _extract_value_from_keys(self, data: dict, keys: List[str]):
        """여러 키에서 값 추출 시도"""
        for key in keys:
            if key in data:
                return data[key]
            
            # 중첩된 딕셔너리에서 찾기
            for sub_key, sub_value in data.items():
                if isinstance(sub_value, dict) and key in sub_value:
                    return sub_value[key]
        
        return None

    def _normalize_result(self, result: str) -> str:
        """결과 값을 P, B, T로 정규화"""
        try:
            result_str = str(result).upper()
            
            # 직접 매칭
            if result_str in ['P', 'B', 'T']:
                return result_str
            
            # 키워드 매칭
            if 'PLAYER' in result_str:
                return 'P'
            elif 'BANKER' in result_str:
                return 'B'
            elif 'TIE' in result_str:
                return 'T'
            
            # 숫자 매칭 (0=P, 1=B, 2=T 등)
            if result_str.isdigit():
                num = int(result_str)
                if num == 0:
                    return 'P'
                elif num == 1:
                    return 'B'
                elif num == 2:
                    return 'T'
            
            return result_str
            
        except Exception:
            return ""

    def _is_valid_game_data(self, game_data: GameData) -> bool:
        """유효한 게임 데이터인지 확인"""
        try:
            # 최소한의 필수 데이터가 있는지 확인
            has_room = bool(game_data.room_name)
            has_round = game_data.round_number > 0
            has_result = bool(game_data.latest_result)
            
            return has_room or has_round or has_result
            
        except Exception:
            return False

    def _is_new_game_data(self, game_data: GameData) -> bool:
        """새로운 게임 데이터인지 확인 (중복 방지)"""
        try:
            if not self.last_game_data:
                return True
            
            # 라운드 번호로 중복 확인
            if (game_data.round_number > 0 and 
                self.last_game_data.round_number > 0 and
                game_data.round_number <= self.last_game_data.round_number):
                return False
            
            # 결과가 같으면 중복일 가능성
            if (game_data.latest_result and 
                game_data.latest_result == self.last_game_data.latest_result and
                abs(game_data.timestamp - self.last_game_data.timestamp) < 5):
                return False
            
            return True
            
        except Exception:
            return True

    def start_connection(self, websocket_url: str):
        """웹소켓 연결 시작 (비동기)"""
        try:
            self.is_running = True
            self.logger.info("웹소켓 연결 시작 요청")
            
            # 새로운 이벤트 루프에서 실행
            self.connection_task = asyncio.create_task(self.connect_and_listen(websocket_url))
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 시작 오류: {e}")
            self.error_occurred.emit(f"연결 시작 실패: {str(e)}")

    def stop_connection(self):
        """웹소켓 연결 중지"""
        try:
            self.is_running = False
            
            if self.websocket:
                asyncio.create_task(self.websocket.close())
            
            if self.connection_task and not self.connection_task.done():
                self.connection_task.cancel()
            
            self.logger.info("웹소켓 연결 중지")
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 중지 오류: {e}")

    def get_connection_status(self) -> Dict[str, any]:
        """연결 상태 정보 반환"""
        return {
            'connected': self.is_connected,
            'running': self.is_running,
            'url': self.websocket_url,
            'message_count': self.message_count,
            'last_data_time': self.last_game_data.timestamp if self.last_game_data else None,
            'current_room': self.current_room_name
        }

    def set_current_room(self, room_name: str):
        """현재 방 이름 설정"""
        self.current_room_name = room_name
        self.logger.info(f"현재 방 설정: {room_name}")


class WebSocketThread(QThread):
    """웹소켓 연결을 별도 스레드에서 실행"""
    
    def __init__(self, websocket_client: WebSocketDirectClient, websocket_url: str):
        super().__init__()
        self.websocket_client = websocket_client
        self.websocket_url = websocket_url
        self.loop = None

    def run(self):
        """스레드 실행"""
        try:
            # 새로운 이벤트 루프 생성
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 웹소켓 연결 및 수신
            self.loop.run_until_complete(
                self.websocket_client.connect_and_listen(self.websocket_url)
            )
            
        except Exception as e:
            print(f"웹소켓 스레드 오류: {e}")
        finally:
            if self.loop:
                self.loop.close()


# 사용 예제
async def test_websocket_connection():
    """웹소켓 연결 테스트"""
    
    def on_game_data(game_data: GameData):
        print(f"게임 데이터 수신: {game_data.room_name} - {game_data.latest_result}")
    
    def on_connection_status(connected: bool):
        print(f"연결 상태: {'연결됨' if connected else '연결 안됨'}")
    
    def on_error(error: str):
        print(f"오류: {error}")
    
    # 클라이언트 생성
    client = WebSocketDirectClient()
    
    # 시그널 연결
    client.game_data_received.connect(on_game_data)
    client.connection_status_changed.connect(on_connection_status)
    client.error_occurred.connect(on_error)
    
    # 웹소켓 URL (실제 Evolution Gaming 웹소켓 URL로 교체 필요)
    websocket_url = "wss://babylonnanosoft.evo-games.com/public/lobby/socket/v2/s67kis2jngua2i4x?messageFormat=json&device=Desktop&features=opensAt%2CmultipleHero%2CshortThumbnails%2CskipInfosPublished%2Csmc%2CuniRouletteHistory%2CbacHistoryV2%2Cfilters%2CtableDecorations&instance=c25qsv-s67kis2jngua2i4x-&EVOSESSIONID=s67kis2jngua2i4xs67uznw5nf66hwfs21f8c005b8b9d86151aff3050660b36d067fae22ba86d02e&client_version=6.20250629.233738.52896-f43d60452b"
    
    # 연결 시작
    await client.connect_and_listen(websocket_url)


if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(test_websocket_connection())