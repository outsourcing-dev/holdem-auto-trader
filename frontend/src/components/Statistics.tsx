import React from 'react';
import { Grid, Typography, Box, LinearProgress } from '@mui/material';

interface StatisticsProps {
  stats: {
    total_games: number;
    wins: number;
    losses: number;
    ties: number;
    win_rate: number;
  };
}

const Statistics: React.FC<StatisticsProps> = ({ stats }) => {
  const winRate = stats.total_games > 0 
    ? (stats.wins / stats.total_games * 100).toFixed(1)
    : '0.0';

  return (
    <Box>
      <Grid container spacing={2}>
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">
            총 게임 수
          </Typography>
          <Typography variant="h6">
            {stats.total_games}
          </Typography>
        </Grid>
        
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">
            승률
          </Typography>
          <Typography variant="h6" color="primary">
            {winRate}%
          </Typography>
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              승/패/무 분포
            </Typography>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="success.main">
                  승: {stats.wins}
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={stats.total_games > 0 ? (stats.wins / stats.total_games * 100) : 0}
                  color="success"
                  sx={{ mt: 0.5 }}
                />
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="error.main">
                  패: {stats.losses}
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={stats.total_games > 0 ? (stats.losses / stats.total_games * 100) : 0}
                  color="error"
                  sx={{ mt: 0.5 }}
                />
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  무: {stats.ties}
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={stats.total_games > 0 ? (stats.ties / stats.total_games * 100) : 0}
                  sx={{ mt: 0.5 }}
                />
              </Box>
            </Box>
          </Box>
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ mt: 1, p: 1, bgcolor: 'background.default', borderRadius: 1 }}>
            <Grid container spacing={1}>
              <Grid item xs={4}>
                <Typography variant="caption" display="block" align="center">
                  마틴 성공률
                </Typography>
                <Typography variant="body2" align="center" fontWeight="bold">
                  {stats.total_games > 0 ? ((stats.wins / (stats.wins + stats.losses)) * 100).toFixed(1) : '0.0'}%
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="caption" display="block" align="center">
                  평균 마틴 단계
                </Typography>
                <Typography variant="body2" align="center" fontWeight="bold">
                  -
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="caption" display="block" align="center">
                  최대 연패
                </Typography>
                <Typography variant="body2" align="center" fontWeight="bold">
                  -
                </Typography>
              </Grid>
            </Grid>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Statistics;