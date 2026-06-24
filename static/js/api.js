const API_BASE = '/api/v1';

async function apiRequest(endpoint, options = {}) {
    // Remove any leading '/api' or '/api/v1' from the endpoint
    let clean = endpoint;
    if (clean.startsWith('/api/v1/')) clean = clean.substring(6);
    else if (clean.startsWith('/api/')) clean = clean.substring(4);
    if (!clean.startsWith('/')) clean = '/' + clean;
    const url = API_BASE + clean;

    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('access_token');
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Request failed');
    }
    return response.json();
}