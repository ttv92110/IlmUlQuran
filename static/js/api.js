const API_BASE = '/api/v1';

// ===== GLOBAL LOADER CONTROLS =====
function showLoader(message = 'Loading...') {
    let overlay = document.getElementById('globalLoader');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'globalLoader';
        overlay.className = 'loader-overlay';
        overlay.innerHTML = `
      <div class="loader-spinner"></div>
      <div class="loader-text" id="loaderText">${message}</div>
    `;
        document.body.appendChild(overlay);
    } else {
        document.getElementById('loaderText').innerText = message;
    }
    overlay.classList.add('active');
}

function hideLoader() {
    const overlay = document.getElementById('globalLoader');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

// ===== API REQUEST WITH AUTOMATIC LOADER =====
async function apiRequest(endpoint, options = {}, showLoaderOnFetch = true) {
    // Clean endpoint
    let clean = endpoint;
    if (clean.startsWith('/api/v1/')) clean = clean.substring(6);
    else if (clean.startsWith('/api/')) clean = clean.substring(4);
    if (!clean.startsWith('/')) clean = '/' + clean;
    const url = API_BASE + clean;

    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('access_token');
    if (token) headers['Authorization'] = `Bearer ${token}`;

    // If showLoaderOnFetch is true, show loader
    if (showLoaderOnFetch) {
        showLoader('Please wait...');
    }

    try {
        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }
        const data = await response.json();
        return data;
    } finally {
        if (showLoaderOnFetch) {
            hideLoader();
        }
    }
}

// ===== BUTTON LOADER HELPER =====
function setButtonLoading(btn, isLoading, originalText = null) {
    if (isLoading) {
        btn.classList.add('btn-loading');
        btn.dataset.originalText = btn.dataset.originalText || btn.innerHTML;
        btn.innerHTML = `<span class="btn-loader"></span> Loading...`;
    } else {
        btn.classList.remove('btn-loading');
        if (btn.dataset.originalText) {
            btn.innerHTML = btn.dataset.originalText;
            delete btn.dataset.originalText;
        }
    }
}