import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class ApiService {
  private instance: AxiosInstance;

  constructor() {
    this.instance = axios.create({
      baseURL: API_BASE_URL,
    });

    // Request interceptor to add token
    this.instance.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        
        // Set content-type based on data type
        if (config.data instanceof FormData) {
          // Let browser set the content-type for FormData
          delete config.headers['Content-Type'];
        } else if (typeof config.data === 'object' && config.data !== null) {
          // Set JSON content-type for objects
          config.headers['Content-Type'] = 'application/json';
        }
        
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.instance.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  get(url: string, config?: any) {
    return this.instance.get(url, config);
  }

  post(url: string, data?: any, config?: any) {
    return this.instance.post(url, data, config);
  }

  put(url: string, data?: any, config?: any) {
    return this.instance.put(url, data, config);
  }

  delete(url: string, config?: any) {
    return this.instance.delete(url, config);
  }
}

export const api = new ApiService();