import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [csrfToken, setCsrfToken] = useState('');
  const [reAuthRequired, setReAuthRequired] = useState(false);
  const [pendingReAuthCallback, setPendingReAuthCallback] = useState(null);

  // Check current authentication session on app mount
  const checkAuth = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/auth/me', {
        headers: {
          'Accept': 'application/json'
        }
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
      }
    } catch (error) {
      console.error('Auth check error:', error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Login handler
  const login = async (email, password, totpCode = '') => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
      },
      body: JSON.stringify({ email, password, totp_code: totpCode })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Login failed');
    }

    if (data.user) {
      setUser(data.user);
      setIsAuthenticated(true);
      if (data.csrf_token) setCsrfToken(data.csrf_token);
    }
    return data;
  };

  // Signup handler
  const signup = async (signupData) => {
    const response = await fetch('/api/auth/signup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(signupData)
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Signup failed');
    }
    return data;
  };

  // Logout handler
  const logout = async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
        }
      });
    } catch (e) {
      console.error('Logout error:', e);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setCsrfToken('');
    }
  };

  // Trigger Re-Authentication password confirmation modal
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
    cancelReAuth
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
