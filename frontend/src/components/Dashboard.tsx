import React, { useState, useEffect } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Button,
  Grid,
  Paper,
  IconButton,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Settings as SettingsIcon,
  Logout,
  AccountBalance
} from '@mui/icons-material';
import BettingWidget from './BettingWidget';
import Settings from './Settings';
import Statistics from './Statistics';
import { api } from '../services/api';
import { useWebSocket } from '../services/websocket';

interface User {
  username: string;
  level: number;
  expire_date: string;
}

interface DashboardProps {
  user: User;
  onLogout: () => void;
}

const Dashboard: React.FC<DashboardProps> = ({ user, onLogout }) => {
  const [browserLaunched, setBrowserLaunched] = useState(false);  // 브라우저 실행 여부
  const [isTrading, setIsTrading] = useState(false);  // 베팅 활성 여부
  const [currentRoom, setCurrentRoom] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [martinStep, setMartinStep] = useState(0);
  const [statistics, setStatistics] = useState({
    total_games: 0,
    wins: 0,
    losses: 0,
    ties: 0,
    win_rate: 0
  });
  const [showSettings, setShowSettings] = useState(false);
  const [selectedSite, setSelectedSite] = useState<string>('site1');
  const [sites, setSites] = useState<{[key: string]: string}>({});
  const [minStreak, setMinStreak] = useState(3);

  // WebSocket 연결
  const { connected, lastMessage } = useWebSocket(user.username);

  useEffect(() => {
    // WebSocket 메시지 처리
    if (lastMessage) {
      const { type, data } = lastMessage;
      
      switch (type) {
        case 'status_update':
          if (data.status === 'browser_launched') {
            setBrowserLaunched(true);
          } else if (data.status === 'betting_started') {
            setIsTrading(true);
          } else if (data.status === 'stopped') {
            setBrowserLaunched(false);
            setIsTrading(false);
          }
          break;
        case 'room_change':
          setCurrentRoom(data.room);
          break;
        case 'balance_update':
          setBalance(data.balance);
          break;
        case 'betting_result':
          setMartinStep(data.martin_step);
          setStatistics(data.statistics);
          break;
        case 'game_update':
          // 게임 상태 업데이트 처리
          break;
      }
    }
  }, [lastMessage]);

  useEffect(() => {
    // 초기 상태 로드
    loadStatus();
    loadSettings();
  }, []);

  const loadStatus = async () => {
    try {
      const response = await api.get('/api/trading/status');
      setIsTrading(response.data.is_active);
      setCurrentRoom(response.data.current_room);
      setBalance(response.data.current_balance);
      setMartinStep(response.data.martin_step);
    } catch (error) {
      console.error('상태 로드 실패:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const response = await api.get('/api/settings');
      setSites({
        site1: response.data.site1 || '',
        site2: response.data.site2 || '',
        site3: response.data.site3 || ''
      });
      setMinStreak(response.data.min_streak || 3);
    } catch (error) {
      console.error('설정 로드 실패:', error);
    }
  };

  const handleStart = async () => {
    try {
      // 기존 브라우저가 있어도 새로 시작 (백엔드에서 자동으로 종료하고 재시작)
      await api.post('/api/trading/start', {
        site_key: selectedSite
      });
      setBrowserLaunched(true);
      setIsTrading(false); // 베팅 상태는 초기화
    } catch (error) {
      console.error('브라우저 시작 실패:', error);
      alert('브라우저 시작에 실패했습니다.');
    }
  };

  const handleStartBetting = async () => {
    try {
      await api.post('/api/trading/start-betting');
      setIsTrading(true);
    } catch (error) {
      console.error('베팅 시작 실패:', error);
    }
  };

  const handleSiteChange = (event: SelectChangeEvent) => {
    setSelectedSite(event.target.value);
  };

  const handleStop = async () => {
    try {
      await api.post('/api/trading/stop');
      setIsTrading(false);
      setBrowserLaunched(false);
    } catch (error) {
      console.error('트레이딩 중지 실패:', error);
    }
  };

  const handleLogout = async () => {
    try {
      await api.post('/api/auth/logout');
      onLogout();
    } catch (error) {
      onLogout();
    }
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            홀덤 자동 트레이더
          </Typography>
          
          <Chip
            icon={<AccountBalance />}
            label={`잔액: ${balance?.toLocaleString() || 0}원`}
            color="primary"
            sx={{ mr: 2 }}
          />
          
          <Typography sx={{ mr: 2 }}>
            {user.username} ({user.level}레벨)
          </Typography>
          
          <IconButton
            color="inherit"
            onClick={() => setShowSettings(true)}
          >
            <SettingsIcon />
          </IconButton>
          
          <IconButton color="inherit" onClick={handleLogout}>
            <Logout />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Box sx={{ p: 3 }}>
        <Grid container spacing={3}>
          {/* 제어 패널 */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <FormControl sx={{ minWidth: 150 }} size="small">
                  <InputLabel>사이트 선택</InputLabel>
                  <Select
                    value={selectedSite}
                    label="사이트 선택"
                    onChange={handleSiteChange}
                    disabled={isTrading}
                  >
                    {Object.entries(sites).map(([key, value]) => (
                      value && (
                        <MenuItem key={key} value={key}>
                          {key}: {value}
                        </MenuItem>
                      )
                    ))}
                  </Select>
                </FormControl>
                
                {/* 3단계 버튼 시스템 */}
                {!browserLaunched && (
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={<PlayArrow />}
                    onClick={handleStart}
                    size="large"
                    disabled={!sites[selectedSite]}
                  >
                    시작
                  </Button>
                )}
                
                {browserLaunched && !isTrading && (
                  <Button
                    variant="contained"
                    color="success"
                    startIcon={<PlayArrow />}
                    onClick={handleStartBetting}
                    size="large"
                  >
                    베팅 시작
                  </Button>
                )}
                
                {(browserLaunched || isTrading) && (
                  <Button
                    variant="contained"
                    color="error"
                    startIcon={<Stop />}
                    onClick={handleStop}
                    size="large"
                  >
                    중지
                  </Button>
                )}
                
                <Typography>
                  상태: {isTrading ? '트레이딩 중' : browserLaunched ? '브라우저 실행됨 (로그인 대기)' : '대기 중'}
                </Typography>
                
                {currentRoom && (
                  <Chip
                    label={`현재 방: ${currentRoom}`}
                    color="info"
                  />
                )}
                
                <Chip
                  label={connected ? 'WebSocket 연결됨' : 'WebSocket 연결 안됨'}
                  color={connected ? 'success' : 'error'}
                  size="small"
                />
              </Box>
            </Paper>
          </Grid>

          {/* 베팅 위젯 */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                베팅 상태
              </Typography>
              <BettingWidget martinStep={martinStep} />
            </Paper>
          </Grid>

          {/* 통계 */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                통계
              </Typography>
              <Statistics stats={statistics} />
            </Paper>
          </Grid>
        </Grid>
      </Box>

      {/* 설정 다이얼로그 */}
      <Settings
        open={showSettings}
        onClose={() => setShowSettings(false)}
        onSave={() => {
          setShowSettings(false);
          loadSettings();
        }}
      />
    </Box>
  );
};

export default Dashboard;