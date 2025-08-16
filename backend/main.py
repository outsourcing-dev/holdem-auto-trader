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
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 경로 설정
BASE_DIR = Path(__file__).parent
if getattr(sys, 'frozen', False):
    # PyInstaller로 패키징된 경우
    BASE_DIR = Path(sys._MEIPASS)
    STATIC_DIR = BASE_DIR / "frontend_build"
else:
    # 개발 환경
    STATIC_DIR = BASE_DIR.parent / "frontend" / "build"

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

if __name__ == "__main__":
    import uvicorn
    
    # 개발 서버 실행
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )