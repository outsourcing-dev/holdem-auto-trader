# ==================== 3. utils/trading_manager/websocket_manager.py ====================

import time
import logging


class WebSocketManager:
    """웹소켓 관리 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger
        self.websocket_service = None
        
    def start_websocket_service(self) -> bool:
        """연패 감지 웹소켓 서비스 시작"""
        try:
            self.logger.info("🎯 연패 감지 웹소켓 서비스 시작")
            
            # 웹소켓 URL 추출
            websocket_urls = self._extract_websocket_urls_for_logging()
            
            if not websocket_urls:
                self.logger.error("❌ 웹소켓 URL을 찾을 수 없습니다")
                return False
            
            websocket_url = websocket_urls[0]
            self.logger.info(f"📡 사용할 웹소켓 URL: {websocket_url[:100]}...")
            
            # 연패 감지 서비스 생성
            from services.websocket_hybrid_service import WebSocketHybridService
            self.websocket_service = WebSocketHybridService(
                devtools=self.tm.devtools,
                logger=self.logger
            )
            
            # 호환성을 위한 변수 설정
            self.tm.websocket_interceptor = self.websocket_service
            
            # 시그널 연결
            self._connect_websocket_signals()
            
            # 웹소켓 연결 시작
            if self.websocket_service.start_websocket_connection(websocket_url):
                self.tm.websocket_intercepting = True
                self.logger.info("✅ 연패 감지 웹소켓 서비스 시작 성공")
                return True
            else:
                self.logger.error("❌ 웹소켓 연결 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"연패 감지 웹소켓 서비스 시작 오류: {e}")
            return False

    def stop_websocket_service(self):
        """웹소켓 서비스 중지"""
        try:
            if self.websocket_service:
                self.websocket_service.stop_websocket_connection()
                self.websocket_service = None
            
            self.tm.websocket_interceptor = None
            self.logger.info("웹소켓 서비스 중지 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 서비스 중지 오류: {e}")

    def _extract_websocket_urls_for_logging(self) -> list:
        """웹소켓 URL 추출"""
        try:
            self.logger.info("⚡ 웹소켓 URL 추출 시작")
            start_time = time.time()
            
            from services.websocket_parser import WebSocketParser
            ws_parser = WebSocketParser(self.tm.devtools, self.logger)
            
            websocket_urls = []
            try:
                websocket_urls = ws_parser.auto_detect_websocket_urls()
            except Exception as e:
                self.logger.warning(f"웹소켓 URL 추출 중 오류: {e}")
                websocket_urls = []
            
            elapsed_time = time.time() - start_time
            
            if websocket_urls:
                first_url = websocket_urls[0]
                self.logger.info(f"📡 WebSocket 연결 감지: {first_url}")
                self.logger.info(f"✅ 웹소켓 URL 추출 완료 ({elapsed_time:.1f}초, {len(websocket_urls)}개 발견)")
            else:
                self.logger.warning(f"❌ 웹소켓 URL 추출 실패 ({elapsed_time:.1f}초)")
            
            if hasattr(ws_parser, 'shutdown'):
                ws_parser.shutdown()
            
            return websocket_urls
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 추출 오류: {e}")
            return []

    def _disconnect_websocket_signals(self):
        """기존 웹소켓 시그널 연결 해제"""
        try:
            if self.websocket_service:
                # 🔥 모든 시그널 연결 해제
                try:
                    self.websocket_service.game_data_received.disconnect()
                    self.websocket_service.connection_status_changed.disconnect()
                    self.websocket_service.error_occurred.disconnect()
                    self.websocket_service.streak_room_found.disconnect()
                    self.websocket_service.room_entry_requested.disconnect()
                    self.logger.info("🔌 기존 웹소켓 시그널 연결 해제 완료")
                except Exception as e:
                    self.logger.debug(f"시그널 해제 중 오류 (무시): {e}")
        except Exception as e:
            self.logger.debug(f"시그널 해제 오류: {e}")

    def _connect_websocket_signals(self):
        """웹소켓 서비스 시그널 연결"""
        try:
            if not self.websocket_service:
                return
                
            # 🔥 기존 시그널 먼저 해제
            self._disconnect_websocket_signals()
                
            # 게임 데이터 수신 시그널
            self.websocket_service.game_data_received.connect(
                self.tm.game_processor.on_game_data_received
            )
            
            # 연결 상태 변경 시그널
            self.websocket_service.connection_status_changed.connect(
                self._on_connection_status_changed
            )
            
            # 오류 발생 시그널
            self.websocket_service.error_occurred.connect(
                self._on_websocket_error
            )
            
            # 연패 방 발견 시그널
            self.websocket_service.streak_room_found.connect(
                self.tm.streak_handler.on_streak_room_found
            )
            
            # 방 입장 요청 시그널
            self.websocket_service.room_entry_requested.connect(
                self.tm.streak_handler.on_room_entry_requested
            )
            
            self.logger.info("✅ 연패 감지 웹소켓 시그널 연결 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 시그널 연결 오류: {e}")

    def _on_connection_status_changed(self, connected: bool):
        """웹소켓 연결 상태 변경 처리"""
        try:
            status_text = "연결됨" if connected else "연결 끊김"
            self.logger.info(f"🔌 연패 감지 웹소켓 상태 변경: {status_text}")
            
            if connected:
                self.logger.info("✅ 실시간 연패 감지 시작")
                
                # 🔥 연결 성공 후 현재 설정값으로 연패 기준 업데이트
                if hasattr(self.tm, 'settings_manager') and self.websocket_service:
                    min_streak = self.tm.settings_manager.get_min_streak()
                    self.websocket_service.update_streak_threshold(min_streak)
                    self.logger.info(f"🎯 웹소켓 서비스 연패 기준 설정: {min_streak}")
            else:
                if self.tm.is_trading_active:
                    self.logger.warning("⚠️ 자동 매매 중 연결 끊김")
                    
        except Exception as e:
            self.logger.error(f"연결 상태 변경 처리 오류: {e}")

    def _on_websocket_error(self, error_message: str):
        """웹소켓 오류 발생 시 처리"""
        try:
            self.logger.error(f"🚨 연패 감지 웹소켓 오류: {error_message}")
            
            if "connection" in error_message.lower() or "timeout" in error_message.lower():
                self.logger.warning("🔄 웹소켓 연결 문제 - 재연결 시도")
                # 🔥 자동 매매 중지 대신 재연결 시도
                if self.tm.is_trading_active:
                    self.force_reconnect_websocket()
                
        except Exception as e:
            self.logger.error(f"웹소켓 오류 처리 중 오류: {e}")

    def get_interceptor_status(self) -> dict:
        """웹소켓 서비스 상태 정보 반환"""
        try:
            if self.websocket_service:
                js_status = self.websocket_service.get_connection_status()
                
                return {
                    'is_intercepting': js_status.get('active', False),
                    'performance_logs_enabled': True,
                    'cdp_session_active': js_status.get('connected', False),
                    'websocket_connections': 1 if js_status.get('connected') else 0,
                    'active_connections': 1 if js_status.get('connected') else 0,
                    'message_buffer_size': js_status.get('total_messages', 0),
                    'processed_messages': js_status.get('total_messages', 0),
                    'server_sent_count': js_status.get('sent_to_server', 0),
                    'filtered_room_count': js_status.get('filtered_room_messages', 0),
                    'target_streak_rooms': len(self.tm.target_streak_rooms),
                    'current_target_room': self.tm.current_target_room,
                    'room_entry_in_progress': self.tm.room_entry_in_progress
                }
            else:
                return {
                    'is_intercepting': False,
                    'performance_logs_enabled': False,
                    'cdp_session_active': False,
                    'websocket_connections': 0,
                    'active_connections': 0,
                    'message_buffer_size': 0,
                    'processed_messages': 0,
                    'server_sent_count': 0,
                    'filtered_room_count': 0,
                    'target_streak_rooms': 0,
                    'current_target_room': None,
                    'room_entry_in_progress': False
                }
        except Exception as e:
            self.logger.error(f"웹소켓 상태 확인 오류: {e}")
            return {'error': str(e)}

    def force_collect_data(self):
        """수동 데이터 수집 트리거"""
        try:
            if self.websocket_service and self.tm.websocket_intercepting:
                status = self.websocket_service.get_connection_status()
                self.logger.info(f"🔍 수동 데이터 수집: {status}")
                return status.get('connected', False)
            else:
                self.logger.warning("웹소켓 서비스가 활성화되지 않음")
                return False
        except Exception as e:
            self.logger.error(f"수동 데이터 수집 오류: {e}")
            return False

    def _verify_devtools_session(self) -> bool:
        """DevTools 세션 유효성 검증"""
        try:
            if not self.tm.devtools or not self.tm.devtools.driver:
                return False
            
            # 간단한 JavaScript 실행으로 세션 확인
            result = self.tm.devtools.driver.execute_script("return document.readyState")
            self.logger.debug(f"🔍 DevTools 세션 상태: {result}")
            return result in ["complete", "interactive"]
        except Exception as e:
            self.logger.warning(f"⚠️ DevTools 세션 확인 실패: {e}")
            return False

    def force_reconnect_websocket(self):
        """웹소켓 강제 재연결 - URL 재추출 포함"""
        try:
            self.logger.info("🔄 웹소켓 재연결 및 URL 재추출 시작")
            
            # 🔥 DevTools 세션 유효성 먼저 확인
            if not self._verify_devtools_session():
                self.logger.error("❌ DevTools 세션이 유효하지 않음 - 재연결 중단")
                return False
            
            # 🔥 기존 시그널 연결 해제
            self._disconnect_websocket_signals()
            
            # 🔥 기존 연결 완전 정리
            if self.websocket_service:
                self.websocket_service.stop_websocket_connection()
                self.websocket_service = None
                self.tm.websocket_interceptor = None
                self.logger.info("🗑️ 기존 웹소켓 서비스 정리 완료")
            
            # 🔥 JavaScript 환경 정리
            self._cleanup_javascript_environment()
            
            # 🔥 로비 복귀 확인 대기 (3초)
            import time
            time.sleep(3)
            self.logger.info("⏰ 로비 안정화 대기 완료")
            
            # 🔥 새로운 웹소켓 URL 추출
            new_websocket_urls = self._extract_websocket_urls_for_logging()
            
            if not new_websocket_urls:
                self.logger.error("❌ 새로운 웹소켓 URL 추출 실패")
                if self.tm.is_trading_active:
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(10000, self.force_reconnect_websocket)
                    self.logger.info("⏰ 10초 후 웹소켓 재연결 재시도")
                return False
                
            new_websocket_url = new_websocket_urls[0]
            self.logger.info(f"📡 새로운 웹소켓 URL 추출 성공: {new_websocket_url[:50]}...")
            
            # 🔥 새로운 서비스로 재시작
            success = self.start_websocket_service()
            
            if not success and self.tm.is_trading_active:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(10000, self.force_reconnect_websocket)
                self.logger.info("⏰ 10초 후 웹소켓 재연결 재시도")
                
            return success
                
        except Exception as e:
            self.logger.error(f"웹소켓 재연결 오류: {e}")
            if self.tm.is_trading_active:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(10000, self.force_reconnect_websocket)
                self.logger.info("⏰ 10초 후 웹소켓 재연결 재시도 (오류 발생)")
            return False

    def _cleanup_javascript_environment(self):
        """JavaScript 환경 정리"""
        try:
            cleanup_script = """
            // 기존 웹소켓 및 인터셉터 정리
            if (window.gameWebSocket) {
                try {
                    window.gameWebSocket.close();
                    window.gameWebSocket = null;
                } catch(e) {}
            }
            if (window.wsServerAnalysis) {
                window.wsServerAnalysis = null;
            }
            if (window.sendServerAnalysisResultToPython) {
                window.sendServerAnalysisResultToPython = null;
            }
            console.log('🧹 JavaScript 환경 정리 완료');
            """
            
            self.tm.devtools.driver.execute_script(cleanup_script)
            self.logger.info("🧹 JavaScript 환경 정리 완료")
            
        except Exception as e:
            self.logger.debug(f"JavaScript 정리 오류 (무시): {e}")

    def debug_service_status(self):
        """디버그용 서비스 상태 출력"""
        try:
            if self.websocket_service:
                self.logger.info("🔍 연패 감지 서비스 디버그 상태:")
                
                status = self.websocket_service.get_connection_status()
                for key, value in status.items():
                    self.logger.info(f"  - {key}: {value}")
                
                self.logger.info(f"🏠 연패 방 관리 상태:")
                self.logger.info(f"  - 타겟 연패 방: {len(self.tm.target_streak_rooms)}개")
                self.logger.info(f"  - 현재 타겟 방: {self.tm.current_target_room}")
                self.logger.info(f"  - 방 입장 진행 중: {self.tm.room_entry_in_progress}")
                
                server_connected = bool(self.tm.server_client and self.tm.server_client.get_server_status())
                self.logger.info(f"📡 서버 연결 상태: {server_connected}")
            else:
                self.logger.info("  - 웹소켓 서비스 인스턴스 없음")
        except Exception as e:
            self.logger.error(f"디버그 상태 출력 오류: {e}")

    def emergency_stop(self):
        """웹소켓 비상 정지"""
        try:
            if self.websocket_service:
                self.websocket_service.stop_websocket_connection()
                self.websocket_service = None
            self.tm.websocket_interceptor = None
        except Exception as e:
            self.logger.error(f"웹소켓 비상 정지 오류: {e}")

    def cleanup(self):
        """리소스 정리"""
        try:
            if self.websocket_service:
                self.websocket_service.stop_websocket_connection()
        except:
            pass