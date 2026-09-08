import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from 'react';
import { registerAuthFailureHandler } from '../lib/apiClient';
import API_BASE_URL from '../config/api';

const AuthContext = createContext(null);

const AUTH_BASE_URL = `${API_BASE_URL}/api/auth`;

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [csrfToken, setCsrfToken] = useState('');
  const [reAuthRequired, setReAuthRequired] = useState(false);
  const [pendingReAuthCallback, setPendingReAuthCallback] = useState(null);

  const checkAuth = useCallback(async () => {
    try {
      setIsLoading(true);

      const response = await fetch(`${AUTH_BASE_URL}/me`, {
        method: 'GET',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();

        setUser(data.user);
        setIsAuthenticated(true);

        if (data.csrf_token) {
          setCsrfToken(data.csrf_token);
        }
      } else {
        setUser(null);
        setIsAuthenticated(false);
        setCsrfToken('');
      }
    } catch (error) {
      console.error('Auth check error:', error);
      setUser(null);
      setIsAuthenticated(false);
      setCsrfToken('');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    registerAuthFailureHandler(() => {
      setUser(null);
      setIsAuthenticated(false);
      setCsrfToken('');
    });
  }, []);

  const login = async (email, password, totpCode = '') => {
    const response = await fetch(`${AUTH_BASE_URL}/login`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      },
      body: JSON.stringify({
        email,
        password,
        totp_code: totpCode,
      }),
    });

    let data = {};

    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.detail || 'Login failed');
    }

    if (data.user) {
      setUser(data.user);
      setIsAuthenticated(true);
    }

    if (data.csrf_token) {
      setCsrfToken(data.csrf_token);
    }

    return data;
  };

  const signup = async (signupData) => {
    const response = await fetch(`${AUTH_BASE_URL}/signup`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(signupData),
    });

    let data = {};

    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.detail || 'Signup failed');
    }

    return data;
  };

  const logout = async () => {
    try {
      await fetch(`${AUTH_BASE_URL}/logout`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
        },
      });
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setCsrfToken('');
    }
  };

  const triggerReAuth = (onSuccessCallback) => {
    setPendingReAuthCallback(() => onSuccessCallback);
    setReAuthRequired(true);
  };

  const handleReAuthSuccess = () => {
    setReAuthRequired(false);

    if (pendingReAuthCallback) {
      pendingReAuthCallback();
      setPendingReAuthCallback(null);
    }
  };

  const cancelReAuth = () => {
    setReAuthRequired(false);
    setPendingReAuthCallback(null);
  };

  const value = {
    user,
    isAuthenticated,
    isLoading,
    csrfToken,
    reAuthRequired,
    login,
    signup,
    logout,
    checkAuth,
    triggerReAuth,
    handleReAuthSuccess,
    cancelReAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
};