# 홀덤 웹 트레이더 (Holdem Web Trader)

Evolution Gaming 자동 베팅 프로그램 - 웹 버전

## 🚀 주요 기능

- **실시간 WebSocket 모니터링**: Evolution Gaming 로비에서 게임 데이터 실시간 수집
- **연패방 자동 감지**: 서버와 통신하여 연패방 검증 및 예측
- **자동 베팅 실행**: Selenium 기반 실제 베팅 자동화
- **웹 기반 UI**: React 프론트엔드로 편리한 사용자 인터페이스
- **마틴게일 전략**: 사용자 설정 가능한 마틴게일 베팅 시스템

## 📦 실행 방법

### 방법 1: 배치 파일 런처 (가장 권장) ⭐
1. `dist/start_with_browser.bat` 더블클릭
2. 서버 시작 후 자동으로 브라우저 열림
3. 가장 확실한 방법

### 방법 2: VBS 런처 (올인원)
1. `dist/HoldemWebTrader_WithBrowser.vbs` 더블클릭
2. exe 실행 + 브라우저 자동 열기 + 종료 제어
3. 메시지 박스로 종료

### 방법 3: PowerShell 런처 (안정적)
1. `Run_HoldemWebTrader.bat` 더블클릭
2. 기존 서버 종료 후 새 서버 시작
3. Enter 키로 종료

### 방법 4: 실행 파일 직접 실행
1. `dist/HoldemWebTrader.exe` 실행
2. 콘솔 창 표시, 수동으로 브라우저 접속 필요
3. http://localhost:8000 직접 접속

### 방법 5: Python 직접 실행 (개발자용)
1. `backend` 폴더에서 `python main.py`
2. 개발 및 디버깅용

## 🔧 시스템 요구사항

- Windows 10/11
- Chrome 브라우저
- 인터넷 연결

## 📁 파일 구조

```
holdem-web-trader/
├── dist/
│   └── HoldemWebTrader.exe    # 실행 파일
├── frontend/                   # React 프론트엔드
│   └── build/                  # 빌드된 정적 파일
├── backend/                    # FastAPI 백엔드
│   ├── main.py                # 메인 서버
│   ├── api/                   # API 엔드포인트
│   ├── core/                  # 핵심 로직
│   │   ├── trading_engine_v2.py
│   │   ├── websocket_monitor.py
│   │   └── betting_executor.py
│   └── services/              # 서비스 모듈
├── settings.json              # 설정 파일
├── users.db                   # 사용자 데이터베이스
└── run.bat                    # 실행 배치 파일
```

## ⚙️ 설정

`settings.json` 파일에서 다음 항목 설정 가능:
- `site1`, `site2`, `site3`: 게임 사이트 URL
- `martin_count`: 마틴게일 단계 수
- `martin_amounts`: 각 단계별 베팅 금액
- `target_amount`: 목표 금액
- `min_streak`: 최소 연패 수

## 🔍 주요 기능 설명

### 1. WebSocket 데이터 파싱
- Evolution Gaming 로비의 실시간 게임 데이터 수집
- 바카라 테이블의 결과 데이터 파싱
- 연패 패턴 자동 감지

### 2. 서버 통신
- 연패 계산 요청: `/api/rooms/calculate-streak`
- 연패 검증 및 예측: `/api/rooms/verify-and-predict`
- 실시간 데이터 동기화

### 3. 자동 베팅
- Selenium WebDriver를 통한 브라우저 제어
- 베팅 타이밍 자동 감지
- 결과 확인 및 전략 실행

## 📝 로그 파일

실행 시 `holdem_web_trader.log` 파일이 생성되어 모든 활동이 기록됩니다.

## ⚠️ 주의사항

- 이 프로그램은 교육 및 연구 목적으로만 사용하세요
- 실제 금전을 사용한 도박은 위험할 수 있습니다
- 책임감 있는 사용을 권장합니다

## 🔧 문제 해결

### 포트 8000 오류가 발생하는 경우
- 기존 서버가 실행 중입니다
- `Run_HoldemWebTrader.bat` 사용 (자동으로 기존 서버 종료)
- 또는 수동으로 작업 관리자에서 Python 프로세스 종료

### 브라우저가 열리지 않는 경우
- 수동으로 `http://localhost:8000` 접속

### 로그인이 안 되는 경우
- Chrome 브라우저 최신 버전 확인
- 방화벽 설정 확인

### 베팅이 실행되지 않는 경우
- Evolution Gaming iframe 로딩 대기
- 설정 파일의 베팅 금액 확인

### exe 파일 실행 오류
- uvicorn 로깅 오류가 발생하는 경우 정상적인 현상입니다
- 콘솔 창이 표시되지만 브라우저는 정상적으로 열립니다

## 📄 라이선스

이 프로그램은 개인 사용 목적으로 제작되었습니다.