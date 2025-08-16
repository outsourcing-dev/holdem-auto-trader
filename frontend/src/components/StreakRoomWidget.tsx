import React from 'react';
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Paper,
  Chip,
  LinearProgress,
  Alert
} from '@mui/material';
import { Casino, CheckCircle, Warning } from '@mui/icons-material';

interface StreakRoom {
  room_id: string;
  room_name: string;
  current_streak: number;
  streak_type: string;
  game_count: number;
  verified?: boolean;
  next_prediction?: string;
}

interface StreakRoomWidgetProps {
  rooms: StreakRoom[];
  currentTargetRoom?: string | null;
  isMonitoring: boolean;
}

const StreakRoomWidget: React.FC<StreakRoomWidgetProps> = ({ 
  rooms, 
  currentTargetRoom,
  isMonitoring 
}) => {
  // 연패 수로 정렬 (높은 순)
  const sortedRooms = [...rooms].sort((a, b) => b.current_streak - a.current_streak);

  return (
    <Paper sx={{ p: 2, height: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Casino sx={{ mr: 1 }} />
        <Typography variant="h6">
          연패방 감지 현황
        </Typography>
        {isMonitoring && (
          <Chip 
            label="모니터링 중" 
            color="success" 
            size="small" 
            sx={{ ml: 'auto' }}
          />
        )}
      </Box>

      {isMonitoring && <LinearProgress sx={{ mb: 2 }} />}

      {rooms.length === 0 ? (
        <Alert severity="info">
          연패방을 검색 중입니다...
        </Alert>
      ) : (
        <List sx={{ maxHeight: 400, overflow: 'auto' }}>
          {sortedRooms.map((room) => (
            <ListItem
              key={room.room_id}
              sx={{
                border: 1,
                borderColor: currentTargetRoom === room.room_name ? 'primary.main' : 'divider',
                borderRadius: 1,
                mb: 1,
                bgcolor: currentTargetRoom === room.room_name ? 'primary.light' : 'background.paper'
              }}
            >
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="subtitle1">
                      {room.room_name}
                    </Typography>
                    {room.verified && (
                      <CheckCircle color="success" fontSize="small" />
                    )}
                    {currentTargetRoom === room.room_name && (
                      <Chip label="현재 타겟" color="primary" size="small" />
                    )}
                  </Box>
                }
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      <Chip 
                        label={`${room.current_streak}연패`}
                        color={room.current_streak >= 5 ? 'error' : 'warning'}
                        size="small"
                      />
                      <Chip 
                        label={`타입: ${room.streak_type}`}
                        size="small"
                        variant="outlined"
                      />
                      <Chip 
                        label={`게임 수: ${room.game_count}`}
                        size="small"
                        variant="outlined"
                      />
                      {room.next_prediction && (
                        <Chip 
                          label={`예측: ${room.next_prediction}`}
                          color="info"
                          size="small"
                        />
                      )}
                    </Box>
                  </Box>
                }
              />
            </ListItem>
          ))}
        </List>
      )}

      <Box sx={{ mt: 2, p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
        <Typography variant="caption" color="text.secondary">
          • 15-64게임 범위의 방만 표시됩니다
        </Typography>
        <br />
        <Typography variant="caption" color="text.secondary">
          • 검증된 방(✓)이 우선 선택됩니다
        </Typography>
      </Box>
    </Paper>
  );
};

export default StreakRoomWidget;