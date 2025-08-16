import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Grid,
  Typography,
  Box,
  Divider
} from '@mui/material';
import { api } from '../services/api';

interface SettingsProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
}

const Settings: React.FC<SettingsProps> = ({ open, onClose, onSave }) => {
  const [settings, setSettings] = useState({
    site1: '',
    site2: '',
    site3: '',
    martin_count: 3,
    martin_amounts: [10000, 20000, 40000],
    target_amount: 5000000,
    min_streak: 3
  });

  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open]);

  const loadSettings = async () => {
    try {
      const response = await api.get('/api/settings');
      setSettings(response.data);
    } catch (error) {
      console.error('설정 로드 실패:', error);
    }
  };

  const handleSave = async () => {
    try {
      await api.put('/api/settings', settings);
      onSave();
    } catch (error) {
      console.error('설정 저장 실패:', error);
    }
  };

  const handleMartinAmountChange = (index: number, value: string) => {
    const amounts = [...settings.martin_amounts];
    amounts[index] = parseInt(value) || 0;
    setSettings({ ...settings, martin_amounts: amounts });
  };

  const handleMartinCountChange = (count: number) => {
    const amounts = Array(count).fill(0).map((_, i) => 
      settings.martin_amounts[i] || 10000 * Math.pow(2, i)
    );
    setSettings({ 
      ...settings, 
      martin_count: count,
      martin_amounts: amounts 
    });
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose} 
      maxWidth="lg" 
      fullWidth
      scroll="paper"
    >
      <DialogTitle>
        <Typography variant="h5">설정</Typography>
        <Typography variant="body2" color="text.secondary">
          트레이딩 설정을 조정하세요
        </Typography>
      </DialogTitle>
      <DialogContent dividers>
        <Box sx={{ mt: 2 }}>
          <Typography variant="h6" gutterBottom>
            사이트 설정
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="사이트 1"
                placeholder="예: https://example1.com"
                value={settings.site1}
                onChange={(e) => setSettings({ ...settings, site1: e.target.value })}
                helperText="주 사이트 URL을 입력하세요"
                margin="normal"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="사이트 2"
                placeholder="예: https://example2.com"
                value={settings.site2}
                onChange={(e) => setSettings({ ...settings, site2: e.target.value })}
                helperText="보조 사이트 URL을 입력하세요 (선택사항)"
                margin="normal"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="사이트 3"
                placeholder="예: https://example3.com"
                value={settings.site3}
                onChange={(e) => setSettings({ ...settings, site3: e.target.value })}
                helperText="추가 사이트 URL을 입력하세요 (선택사항)"
                margin="normal"
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            마틴 설정
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={6}>
              <TextField
                fullWidth
                type="number"
                label="마틴 단계 수"
                value={settings.martin_count}
                onChange={(e) => handleMartinCountChange(parseInt(e.target.value) || 1)}
                inputProps={{ min: 1, max: 10 }}
                helperText="마틴게일 진행 단계 (1-10)"
                margin="normal"
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                fullWidth
                type="number"
                label="최소 연패"
                value={settings.min_streak}
                onChange={(e) => setSettings({ ...settings, min_streak: parseInt(e.target.value) || 1 })}
                inputProps={{ min: 1 }}
                helperText="진입할 최소 연패 수"
                margin="normal"
              />
            </Grid>
          </Grid>

          <Box sx={{ mt: 3 }}>
            <Typography variant="subtitle1" gutterBottom>
              마틴 금액 설정
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              각 단계별 베팅 금액을 설정하세요
            </Typography>
            <Grid container spacing={2}>
              {Array.from({ length: settings.martin_count }, (_, i) => (
                <Grid item xs={settings.martin_count <= 3 ? 4 : settings.martin_count <= 6 ? 6 : 12} key={i}>
                  <TextField
                    fullWidth
                    type="number"
                    label={`${i + 1}단계 금액`}
                    value={settings.martin_amounts[i] || 0}
                    onChange={(e) => handleMartinAmountChange(i, e.target.value)}
                    inputProps={{ min: 1000, step: 1000 }}
                    helperText={i === 0 ? "기본 베팅" : `${i}번 실패 후`}
                    margin="normal"
                  />
                </Grid>
              ))}
            </Grid>
          </Box>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            목표 설정
          </Typography>
          <TextField
            fullWidth
            type="number"
            label="목표 금액"
            value={settings.target_amount}
            onChange={(e) => setSettings({ ...settings, target_amount: parseInt(e.target.value) || 0 })}
            inputProps={{ min: 10000, step: 10000 }}
            helperText="목표 수익 금액에 도달하면 자동 종료됩니다"
            margin="normal"
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>취소</Button>
        <Button onClick={handleSave} variant="contained">저장</Button>
      </DialogActions>
    </Dialog>
  );
};

export default Settings;