"""
인증 API - 기존 DB 시스템과 연동
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext

# 기존 데이터베이스 서비스 재사용
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "holdem-auto-trader"))
from services.database_service import get_database_service

logger = logging.getLogger(__name__)

# JWT 설정
SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24시간

# 비밀번호 암호화
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 라우터 생성
router = APIRouter()

# Pydantic 모델
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    level: int
    expire_date: str

class LoginRequest(BaseModel):
    username: str
    password: str

# 데이터베이스 서비스 인스턴스
db_service = get_database_service()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """현재 로그인한 사용자 정보 가져오기"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    # DB에서 사용자 정보 조회
    user_info = db_service.get_user(username)
    if user_info is None:
        raise credentials_exception
    
    return User(
        username=user_info['username'],
        level=user_info['level'],
        expire_date=user_info['expire_date']
    )

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """사용자 로그인"""
    try:
        # 기존 DB 서비스를 통한 인증
        user_info = db_service.verify_user(
            form_data.username,
            form_data.password
        )
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="아이디 또는 비밀번호가 올바르지 않습니다",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 만료일은 verify_user에서 이미 확인됨
        
        # JWT 토큰 생성
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": form_data.username},
            expires_delta=access_token_expires
        )
        
        logger.info(f"로그인 성공: {form_data.username}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"로그인 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="로그인 처리 중 오류가 발생했습니다"
        )

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """현재 로그인한 사용자 정보 조회"""
    return current_user

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """로그아웃 (클라이언트에서 토큰 삭제 필요)"""
    logger.info(f"로그아웃: {current_user.username}")
    return {"message": "로그아웃 되었습니다"}

@router.get("/check")
async def check_auth(current_user: User = Depends(get_current_user)):
    """인증 상태 확인"""
    return {
        "authenticated": True,
        "username": current_user.username,
        "level": current_user.level,
        "expire_date": current_user.expire_date
    }