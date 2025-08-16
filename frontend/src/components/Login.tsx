import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress
} from '@mui/material';
import { api } from '../services/api';

interface LoginProps {
  onLogin: (user: any) => void;
}

const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await api.post('/api/auth/login', formData);
      
      // 토큰 저장
      localStorage.setItem('token', response.data.access_token);
      
      // 사용자 정보 가져오기
      const userResponse = await api.get('/api/auth/me');
      
      onLogin(userResponse.data);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail;
      if (typeof errorMessage === 'string') {
        setError(errorMessage);
      } else if (Array.isArray(errorMessage)) {
        setError(errorMessage[0]?.msg || '로그인에 실패했습니다.');
      } else {
        setError('로그인에 실패했습니다.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        backgroundColor: '#121212'
      }}
    >
      <Card sx={{ minWidth: 400, maxWidth: 500 }}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h4" align="center" gutterBottom>
            홀덤 자동 트레이더
          </Typography>
          <Typography variant="subtitle1" align="center" color="text.secondary" gutterBottom>
            웹 버전 2.0
          </Typography>
          
          <Box component="form" onSubmit={handleSubmit} sx={{ mt: 3 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            
            <TextField
              fullWidth
              label="아이디"
              variant="outlined"
              margin="normal"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={loading}
            />
            
            <TextField
              fullWidth
              label="비밀번호"
              type="password"
              variant="outlined"
              margin="normal"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
            />
            
            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              sx={{ mt: 3 }}
              disabled={loading || !username || !password}
            >
              {loading ? <CircularProgress size={24} /> : '로그인'}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Login;