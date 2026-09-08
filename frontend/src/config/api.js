// Centralized API configuration

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || ''
).replace(/\/+$/, '');

export default API_BASE_URL;