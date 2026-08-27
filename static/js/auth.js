/**
 * Gmail Unsubscribe - Authentication Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Auth = {
    // True once the consent URL has been rendered for the current sign-in.
    authUrlShown: false,

    async checkStatus() {
        try {
            const response = await fetch('/api/auth-status');
            const status = await response.json();
            this.updateUI(status);
        } catch (error) {
            console.error('Error checking auth status:', error);
            GmailCleaner.UI.showView('login');
        }
    },

    updateUI(authStatus) {
        const userSection = document.getElementById('userSection');

        if (authStatus.logged_in && authStatus.email) {
            const safeEmail = GmailCleaner.UI.escapeHtml(authStatus.email);
            const initial = authStatus.email.charAt(0).toUpperCase();
            userSection.innerHTML = `
                <span class="user-email">${safeEmail}</span>
                <div class="user-avatar" onclick="GmailCleaner.Auth.showUserMenu()" title="${safeEmail}">${initial}</div>
                <button class="btn btn-sm btn-secondary" onclick="GmailCleaner.Auth.signOut()">Sign Out</button>
            `;
            GmailCleaner.Filters.showBar(true);
            GmailCleaner.UI.showView('unsubscribe');

            // Load labels for filter dropdown
            this.loadLabelsForFilter();
        } else {
            userSection.innerHTML = '';
            GmailCleaner.Filters.showBar(false);
            GmailCleaner.UI.showView('login');
        }
    },

    async loadLabelsForFilter() {
        try {
            // Load labels using the Labels module
            const labels = await GmailCleaner.Labels.loadLabels();
            if (labels && labels.user) {
                GmailCleaner.Filters.populateLabelDropdown(labels.user);
            }
        } catch (error) {
            console.error('Error loading labels for filter:', error);
        }
    },

    async signIn() {
        const signInBtn = document.getElementById('signInBtn');

        if (signInBtn) {
            signInBtn.disabled = true;
            signInBtn.innerHTML = '<span>Signing in...</span>';
        }

        try {
            const statusResp = await fetch('/api/web-auth-status');
            const status = await statusResp.json();

            // Check if credentials exist
            if (!status.has_credentials) {
                this.resetSignInButton();
                alert('credentials.json not found!\n\nSetup instructions:\n1. Go to https://console.cloud.google.com/\n2. Create project → Enable Gmail API\n3. Create OAuth credentials (Desktop app)\n4. Download JSON → rename to credentials.json\n5. Put credentials.json in the app folder\n6. Restart the app');
                return;
            }

            const signInResp = await fetch('/api/sign-in', { method: 'POST' });
            const signInResult = await signInResp.json();

            if (signInResult.error) {
                this.resetSignInButton();
                alert('Sign-in error: ' + signInResult.error);
                return;
            }

            this.pollStatus();
        } catch (error) {
            alert('Error signing in: ' + error.message);
            this.resetSignInButton();
        }
    },

    // The OAuth flow runs on a background thread, so the consent URL only
    // becomes available a moment after /api/sign-in returns.
    async pollStatus(attempts = 0) {
        // 300s, matching the timeout the custom-redirect-port flow uses.
        const maxAttempts = 300;

        try {
            const response = await fetch('/api/auth-status');
            const status = await response.json();

            if (status.logged_in) {
                this.hideAuthUrl();
                this.updateUI(status);
                return;
            }

            if (!this.authUrlShown) {
                await this.fetchAuthUrl();
            }

            if (attempts < maxAttempts) {
                setTimeout(() => this.pollStatus(attempts + 1), 1000);
            } else {
                // Only this page gives up. The sign-in may still be live on the
                // server, so keep the link on screen and don't promise that
                // starting over will work.
                GmailCleaner.UI.showErrorToast(
                    'Still waiting for Google authorization. Finish it in the Google tab, then reload this page.'
                );
            }
        } catch (error) {
            console.error('Error polling auth status:', error);
            setTimeout(() => this.pollStatus(attempts + 1), 1000);
        }
    },

    async fetchAuthUrl() {
        try {
            const response = await fetch('/api/web-auth-status');
            const status = await response.json();
            if (status && status.pending_auth_url) {
                this.showAuthUrl(status.pending_auth_url);
            }
        } catch (error) {
            // Transient failure - the next poll will retry.
            console.error('Error fetching authorization URL:', error);
        }
    },

    // Only ever put http(s) URLs into an href, even though this one comes from
    // our own backend.
    isSafeHttpUrl(url) {
        if (typeof url !== 'string' || !url) return false;
        try {
            const protocol = new URL(url, window.location.origin).protocol;
            return protocol === 'https:' || protocol === 'http:';
        } catch (error) {
            return false;
        }
    },

    showAuthUrl(url) {
        if (this.authUrlShown) return;

        if (!this.isSafeHttpUrl(url)) {
            console.error('Refusing to display non-http(s) authorization URL');
            return;
        }

        const panel = document.getElementById('authUrlPanel');
        const link = document.getElementById('authUrlOpen');
        const input = document.getElementById('authUrlInput');
        const statusEl = document.getElementById('authUrlStatus');
        if (!panel || !link || !input) return;

        this.authUrlShown = true;
        link.href = url;
        input.value = url;
        panel.classList.remove('hidden');

        // Best-effort auto-open. The URL arrives asynchronously, so this is
        // outside the click's user-activation window and browsers will often
        // block it - hence the button and copyable link above, which are the
        // supported path rather than a fallback.
        let opened = null;
        try {
            opened = window.open(url, '_blank', 'noopener');
        } catch (error) {
            opened = null;
        }

        if (statusEl) {
            statusEl.textContent = opened
                ? 'Opened Google sign-in in a new tab. Waiting for you to finish…'
                : 'Authorize with Google to continue. Waiting for you to finish…';
        }
    },

    hideAuthUrl() {
        this.authUrlShown = false;

        const panel = document.getElementById('authUrlPanel');
        const link = document.getElementById('authUrlOpen');
        const input = document.getElementById('authUrlInput');
        const manual = document.getElementById('authUrlManual');

        if (panel) panel.classList.add('hidden');
        if (manual) manual.classList.add('hidden');
        if (link) link.href = '#';
        if (input) input.value = '';
    },

    toggleAuthUrl() {
        const manual = document.getElementById('authUrlManual');
        if (!manual) return;

        manual.classList.toggle('hidden');
        if (!manual.classList.contains('hidden')) {
            const input = document.getElementById('authUrlInput');
            if (input) input.select();
        }
    },

    async copyAuthUrl() {
        const input = document.getElementById('authUrlInput');
        if (!input || !input.value) return;

        try {
            // navigator.clipboard needs a secure context, which a plain
            // http://<host>:8766 deployment is not.
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(input.value);
            } else {
                input.select();
                document.execCommand('copy');
            }
            GmailCleaner.UI.showSuccessToast('Authorization link copied');
        } catch (error) {
            input.select();
            GmailCleaner.UI.showErrorToast('Could not copy automatically - press Ctrl+C');
        }
    },

    resetSignInButton() {
        const signInBtn = document.getElementById('signInBtn');
        if (signInBtn) {
            signInBtn.disabled = false;
            signInBtn.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20">
                <path fill="currentColor" d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.477,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.748L12.545,10.239z"/>
            </svg>
            Sign in with Google`;
        }
    },

    async checkWebAuthMode() {
        // No longer needed - sign in works everywhere now!
        return;
    },

    async signOut() {
        if (!confirm('Sign out of your Gmail account?')) return;

        try {
            await fetch('/api/sign-out', { method: 'POST' });
            this.hideAuthUrl();
            GmailCleaner.results = [];
            GmailCleaner.Scanner.updateResultsBadge();
            GmailCleaner.Scanner.displayResults();
            document.getElementById('selectAll').checked = false;
            this.checkStatus();
        } catch (error) {
            alert('Error signing out: ' + error.message);
        }
    },

    showUserMenu() {
        console.log('User menu clicked');
    }
};

// Global shortcuts for onclick handlers
function signIn() { GmailCleaner.Auth.signIn(); }
function signOut() { GmailCleaner.Auth.signOut(); }
