"""
홀덤 자동 트레이더 웹 버전 - FastAPI 백엔드 서버
"""
import sys
import os
from pathlib import Path
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# API 라우터 임포트
from api.auth import router as auth_router
from api.trading import router as trading_router
from api.settings import router as settings_router
from api.websocket import websocket_manager

# 로깅 설정
log_handlers = []

# 패키징된 경우 파일로만 로깅
if getattr(sys, 'frozen', False):
    # 로그 파일 경로
    log_file = Path(sys._MEIPASS).parent / "holdem_web_trader.log"
    log_handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
else:
    # 개발 환경에서는 콘솔 출력
    log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# 경로 설정
if getattr(sys, 'frozen', False):
    # PyInstaller로 패키징된 경우
    BASE_DIR = Path(sys._MEIPASS)
    # API 모듈 경로를 sys.path에 추가
    sys.path.insert(0, str(BASE_DIR))
    STATIC_DIR = BASE_DIR / "frontend" / "build"
    logger.info(f"Frozen mode - BASE_DIR: {BASE_DIR}")
    logger.info(f"Frozen mode - STATIC_DIR: {STATIC_DIR}")
else:
    # 개발 환경
    BASE_DIR = Path(__file__).parent
    STATIC_DIR = BASE_DIR.parent / "frontend" / "build"
    logger.info(f"Development mode - STATIC_DIR: {STATIC_DIR}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시
    logger.info("🚀 홀덤 자동 트레이더 웹 서버 시작")
    
    # WebSocket 매니저 초기화
    await websocket_manager.startup()
    
    yield
    
    # 종료 시
    logger.info("🛑 서버 종료 중...")
    await websocket_manager.shutdown()

# FastAPI 앱 생성
app = FastAPI(
    title="홀덤 자동 트레이더 Web API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 설정 (개발 환경)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(trading_router, prefix="/api/trading", tags=["Trading"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])

# WebSocket 엔드포인트
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 연결 처리"""
    await websocket_manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_json()
            await websocket_manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        websocket_manager.disconnect(websocket)

# 정적 파일 서빙 (프로덕션 모드)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR / "static")), name="static")
    
    @app.get("/")
    async def serve_spa():
        """React SPA 서빙"""
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend not built. Run 'npm run build' in frontend directory."}
    
    @app.get("/{full_path:path}")
    async def serve_spa_paths(full_path: str):
        """React Router 경로 처리"""
        # API 경로가 아닌 경우 index.html 반환
        if not full_path.startswith("api/") and not full_path.startswith("ws"):
            index_path = STATIC_DIR / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
        return {"message": "Not found"}

# 헬스체크 엔드포인트
@app.get("/api/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "message": "홀덤 자동 트레이더 웹 서버 정상 작동 중"
    }

def open_browser():
    """브라우저 자동 열기"""
    import webbrowser
    import time
    import socket
    
    # 서버가 실제로 시작될 때까지 대기
    for i in range(15):  # 최대 15초 대기
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 8000))
            sock.close()
            if result == 0:
                print("서버가 시작되었습니다. 브라우저를 엽니다...")
                webbrowser.open('http://localhost:8000')
                return
        except:
            pass
        time.sleep(1)
    print("서버 시작을 확인할 수 없습니다. 수동으로 http://localhost:8000에 접속하세요.")

if __name__ == "__main__":
    import uvicorn
    import threading
    
    # PyInstaller로 빌드된 경우 stdout/stderr 복구
    is_frozen = getattr(sys, 'frozen', False)
    if is_frozen:
        # stdout과 stderr를 복구
        if sys.stdout is None:
            sys.stdout = open(os.devnull, 'w')
        if sys.stderr is None:
            sys.stderr = open(os.devnull, 'w')
    
    print("")
    print("=" * 60)
    print("홀덤 자동 트레이더 웹 서버가 시작되었습니다!")
    print("브라우저가 자동으로 열립니다...")
    print("주소: http://localhost:8000")
    print("종료하려면 Ctrl+C를 누르세요.")
    print("=" * 60)
    print("")
    
    # 프로덕션 서버 실행
    if is_frozen:
        # 패키징된 경우 - 브라우저 열기를 별도 프로세스로
        import subprocess
        import logging
        logging.basicConfig(level=logging.INFO)
        
        # 브라우저 열기 (별도 프로세스)
        def start_browser():
            import time
            time.sleep(3)
            try:
                # 여러 방법으로 브라우저 열기 시도
                import subprocess
                
                # 방법 1: cmd /c start
                try:
                    subprocess.run(['cmd', '/c', 'start', 'http://localhost:8000'], 
                                 check=True, timeout=5)
                    print("브라우저가 열렸습니다.")
                    return
                except:
                    pass
                
                # 방법 2: rundll32
                try:
                    subprocess.run(['rundll32', 'url.dll,FileProtocolHandler', 'http://localhost:8000'], 
                                 check=True, timeout=5)
                    print("브라우저가 열렸습니다.")
                    return
                except:
                    pass
                
                # 방법 3: 기본 브라우저 직접 실행
                try:
                    subprocess.run(['start', 'http://localhost:8000'], shell=True, 
                                 check=True, timeout=5)
                    print("브라우저가 열렸습니다.")
                    return
                except:
                    pass
                    
                print("브라우저 자동 열기에 실패했습니다.")
                print("수동으로 http://localhost:8000에 접속하세요.")
                
            except Exception as e:
                print(f"브라우저 열기 중 오류: {e}")
                print("수동으로 http://localhost:8000에 접속하세요.")
        
        browser_thread = threading.Thread(target=start_browser, daemon=True)
        browser_thread.start()
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            log_config=None  # 기본 로깅 설정 비활성화
        )
    else:
        # 개발 환경 - 기존 방식
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        uvicorn.run(
            "main:app",  # import string으로 전달
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )