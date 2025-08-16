"""
WebSocket 모니터링 및 연패방 검출
Evolution Gaming WebSocket 데이터를 파싱하여 서버와 통신
"""
import logging
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from services.prediction_client import PredictionClient

logger = logging.getLogger(__name__)

class WebSocketMonitor:
    """WebSocket 모니터링 및 서버 통신"""
    
    def __init__(self, driver):
        self.driver = driver
        self.prediction_client = PredictionClient()
        self.rooms_data = {}  # room_id -> room_data
        self.streak_rooms = []  # 연패방 목록
        self.min_streak = 3
        self.is_monitoring = False
        self._monitoring_task = None
        
    async def start_monitoring(self, min_streak: int = 3):
        """WebSocket 모니터링 시작"""
        self.min_streak = min_streak
        self.is_monitoring = True
        
        # JavaScript로 WebSocket 인터셉트 설치
        await self._install_websocket_interceptor()
        
        # 모니터링 태스크 시작
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"✅ WebSocket 모니터링 시작 (min_streak={min_streak})")
        
    async def stop_monitoring(self):
        """WebSocket 모니터링 중지"""
        self.is_monitoring = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
                
        logger.info("⏹️ WebSocket 모니터링 중지")
        
    async def _install_websocket_interceptor(self):
        """WebSocket 데이터 인터셉터 설치"""
        interceptor_script = """
        // WebSocket 데이터 수집기
        window.wsMessages = [];
        window.wsRooms = {};
        
        // 원본 WebSocket 저장
        const OriginalWebSocket = window.WebSocket;
        
        // WebSocket 프록시
        window.WebSocket = function(...args) {
            const ws = new OriginalWebSocket(...args);
            
            // 메시지 수신 후킹
            ws.addEventListener('message', function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    // Evolution Gaming 메시지 필터링
                    if (data.id && data.args) {
                        // 로비 테이블 정보
                        if (data.id === 'lobby.tables' || data.id === 'lobby.virtualTables') {
                            const tables = data.args.tables || data.args.virtualTables || [];
                            
                            tables.forEach(table => {
                                const roomId = table.tableId || table.id;
                                const roomName = table.name || table.tableName;
                                
                                // 바카라 테이블만 필터링
                                if (roomName && (roomName.includes('바카라') || roomName.includes('Baccarat'))) {
                                    // 결과 데이터 파싱
                                    const results = [];
                                    if (table.history && table.history.results) {
                                        table.history.results.forEach(r => {
                                            if (r.winner === 'Player') results.push('P');
                                            else if (r.winner === 'Banker') results.push('B');
                                            else if (r.winner === 'Tie') results.push('T');
                                        });
                                    }
                                    
                                    // 방 데이터 저장
                                    window.wsRooms[roomId] = {
                                        roomId: roomId,
                                        roomName: roomName,
                                        results: results,
                                        gameCount: results.length,
                                        lastUpdate: new Date().toISOString()
                                    };
                                }
                            });
                        }
                        
                        // 게임 결과 업데이트
                        if (data.id === 'baccarat.roadmap' || data.id === 'game.result') {
                            const roomId = data.args.tableId || data.args.gameId;
                            const result = data.args.winner || data.args.result;
                            
                            if (roomId && window.wsRooms[roomId]) {
                                if (result === 'Player') window.wsRooms[roomId].results.push('P');
                                else if (result === 'Banker') window.wsRooms[roomId].results.push('B');
                                else if (result === 'Tie') window.wsRooms[roomId].results.push('T');
                                
                                window.wsRooms[roomId].gameCount = window.wsRooms[roomId].results.length;
                                window.wsRooms[roomId].lastUpdate = new Date().toISOString();
                            }
                        }
                    }
                    
                    // 메시지 저장 (디버깅용)
                    window.wsMessages.push({
                        time: new Date().toISOString(),
                        data: data
                    });
                    
                    // 최대 100개만 유지
                    if (window.wsMessages.length > 100) {
                        window.wsMessages.shift();
                    }
                    
                } catch(e) {
                    // JSON 파싱 오류 무시
                }
            });
            
            return ws;
        };
        
        console.log('✅ WebSocket 인터셉터 설치 완료');
        """
        
        try:
            self.driver.execute_script(interceptor_script)
            logger.info("✅ WebSocket 인터셉터 설치 성공")
        except Exception as e:
            logger.error(f"WebSocket 인터셉터 설치 오류: {e}")
            
    async def _monitoring_loop(self):
        """모니터링 루프"""
        while self.is_monitoring:
            try:
                # WebSocket에서 수집된 방 데이터 가져오기
                rooms_data = await self._get_rooms_from_websocket()
                
                if rooms_data:
                    # 연패방 분석 및 서버 통신
                    await self._analyze_streak_rooms(rooms_data)
                    
                await asyncio.sleep(2)  # 2초마다 체크
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                await asyncio.sleep(5)
                
    async def _get_rooms_from_websocket(self) -> Dict[str, Any]:
        """WebSocket에서 수집된 방 데이터 가져오기"""
        try:
            script = "return window.wsRooms || {};"
            rooms_data = self.driver.execute_script(script)
            return rooms_data
        except Exception as e:
            logger.error(f"WebSocket 데이터 가져오기 오류: {e}")
            return {}
            
    async def _analyze_streak_rooms(self, rooms_data: Dict[str, Any]):
        """연패방 분석 및 서버 통신"""
        try:
            new_streak_rooms = []
            
            for room_id, room_info in rooms_data.items():
                room_name = room_info.get('roomName', '')
                results = room_info.get('results', [])
                game_count = room_info.get('gameCount', 0)
                
                # 게임 수 체크 (15-64)
                if game_count < 15 or game_count > 64:
                    continue
                    
                # 결과가 충분한지 체크
                if len(results) < 5:
                    continue
                    
                # 서버에 연패 계산 요청
                streak_response = await self.prediction_client.calculate_streak(
                    room_id=room_id,
                    room_name=room_name,
                    results=results
                )
                
                if streak_response:
                    current_streak = streak_response.get('current_streak', 0)
                    streak_type = streak_response.get('streak_type', '')
                    
                    # min_streak 이상인 경우 연패방으로 등록
                    if current_streak >= self.min_streak:
                        room_data = {
                            'room_id': room_id,
                            'room_name': room_name,
                            'current_streak': current_streak,
                            'streak_type': streak_type,
                            'game_count': game_count,
                            'results': results,
                            'last_update': room_info.get('lastUpdate')
                        }
                        
                        new_streak_rooms.append(room_data)
                        
                        logger.info(f"🎯 연패방 발견: {room_name} ({current_streak}연패, 타입: {streak_type})")
                        
                        # 서버에 검증 요청
                        verify_response = await self.prediction_client.verify_and_predict(
                            room_id=room_id,
                            current_results=results,
                            expected_streak=current_streak
                        )
                        
                        if verify_response and verify_response.get('status') == 'success':
                            room_data['verified'] = True
                            room_data['next_prediction'] = verify_response.get('next_prediction')
                            logger.info(f"✅ 연패방 검증 완료: {room_name}, 다음 예측: {room_data['next_prediction']}")
                        else:
                            room_data['verified'] = False
                            logger.warning(f"⚠️ 연패방 검증 실패: {room_name}")
            
            # 연패방 목록 업데이트
            self.streak_rooms = new_streak_rooms
            self.rooms_data = rooms_data
            
            if new_streak_rooms:
                logger.info(f"📊 총 {len(new_streak_rooms)}개 연패방 감지")
                
        except Exception as e:
            logger.error(f"연패방 분석 오류: {e}")
            
    def get_streak_rooms(self) -> List[Dict[str, Any]]:
        """현재 감지된 연패방 목록 반환"""
        return self.streak_rooms
        
    def get_best_streak_room(self) -> Optional[Dict[str, Any]]:
        """가장 좋은 연패방 반환 (검증된 방 우선)"""
        if not self.streak_rooms:
            return None
            
        # 검증된 방 우선, 연패 수가 높은 순으로 정렬
        sorted_rooms = sorted(
            self.streak_rooms,
            key=lambda x: (x.get('verified', False), x.get('current_streak', 0)),
            reverse=True
        )
        
        return sorted_rooms[0] if sorted_rooms else None
        
    async def get_room_prediction(self, room_id: str) -> Optional[str]:
        """특정 방의 예측값 가져오기"""
        try:
            room_data = self.rooms_data.get(room_id)
            if not room_data:
                return None
                
            results = room_data.get('results', [])
            if len(results) < 5:
                return None
                
            # 서버에 예측 요청
            prediction = await self.prediction_client.get_prediction(room_id, results)
            return prediction
            
        except Exception as e:
            logger.error(f"예측값 가져오기 오류: {e}")
            return None
            
    def get_monitoring_status(self) -> Dict[str, Any]:
        """모니터링 상태 반환"""
        return {
            'is_monitoring': self.is_monitoring,
            'total_rooms': len(self.rooms_data),
            'streak_rooms': len(self.streak_rooms),
            'min_streak': self.min_streak,
            'best_room': self.get_best_streak_room()
        }