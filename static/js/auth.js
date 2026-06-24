// statics/js/auth.js
async function login(email, password) {
    const data = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
    });
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return data;
}

async function register(name, email, password) {
    return await apiRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password })
    });
}

async function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/';
}

async function getCurrentUser() {
    try {
        const user = await apiRequest('/auth/me');
        return user;
    } catch (e) {
        return null;
    }
}

// Auto-refresh token interceptor (simplified)
setInterval(async () => {
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) {
        try {
            const data = await apiRequest('/auth/refresh', {
                method: 'POST',
                body: JSON.stringify({ refresh_token: refresh })
            });
            localStorage.setItem('access_token', data.access_token);
        } catch (e) { }
    }
}, 14 * 60 * 1000); // refresh every 14 minutes

function setUserLanguage(lang) {
    localStorage.setItem('preferred_language', lang);
}

function getUserLanguage() {
    return localStorage.getItem('preferred_language') || 'ur';
}