import time
import logging
import asyncio
from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import QObject, pyqtSlot

# 기존 TradingManager 임포트
from services.hybrid_realtime_service import HybridRealtimeService
from utils.trading_manager import TradingManager

# 추가 서# utils/enhanced_trading_manager.py 수정 부분
"""
향상된 하이브리드 TradingManager - 웹소켓 데이터 수집 연동
- WebSocketDataCollector 통합
- 실시간 데이터 수집 및 하이브리드 서비스 연동
- 논블로킹 모니터링
"""

# 기존 클래스에 추가할 메서드들과 수정사항

class EnhancedTradingManager(TradingManager):
    """하이브리드 기능이 추가된 TradingManager - 웹소켓 데이터 수집 포함"""
    
    def __init__(self, main_window, logger=None):
        super().__init__(main_window, logger)
        
        # 웹소켓 데이터 수집기 초기화
        self.websocket_collector = None
        
        # 데이터 수집 상태
        self.data_collection_active = False
        self.last_collected_data = None
        self.collection_stats = {}
        
        self.logger.info("향상된 하이브리드 TradingManager 초기화 (웹소켓 수집 포함)")

    async def start_enhanced_trading(self):
        """향상된 하이브리드 자동매매 시작 - 웹소켓 데이터 수집 포함"""
        try:
            self.logger.info("🚀 향상된 하이브리드 자동매매 시작 (웹소켓 수집 포함)")
            
            # 기본 검증
            if not self.helpers.validate_trading_prerequisites():
                return False
            
            # 웹소켓 URL 추출
            websocket_url = self._extract_websocket_async()
            if not websocket_url:
                QMessageBox.critical(
                    self.main_window,
                    "웹소켓 추출 실패",
                    "웹소켓 URL을 추출할 수 없습니다.\n에볼루션 게임을 시작해주세요."
                )
                return False
            
            # 하이브리드 서비스 초기화
            self.hybrid_service = HybridRealtimeService(
                self.server_client, 
                self.user_id, 
                self.logger
            )
            
            # 웹소켓 데이터 수집기 초기화
            self._init_websocket_collector()
            
            # 시그널 연결
            self._connect_hybrid_signals()
            self._connect_collector_signals()
            
            # 하이브리드 모니터링 시작
            success = await self.hybrid_service.start_monitoring(websocket_url)
            if not success:
                QMessageBox.warning(
                    self.main_window,
                    "모니터링 시작 실패",
                    "하이브리드 모니터링을 시작할 수 없습니다."
                )
                return False
            
            # 웹소켓 데이터 수집 시작
            if not self._start_websocket_collection():
                self.logger.warning("웹소켓 데이터 수집 시작 실패, 하이브리드 모니터링만 진행")
            
            # 기본 자동매매 상태 설정
            self.is_trading_active = True
            self.server_monitoring_active = True
            self.data_collection_active = True
            
            # UI 업데이트
            self._update_ui_for_trading_start()
            
            # 초기 방 검색 시작
            self._start_initial_room_search()
            
            self.logger.info("✅ 향상된 하이브리드 자동매매 시작 완료 (웹소켓 수집 포함)")
            return True
            
        except Exception as e:
            self.logger.error(f"향상된 자동매매 시작 오류: {e}")
            return False

    def _init_websocket_collector(self):
        """웹소켓 데이터 수집기 초기화"""
        try:
            from services.websocket_data_collector import WebSocketDataCollector
            
            self.websocket_collector = WebSocketDataCollector(
                devtools=self.devtools,
                hybrid_service=self.hybrid_service,
                logger=self.logger
            )
            
            self.logger.info("웹소켓 데이터 수집기 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 데이터 수집기 초기화 실패: {e}")
            self.websocket_collector = None

    def _connect_collector_signals(self):
        """웹소켓 수집기 시그널 연결"""
        try:
            if not self.websocket_collector:
                return
            
            # 데이터 수집 시그널
            self.websocket_collector.data_collected.connect(self._on_websocket_data_collected)
            
            # 연결 상태 변경 시그널
            self.websocket_collector.connection_status_changed.connect(self._on_collection_status_changed)
            
            # 오류 발생 시그널
            self.websocket_collector.error_occurred.connect(self._on_collection_error)
            
            self.logger.info("웹소켓 수집기 시그널 연결 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 수집기 시그널 연결 오류: {e}")

    def _start_websocket_collection(self):
        """웹소켓 데이터 수집 시작"""
        try:
            if not self.websocket_collector:
                self.logger.warning("웹소켓 데이터 수집기가 없습니다.")
                return False
            
            # 하이브리드 서비스 연결
            self.websocket_collector.set_hybrid_service(self.hybrid_service)
            
            # 수집 시작
            success = self.websocket_collector.start_collection()
            
            if success:
                self.logger.info("✅ 웹소켓 데이터 수집 시작 완료")
                return True
            else:
                self.logger.warning("❌ 웹소켓 데이터 수집 시작 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"웹소켓 데이터 수집 시작 오류: {e}")
            return False

    @pyqtSlot(dict)
    def _on_websocket_data_collected(self, data):
        """웹소켓 데이터 수집 시 처리"""
        try:
            self.last_collected_data = data
            
            # 데이터 분석 및 처리
            room_name = data.get('room_name')
            latest_result = data.get('latest_result')
            round_number = data.get('round')
            
            if room_name:
                self.logger.debug(f"웹소켓 데이터 수집: {room_name} - {latest_result} (라운드: {round_number})")
            
            # 필요시 추가 처리 로직
            self._process_collected_websocket_data(data)
            
        except Exception as e:
            self.logger.error(f"웹소켓 데이터 처리 오류: {e}")

    @pyqtSlot(bool)
    def _on_collection_status_changed(self, is_active):
        """데이터 수집 상태 변경 처리"""
        try:
            self.data_collection_active = is_active
            status_text = "활성" if is_active else "비활성"
            self.logger.info(f"웹소켓 데이터 수집 상태 변경: {status_text}")
            
            # UI 업데이트 (필요시)
            if hasattr(self.main_window, 'update_collection_status'):
                self.main_window.update_collection_status(is_active)
                
        except Exception as e:
            self.logger.error(f"수집 상태 변경 처리 오류: {e}")

    @pyqtSlot(str)
    def _on_collection_error(self, error_message):
        """데이터 수집 오류 처리"""
        try:
            self.logger.warning(f"웹소켓 데이터 수집 오류: {error_message}")
            
            # 심각한 오류인 경우 수집 재시작 시도
            if "critical" in error_message.lower() or "connection" in error_message.lower():
                self.logger.info("심각한 수집 오류 감지 - 재시작 시도")
                self._restart_websocket_collection()
                
        except Exception as e:
            self.logger.error(f"수집 오류 처리 중 오류: {e}")

    def _process_collected_websocket_data(self, data):
        """수집된 웹소켓 데이터 추가 처리"""
        try:
            # 방 이름 매칭 확인
            if self.current_room_name and data.get('room_name'):
                if self.current_room_name in data.get('room_name', ''):
                    # 현재 방의 데이터인 경우 우선 처리
                    self._process_current_room_data(data)
            
            # 새로운 조건 방 감지
            if self._is_potential_target_room(data):
                self.logger.info(f"잠재적 목표 방 감지: {data.get('room_name', 'Unknown')}")
                # 하이브리드 서비스에서 이미 처리되므로 추가 로직 불필요
                
        except Exception as e:
            self.logger.error(f"웹소켓 데이터 추가 처리 오류: {e}")

    def _process_current_room_data(self, data):
        """현재 방의 웹소켓 데이터 처리"""
        try:
            latest_result = data.get('latest_result')
            round_number = data.get('round')
            
            if latest_result and round_number:
                # 게임 상태와 동기화
                if hasattr(self, 'game_monitoring_service'):
                    # 웹소켓 데이터로 게임 상태 업데이트 보조
                    self.logger.debug(f"현재 방 웹소켓 데이터: 라운드 {round_number}, 결과 {latest_result}")
                    
        except Exception as e:
            self.logger.error(f"현재 방 데이터 처리 오류: {e}")

    def _is_potential_target_room(self, data):
        """잠재적 목표 방인지 확인"""
        try:
            room_name = data.get('room_name', '')
            latest_result = data.get('latest_result')
            
            # 바카라 방인지 확인
            if not any(keyword in room_name.lower() for keyword in ['baccarat', '바카라']):
                return False
            
            # 결과가 있는지 확인
            if latest_result not in ['P', 'B']:
                return False
            
            # 추가 조건 확인 가능
            return True
            
        except Exception as e:
            self.logger.error(f"목표 방 확인 오류: {e}")
            return False

    def _restart_websocket_collection(self):
        """웹소켓 데이터 수집 재시작"""
        try:
            if not self.websocket_collector:
                return
            
            self.logger.info("웹소켓 데이터 수집 재시작 시도")
            
            # 기존 수집 중지
            self.websocket_collector.stop_collection()
            
            # 잠시 대기
            time.sleep(2)
            
            # 수집 재시작
            success = self.websocket_collector.start_collection()
            
            if success:
                self.logger.info("✅ 웹소켓 데이터 수집 재시작 성공")
            else:
                self.logger.warning("❌ 웹소켓 데이터 수집 재시작 실패")
                
        except Exception as e:
            self.logger.error(f"웹소켓 수집 재시작 오류: {e}")

    async def stop_enhanced_trading(self):
        """향상된 자동매매 중지 - 웹소켓 수집 포함"""
        try:
            self.logger.info("향상된 자동매매 중지 중... (웹소켓 수집 포함)")
            
            # 기본 중지 프로세스
            self.stop_all_processes = True
            self.is_trading_active = False
            self.data_collection_active = False
            
            # 웹소켓 데이터 수집 중지
            if self.websocket_collector:
                self.websocket_collector.stop_collection()
                self.logger.info("웹소켓 데이터 수집 중지 완료")
            
            # 하이브리드 서비스 중지
            if self.hybrid_service:
                await self.hybrid_service.stop_monitoring()
                self.hybrid_service = None
                self.logger.info("하이브리드 서비스 중지 완료")
            
            # 기본 서비스들 중지
            if hasattr(self, 'server_client'):
                self.server_client.stop_monitoring(self.user_id)
            
            # UI 상태 복원
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)
            self.main_window.update_button_styles()
            
            # 현재 방에서 나가기
            if self.current_room_name:
                self._quick_exit_current_room()
            
            self.logger.info("향상된 자동매매 중지 완료 (웹소켓 수집 포함)")
            
        except Exception as e:
            self.logger.error(f"향상된 자동매매 중지 오류: {e}")

    def get_enhanced_status(self) -> dict:
        """향상된 상태 정보 반환 - 웹소켓 수집 포함"""
        try:
            base_status = super().get_current_status()
            
            # 웹소켓 수집 통계
            collection_stats = {}
            if self.websocket_collector:
                collection_stats = self.websocket_collector.get_collection_stats()
            
            enhanced_status = {
                **base_status,
                "hybrid_monitoring": self.hybrid_service.is_monitoring if self.hybrid_service else False,
                "websocket_collection": self.data_collection_active,
                "collection_stats": collection_stats,
                "last_collected_data": self.last_collected_data,
                "immediate_entry_mode": self.immediate_entry_mode,
                "target_room": self.current_target_room,
                "last_entry_attempt": self.last_room_entry_attempt,
                "hybrid_stats": self.hybrid_service.get_monitoring_stats() if self.hybrid_service else {}
            }
            
            return enhanced_status
            
        except Exception as e:
            self.logger.error(f"향상된 상태 정보 수집 오류: {e}")
            return {"error": str(e)}

    def force_websocket_data_collection(self):
        """수동 웹소켓 데이터 수집 트리거"""
        try:
            if not self.websocket_collector:
                self.logger.warning("웹소켓 데이터 수집기가 없습니다.")
                return False
            
            return self.websocket_collector.force_collect_data()
            
        except Exception as e:
            self.logger.error(f"수동 웹소켓 데이터 수집 오류: {e}")
            return False

    async def emergency_stop_enhanced(self):
        """비상 정지 - 향상된 버전 (웹소켓 수집 포함)"""
        try:
            self.logger.warning("🚨 향상된 비상 정지 실행 (웹소켓 수집 포함)")
            
            # 모든 플래그 즉시 설정
            self.stop_all_processes = True
            self.is_trading_active = False
            self.immediate_entry_mode = False
            self.data_collection_active = False
            
            # 웹소켓 데이터 수집 즉시 중지
            if self.websocket_collector:
                try:
                    self.websocket_collector.stop_collection()
                except:
                    pass
                self.websocket_collector = None
            
            # 하이브리드 서비스 즉시 중지
            if self.hybrid_service:
                try:
                    await self.hybrid_service.stop_monitoring()
                except:
                    pass
                self.hybrid_service = None
            
            # 기본 비상 정지 실행
            self.emergency_stop()
            
            self.logger.info("향상된 비상 정지 완료 (웹소켓 수집 포함)")
            
        except Exception as e:
            self.logger.error(f"향상된 비상 정지 중 오류: {e}")

    def __del__(self):
        """소멸자 - 리소스 정리 (웹소켓 수집기 포함)"""
        try:
            # 웹소켓 데이터 수집기 정리
            if hasattr(self, 'websocket_collector') and self.websocket_collector:
                try:
                    self.websocket_collector.stop_collection()
                except:
                    pass
                self.websocket_collector = None
            
            # 하이브리드 서비스 정리
            if hasattr(self, 'hybrid_service') and self.hybrid_service:
                # 비동기 정리는 여기서 할 수 없으므로 기본 정리만
                self.hybrid_service = None
            
            # 부모 클래스의 소멸자 호출
            super().__del__()
            
        except:
            pass


# 추가: TradingManager 클래스에 웹소켓 수집 연동 메서드들

def integrate_websocket_collection_to_trading_manager():
    """기존 TradingManager에 웹소켓 수집 기능을 통합하는 메서드들"""
    
    def init_websocket_collection(self):
        """TradingManager에 웹소켓 수집 기능 추가"""
        try:
            from services.websocket_data_collector import WebSocketDataCollector
            
            # 웹소켓 수집기가 없으면 생성
            if not hasattr(self, 'websocket_collector') or not self.websocket_collector:
                self.websocket_collector = WebSocketDataCollector(
                    devtools=self.devtools,
                    hybrid_service=getattr(self, 'hybrid_service', None),
                    logger=self.logger
                )
                
                # 시그널 연결
                self.websocket_collector.data_collected.connect(self._on_websocket_data_received)
                self.websocket_collector.connection_status_changed.connect(self._on_websocket_status_changed)
                self.websocket_collector.error_occurred.connect(self._on_websocket_error)
                
                self.logger.info("TradingManager에 웹소켓 수집 기능 통합 완료")
                return True
            else:
                self.logger.info("웹소켓 수집기가 이미 존재합니다.")
                return True
                
        except Exception as e:
            self.logger.error(f"웹소켓 수집 기능 통합 오류: {e}")
            return False
    
    def start_websocket_monitoring(self):
        """웹소켓 모니터링 시작"""
        try:
            if not hasattr(self, 'websocket_collector') or not self.websocket_collector:
                if not self.init_websocket_collection():
                    return False
            
            # 하이브리드 서비스 연결 (있는 경우)
            if hasattr(self, 'hybrid_service') and self.hybrid_service:
                self.websocket_collector.set_hybrid_service(self.hybrid_service)
            
            # 수집 시작
            return self.websocket_collector.start_collection()
            
        except Exception as e:
            self.logger.error(f"웹소켓 모니터링 시작 오류: {e}")
            return False
    
    def stop_websocket_monitoring(self):
        """웹소켓 모니터링 중지"""
        try:
            if hasattr(self, 'websocket_collector') and self.websocket_collector:
                self.websocket_collector.stop_collection()
                self.logger.info("웹소켓 모니터링 중지 완료")
                
        except Exception as e:
            self.logger.error(f"웹소켓 모니터링 중지 오류: {e}")
    
    def _on_websocket_data_received(self, data):
        """웹소켓 데이터 수신 처리"""
        try:
            # 기본적인 데이터 로깅
            room_name = data.get('room_name', 'Unknown')
            latest_result = data.get('latest_result')
            
            if latest_result:
                self.logger.debug(f"웹소켓 데이터 수신: {room_name} - {latest_result}")
            
            # 추가 처리가 필요한 경우 여기에 구현
            
        except Exception as e:
            self.logger.error(f"웹소켓 데이터 수신 처리 오류: {e}")
    
    def _on_websocket_status_changed(self, is_active):
        """웹소켓 연결 상태 변경 처리"""
        try:
            status = "활성" if is_active else "비활성"
            self.logger.info(f"웹소켓 수집 상태 변경: {status}")
            
        except Exception as e:
            self.logger.error(f"웹소켓 상태 변경 처리 오류: {e}")
    
    def _on_websocket_error(self, error_message):
        """웹소켓 오류 처리"""
        try:
            self.logger.warning(f"웹소켓 수집 오류: {error_message}")
            
        except Exception as e:
            self.logger.error(f"웹소켓 오류 처리 중 오류: {e}")
    
    # TradingManager 클래스에 메서드들을 동적으로 추가
    import types
    from utils.trading_manager import TradingManager
    
    TradingManager.init_websocket_collection = init_websocket_collection
    TradingManager.start_websocket_monitoring = start_websocket_monitoring
    TradingManager.stop_websocket_monitoring = stop_websocket_monitoring
    TradingManager._on_websocket_data_received = _on_websocket_data_received
    TradingManager._on_websocket_status_changed = _on_websocket_status_changed
    TradingManager._on_websocket_error = _on_websocket_error

# 모듈 로드 시 통합 실행
if __name__ != "__main__":
    try:
        integrate_websocket_collection_to_trading_manager()
    except Exception as e:
        print(f"웹소켓 수집 기능 통합 중 오류: {e}")