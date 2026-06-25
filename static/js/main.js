// statics/js/main.js
document.addEventListener('DOMContentLoaded', () => {
    // Update auth buttons
    const authDiv = document.getElementById('auth-buttons');
    if (authDiv) {
        const token = localStorage.getItem('access_token');
        if (token) {
            authDiv.innerHTML = `<button onclick="logout()">Logout</button>`;
        } else {
            authDiv.innerHTML = `<a href="/login">Login</a> | <a href="/register">Register</a>`;
        }
    }

    // Sync language selector with localStorage
    const langSelect = document.getElementById('language-selector');
    if (langSelect) {
        const saved = getUserLanguage() || 'ur';
        langSelect.value = saved;
    }

    // اگر صارف لاگ ان ہے تو اس کی زبان لوڈ کریں اور سیٹ کریں
    getCurrentUser().then(user => {
        if (user && user.language) {
            setUserLanguage(user.language);
            if (langSelect) langSelect.value = user.language;
        }
    });
});