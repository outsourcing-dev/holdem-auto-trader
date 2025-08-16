"""
설정 관리 API - 기존 settings.json과 호환
"""
import logging
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.auth import get_current_user, User

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# 설정 파일 경로
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
ROOM_SETTINGS_FILE = CONFIG_DIR / "room_settings.json"

# Pydantic 모델
class Settings(BaseModel):
    site1: str = ""
    site2: str = ""
    site3: str = ""
    martin_count: int = 3
    martin_amounts: List[int] = [10000, 20000, 40000]
    target_amount: int = 5000000
    min_streak: int = 3
    double_half_start: int = 0
    double_half_stop: int = 0

class RoomSettings(BaseModel):
    excluded_rooms: List[str] = []
    preferred_rooms: List[str] = []
    auto_exclude_time: int = 600  # 10분

def load_settings() -> Settings:
    """설정 파일 로드"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Settings(**data)
        else:
            # 기본 설정 생성
            default_settings = Settings()
            save_settings(default_settings)
            return default_settings
    except Exception as e:
        logger.error(f"설정 로드 오류: {e}")
        return Settings()

def save_settings(settings: Settings):
    """설정 파일 저장"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, indent=2, ensure_ascii=False)
        logger.info("설정 저장 완료")
    except Exception as e:
        logger.error(f"설정 저장 오류: {e}")
        raise

def load_room_settings() -> RoomSettings:
    """방 설정 파일 로드"""
    try:
        if ROOM_SETTINGS_FILE.exists():
            with open(ROOM_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return RoomSettings(**data)
        else:
            default_settings = RoomSettings()
            save_room_settings(default_settings)
            return default_settings
    except Exception as e:
        logger.error(f"방 설정 로드 오류: {e}")
        return RoomSettings()

def save_room_settings(settings: RoomSettings):
    """방 설정 파일 저장"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(ROOM_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, indent=2, ensure_ascii=False)
        logger.info("방 설정 저장 완료")
    except Exception as e:
        logger.error(f"방 설정 저장 오류: {e}")
        raise

@router.get("/", response_model=Settings)
async def get_settings(current_user: User = Depends(get_current_user)):
    """현재 설정 조회"""
    try:
        settings = load_settings()
        return settings
    except Exception as e:
        logger.error(f"설정 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail="설정 조회에 실패했습니다"
        )

@router.put("/")
async def update_settings(
    settings: Settings,
    current_user: User = Depends(get_current_user)
):
    """설정 업데이트"""
    try:
        # 유효성 검사
        if settings.martin_count <= 0:
            raise HTTPException(
                status_code=400,
                detail="마틴 단계는 1 이상이어야 합니다"
            )
        
        if len(settings.martin_amounts) != settings.martin_count:
            raise HTTPException(
                status_code=400,
                detail="마틴 금액 개수와 단계 수가 일치해야 합니다"
            )
        
        if settings.target_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="목표 금액은 0보다 커야 합니다"
            )
        
        if settings.min_streak < 1:
            raise HTTPException(
                status_code=400,
                detail="최소 연패는 1 이상이어야 합니다"
            )
        
        # 설정 저장
        save_settings(settings)
        
        logger.info(f"설정 업데이트: {current_user.username}")
        
        return {
            "status": "success",
            "message": "설정이 저장되었습니다"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"설정 업데이트 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"설정 저장 실패: {str(e)}"
        )

@router.get("/rooms", response_model=RoomSettings)
async def get_room_settings(current_user: User = Depends(get_current_user)):
    """방 설정 조회"""
    try:
        settings = load_room_settings()
        return settings
    except Exception as e:
        logger.error(f"방 설정 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail="방 설정 조회에 실패했습니다"
        )

@router.put("/rooms")
async def update_room_settings(
    settings: RoomSettings,
    current_user: User = Depends(get_current_user)
):
    """방 설정 업데이트"""
    try:
        save_room_settings(settings)
        
        logger.info(f"방 설정 업데이트: {current_user.username}")
        
        return {
            "status": "success",
            "message": "방 설정이 저장되었습니다"
        }
        
    except Exception as e:
        logger.error(f"방 설정 업데이트 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"방 설정 저장 실패: {str(e)}"
        )

@router.post("/reset")
async def reset_settings(current_user: User = Depends(get_current_user)):
    """설정 초기화"""
    try:
        # 기본 설정으로 초기화
        default_settings = Settings()
        save_settings(default_settings)
        
        default_room_settings = RoomSettings()
        save_room_settings(default_room_settings)
        
        logger.info(f"설정 초기화: {current_user.username}")
        
        return {
            "status": "success",
            "message": "설정이 초기화되었습니다"
        }
        
    except Exception as e:
        logger.error(f"설정 초기화 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"설정 초기화 실패: {str(e)}"
        )