// Centralized API configuration
// Resolves relative endpoint paths or environment variable override

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

export default API_BASE_URL;

