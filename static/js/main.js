// statics/js/main.js
document.addEventListener('DOMContentLoaded', () => {
    // Update auth buttons in header
    const authDiv = document.getElementById('auth-buttons');
    if (authDiv) {
        const token = localStorage.getItem('access_token');
        if (token) {
            authDiv.innerHTML = `<button onclick="logout()">Logout</button>`;
        } else {
            authDiv.innerHTML = `<a href="/login">Login</a> | <a href="/register">Register</a>`;
        }
    }
});