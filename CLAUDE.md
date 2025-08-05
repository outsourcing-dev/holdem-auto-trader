# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Holdem Auto Trader is a Python-based automated trading bot for online Holdem poker games. It uses Chrome DevTools Protocol (CDP) to control browsers and automatically performs room entry, betting, and room switching based on defined strategies.

## Core Architecture

### Main Application Flow
1. **Login System** → **Main Window** → **Trading Manager** → **Automated Trading**
2. Entry point: `main.py` creates `MainApp` which handles login flow and shows `MainWindow`
3. Main trading logic is orchestrated by `TradingManager` class
4. Comprehensive logging to `log.txt` with file rotation

### Key Components

#### Trading Manager (utils/trading_manager.py)
- **Central orchestrator** for all trading operations
- Manages multiple specialized handler modules:
  - `StreakHandler`: Detects losing streak rooms and manages room targeting
  - `WebSocketManager`: Handles real-time game data via WebSocket interception
  - `GameProcessor`: Processes game results and betting decisions
  - `BettingExecutor`: Executes betting operations
  - `RoomEntryHandler`: Manages room entry and iframe-based monitoring

#### Service Layer (services/)
- `BettingService`: Core betting operations and duplicate prevention
- `GameMonitoringService`: Real-time game state monitoring via CDP
- `BalanceService`: Account balance tracking and target amount monitoring
- `MartinBettingService`: Martingale betting strategy implementation
- `ExcelTradingService`: Excel-based trading strategy integration
- `RoomEntryService`: Room navigation and entry logic
- `WebSocketHybridService`: JavaScript-based WebSocket communication

#### DevTools Integration (utils/devtools.py)
- **DevToolsController**: Chrome DevTools Protocol wrapper
- Controls browser automation via CDP (not Selenium)
- Handles iframe switching and DOM manipulation
- Uses `undetected-chromedriver` for stealth operation

#### Settings Management
- `SettingsManager`: JSON-based configuration (sites, martin amounts, target amount, min_streak)
- Settings UI: `ui/settings_window.py` with user-configurable parameters
- Key settings: martin_count, martin_amounts, target_amount, min_streak

### Trading Strategy Flow

#### Streak-Based Room Detection
1. **WebSocket monitoring** detects rooms with losing streaks
2. **StreakHandler** filters rooms based on `min_streak` setting (user-configurable)
3. **Room entry** only if game count is 15-64 (避开太早或太晚的房间)
4. **Server communication** via `unified_server_client.py` for streak validation

#### Betting Logic
1. **Game state monitoring** via iframe inspection (`current_game` vs completed rounds)
2. **Timing synchronization**: Betting for round N+1 when round N completes
3. **Result handling**: WIN (exit and find new room), LOSE (martin progression), TIE (retry same level)
4. **Martin limits**: Exit room when reaching configured martin_count limit

#### Room Management
1. **Exclusion system**: Failed rooms excluded for 10min (martin fail) or 5min (condition fail)
2. **Automatic room switching** after win/loss conditions
3. **Return to lobby** and search for new streak rooms

## Common Development Commands

### Running the Application
```bash
# Install dependencies
pip install -r requirements.txt

# Run in development
python main.py

# Build executable
pyinstaller "JD Soft.spec"

# Or use automated build script
build_encrypted_excel.bat
```

### Testing and Debugging
- No automated test suite - manual testing via UI
- Debugging: Check logs in `log.txt` and console output
- Trading debug: Use emergency stop button or force room exit
- Logging configured with rotation in `main.py`

## Key Configuration Files

### settings.json
```json
{
    "site1": "domain.com",
    "site2": "domain2.com", 
    "site3": "",
    "martin_count": 3,
    "martin_amounts": [10000, 15000, 20000],
    "target_amount": 5000000,
    "min_streak": 3
}
```

### room_settings.json
- Room filtering and targeting preferences
- Managed by `RoomManager`

### JD Soft.spec
- PyInstaller build configuration
- Includes all necessary data files and hidden imports
- Configures proper icon and metadata

## Architecture Patterns

### Modular Design
- **TradingManager** delegates to specialized handlers in `trading_manager_modules/`
- Each handler focuses on single responsibility (streak detection, betting, room entry)
- Services layer provides reusable business logic

### State Management
- **Central state** in TradingManager (current_target_room, game_count, etc.)
- **Exclusion tracking** with timestamps for room filtering
- **Betting state** tracked per-round to prevent duplicates

### Error Handling
- **Graceful degradation**: Continue operation on non-critical failures
- **Automatic recovery**: Return to lobby and restart room search on errors
- **User feedback**: UI status updates and error messaging
- **Comprehensive logging**: All operations logged to file with rotation

## Critical Implementation Details

### Timing Synchronization
- **iframe monitoring** every 2 seconds to detect game state changes
- **Betting round calculation**: Use `current_game` field for accurate targeting
- **Result waiting**: Don't start new betting until previous result confirmed

### WebSocket vs iframe Strategy
- **WebSocket**: Real-time room discovery and streak detection (lobby)
- **iframe**: Game state monitoring and betting execution (in-room)
- **Hybrid approach**: Pause WebSocket during room play, resume after exit

### Martin Progression
- **User-configurable stages**: Not fixed 3-loss rule
- **TIE handling**: Maintain same martin level, don't progress
- **Exit conditions**: Reach martin limit OR win

### Browser Control
- **CDP (not Selenium)**: Direct Chrome DevTools Protocol for better performance
- **Undetected operation**: Uses undetected-chromedriver
- **iframe focus**: Switch between lobby and game iframes as needed

## Security and Safety

### Room Validation
- **Game count limits**: 15-64 games only
- **Streak verification**: Server-side validation of losing streaks
- **Exclusion lists**: Prevent immediate re-entry to failed rooms

### Betting Safety
- **Duplicate prevention**: Track betting per round
- **Balance monitoring**: Stop at configured target amount
- **Emergency controls**: Manual stop and force exit capabilities

## UI Architecture
- **PyQt6-based**: Modern Qt6 widgets with custom styling
- **Responsive layout**: Fixed window size with dynamic content
- **Real-time updates**: Timer-based UI refresh for trading status
- **Settings integration**: Live configuration updates without restart

## Dependencies
Key packages from requirements.txt:
- PyQt6: UI framework
- undetected-chromedriver: Browser automation
- websockets: WebSocket communication
- beautifulsoup4: HTML parsing
- openpyxl: Excel file handling
- pyinstaller: Executable building