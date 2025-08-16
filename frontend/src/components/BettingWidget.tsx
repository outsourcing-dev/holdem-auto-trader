import React from 'react';
import { Box, Grid, Paper, Typography } from '@mui/material';

interface BettingWidgetProps {
  martinStep: number;
}

const BettingWidget: React.FC<BettingWidgetProps> = ({ martinStep }) => {
  const maxSteps = 10; // 최대 표시할 단계 수
  
  const getMarkerForStep = (step: number) => {
    if (step < martinStep) return 'X'; // 패배
    if (step === martinStep) return '●'; // 현재 위치
    return '○'; // 대기
  };

  const getColorForStep = (step: number) => {
    if (step < martinStep) return '#f44336'; // 빨강 (패배)
    if (step === martinStep) return '#4caf50'; // 초록 (현재)
    return '#666'; // 회색 (대기)
  };

  return (
    <Box>
      <Grid container spacing={1}>
        {Array.from({ length: maxSteps }, (_, i) => (
          <Grid item key={i}>
            <Paper
              sx={{
                width: 50,
                height: 50,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: i === martinStep ? 'primary.dark' : 'background.paper',
                border: i === martinStep ? '2px solid' : '1px solid',
                borderColor: getColorForStep(i)
              }}
            >
              <Typography
                variant="h6"
                sx={{
                  color: getColorForStep(i),
                  fontWeight: i === martinStep ? 'bold' : 'normal'
                }}
              >
                {getMarkerForStep(i)}
              </Typography>
            </Paper>
            <Typography
              variant="caption"
              align="center"
              display="block"
              sx={{ mt: 0.5 }}
            >
              {i + 1}단계
            </Typography>
          </Grid>
        ))}
      </Grid>
      
      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          현재 마틴 단계: {martinStep + 1}
        </Typography>
      </Box>
    </Box>
  );
};

export default BettingWidget;