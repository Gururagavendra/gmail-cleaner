/**
 * Gmail Cleaner - API helpers
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Session = {
    sessionKey: 'gc_session_id',
    tokenKey: 'gc_token_json',

    getSessionId() {
        let sessionId = localStorage.getItem(this.sessionKey);
        if (!sessionId) {
            if (window.crypto && typeof window.crypto.randomUUID === 'function') {
                sessionId = window.crypto.randomUUID();
            } else {
                sessionId = `sess_${Math.random().toString(36).slice(2)}${Date.now()}`;
            }
            localStorage.setItem(this.sessionKey, sessionId);
        }
        return sessionId;
    },

    getToken() {
        return localStorage.getItem(this.tokenKey);
    },

    setToken(tokenJson) {
        if (tokenJson) {
            localStorage.setItem(this.tokenKey, tokenJson);
        }
    },

    clearToken() {
        localStorage.removeItem(this.tokenKey);
    },

    encodeToken(tokenJson) {
        if (!tokenJson) return null;
        try {
            return btoa(unescape(encodeURIComponent(tokenJson)));
        } catch (error) {
            console.warn('Failed to encode auth token:', error);
            return null;
        }
    }
};

GmailCleaner.apiFetch = async function apiFetch(url, options = {}) {
    const sessionId = GmailCleaner.Session.getSessionId();
    const tokenJson = GmailCleaner.Session.getToken();
    const authToken = GmailCleaner.Session.encodeToken(tokenJson);

    const headers = new Headers(options.headers || {});
    headers.set('X-Session-Id', sessionId);
    if (authToken) {
        headers.set('X-Auth-Token', authToken);
    }

    const requestOptions = {
        ...options,
        headers
    };

    return fetch(url, requestOptions);
};
