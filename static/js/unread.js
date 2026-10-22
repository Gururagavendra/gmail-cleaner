/**
 * Gmail Cleaner - Unread Emails Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Unread = {
    scanning: false,
    results: [],
    inboxOnly: true,
    displayLimit: 20,
    MAX_POLL_RETRIES: 10,

    shouldConfirm() {
        const skipCheckbox = document.getElementById('unreadSkipConfirm');
        return !skipCheckbox || !skipCheckbox.checked;
    },

    changeDisplayLimit() {
        const select = document.getElementById('unreadDisplayLimit');
        if (select) {
            this.displayLimit = parseInt(select.value);
            this.displayResults();
        }
    },

    formatDateRange(firstDate, lastDate) {
        const formatDate = (dateStr) => {
            try {
                const date = new Date(dateStr);
                if (isNaN(date.getTime())) return null;
                const m = String(date.getMonth() + 1).padStart(2, '0');
                const d = String(date.getDate()).padStart(2, '0');
                const y = date.getFullYear();
                return `${m}/${d}/${y}`;
            } catch {
                return null;
            }
        };

        const first = formatDate(firstDate);
        const last = formatDate(lastDate);

        if (!first || !last) return '';
        if (first === last) return first;

        const firstDateObj = new Date(firstDate);
        const lastDateObj = new Date(lastDate);

        if (firstDateObj <= lastDateObj) {
            return `${first} to ${last}`;
        } else {
            return `${last} to ${first}`;
        }
    },

    toggleScope() {
        this.inboxOnly = !this.inboxOnly;
        this.updateScopeToggle();
    },

    updateScopeToggle() {
        const toggle = document.getElementById('unreadScopeToggle');
        const label = document.getElementById('unreadScopeLabel');
        if (toggle) toggle.checked = !this.inboxOnly;
        if (label) label.textContent = this.inboxOnly ? 'Inbox only' : 'All folders';
    },

    async startScan() {
        if (this.scanning) return;

        const authResponse = await fetch('/api/auth-status');
        const authStatus = await authResponse.json();

        if (!authStatus.logged_in) {
            GmailCleaner.Auth.signIn();
            return;
        }

        this.scanning = true;

        const scanBtn = document.getElementById('unreadScanBtn');
        const progressCard = document.getElementById('unreadProgressCard');

        scanBtn.disabled = true;
        scanBtn.innerHTML = `
            <svg class="spinner" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
            </svg>
            Scanning...
        `;
        progressCard.classList.remove('hidden');

        const limit = document.getElementById('unreadScanLimit').value;
        const filters = GmailCleaner.Filters.get();

        try {
            const response = await fetch('/api/unread-scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    limit: parseInt(limit),
                    inbox_only: this.inboxOnly,
                    filters: filters
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMsg = errorData.detail || `Request failed with status ${response.status}`;
                throw new Error(errorMsg);
            }

            this.pollProgress();
        } catch (error) {
            alert('Error: ' + error.message);
            this.resetScan();
        }
    },

    async pollProgress(retryCount = 0) {
        try {
            const response = await fetch('/api/unread-scan-status');
            const status = await response.json();

            const progressBar = document.getElementById('unreadProgressBar');
            const progressText = document.getElementById('unreadProgressText');

            progressBar.style.width = status.progress + '%';
            progressText.textContent = status.message;

            if (status.done) {
                if (!status.error) {
                    const resultsResponse = await fetch('/api/unread-scan-results');
                    this.results = await resultsResponse.json();
                    this.displayResults();
                } else {
                    alert('Error: ' + status.error);
                }
                this.resetScan();
            } else {
                setTimeout(() => this.pollProgress(0), 300);
            }
        } catch (error) {
            if (retryCount >= this.MAX_POLL_RETRIES) {
                alert('Error: Network error while polling scan status. Please try again.');
                this.resetScan();
                return;
            }
            setTimeout(() => this.pollProgress(retryCount + 1), 500);
        }
    },

    resetScan() {
        this.scanning = false;
        const scanBtn = document.getElementById('unreadScanBtn');
        scanBtn.disabled = false;
        scanBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18">
                <path fill="currentColor" d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
            </svg>
            Scan Unread
        `;
    },

    displayResults() {
        const resultsList = document.getElementById('unreadResultsList');
        const resultsSection = document.getElementById('unreadResultsSection');
        const noResults = document.getElementById('unreadNoResults');
        const badge = document.getElementById('unreadSendersBadge');

        resultsList.innerHTML = '';
        badge.textContent = this.results.length;

        if (this.results.length === 0) {
            resultsSection.classList.add('hidden');
            noResults.classList.remove('hidden');
            this.setActionButtonsEnabled(false);
            return;
        }

        resultsSection.classList.remove('hidden');
        noResults.classList.add('hidden');
        this.setActionButtonsEnabled(true);

        const displayCount = Math.min(this.results.length, this.displayLimit);
        this.results.slice(0, displayCount).forEach((r, i) => {
            const item = document.createElement('div');
            item.className = 'result-item';

            const dateRange = this.formatDateRange(r.first_date, r.last_date);
            const dateRangeDisplay = dateRange ? `<div class="result-date-range">${dateRange}</div>` : '';

            item.innerHTML = `
                <label class="checkbox-wrapper result-checkbox">
                    <input type="checkbox" class="unread-cb" data-index="${i}" data-email="${GmailCleaner.UI.escapeHtml(r.email)}">
                    <span class="checkmark"></span>
                </label>
                <div class="result-content">
                    <div class="result-sender">${GmailCleaner.UI.escapeHtml(r.email)}</div>
                    <div class="result-subject">${GmailCleaner.UI.escapeHtml(r.subjects[0] || 'No subject')}</div>
                    <div class="result-meta">
                        ${dateRangeDisplay}
                        <span class="result-count">${r.count} unread</span>
                    </div>
                </div>
                <div class="result-actions" style="display: flex; gap: 4px;">
                    <button class="unsub-btn" style="background: #10b981;" onclick="GmailCleaner.Unread.markReadSender(${i})" title="Mark as Read">
                        Read
                    </button>
                    <button class="unsub-btn" style="background: #3b82f6;" onclick="GmailCleaner.Unread.markReadAndArchiveSender(${i})" title="Mark as Read + Archive">
                        R+A
                    </button>
                    <button class="unsub-btn" style="background: #8b5cf6;" onclick="GmailCleaner.Unread.archiveSender(${i})" title="Archive Only">
                        Archive
                    </button>
                    <button class="unsub-btn" style="background: #ef4444;" onclick="GmailCleaner.Unread.deleteSender(${i})" title="Delete">
                        Del
                    </button>
                </div>
            `;
            resultsList.appendChild(item);
        });
    },

    setActionButtonsEnabled(enabled) {
        const buttons = [
            'unreadMarkReadBtn',
            'unreadMarkReadArchiveBtn',
            'unreadArchiveBtn',
            'unreadDeleteBtn'
        ];
        buttons.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) {
                btn.disabled = !enabled;
            }
        });
    },

    toggleSelectAll() {
        const selectAll = document.getElementById('unreadSelectAll');
        document.querySelectorAll('.unread-cb').forEach(cb => {
            cb.checked = selectAll.checked;
        });
    },

    async markReadSender(index) {
        await this.processSingleSender(index, '/api/unread-mark-read', 'Mark as read');
    },

    async markReadAndArchiveSender(index) {
        await this.processSingleSender(index, '/api/unread-mark-read-archive', 'Mark as read and archive');
    },

    async archiveSender(index) {
        await this.processSingleSender(index, '/api/unread-archive', 'Archive');
    },

    async deleteSender(index) {
        await this.processSingleSender(index, '/api/unread-delete', 'Delete');
    },

    async processSingleSender(index, endpoint, actionName) {
        const r = this.results[index];
        const buttons = document.querySelectorAll(`#unreadResultsList .result-item:nth-child(${index + 1}) .result-actions button`);

        if (this.shouldConfirm() && !confirm(`${actionName} ${r.count} emails from ${r.email}?`)) {
            return;
        }

        buttons.forEach(btn => {
            btn.disabled = true;
            btn.innerHTML = '...';
        });

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ senders: [r.email] })
            });

            if (!response.ok) {
                throw new Error('Request failed');
            }

            // Poll for completion
            await this.pollActionProgress(actionName, [r.email]);

            GmailCleaner.UI.showSuccessToast(`${actionName} completed for ${r.email}`);

            // Refresh results
            const resultsResponse = await fetch('/api/unread-scan-results');
            this.results = await resultsResponse.json();
            this.displayResults();

        } catch (error) {
            alert('Error: ' + error.message);
            buttons.forEach((btn, i) => {
                btn.disabled = false;
                btn.innerHTML = ['Read', 'R+A', 'Archive', 'Del'][i];
            });
        }
    },

    async markReadSelected() {
        await this.processSelectedSenders('/api/unread-mark-read', 'mark as read');
    },

    async markReadAndArchiveSelected() {
        await this.processSelectedSenders('/api/unread-mark-read-archive', 'mark as read and archive');
    },

    async archiveSelected() {
        await this.processSelectedSenders('/api/unread-archive', 'archive');
    },

    async deleteSelected() {
        await this.processSelectedSenders('/api/unread-delete', 'delete');
    },

    async processSelectedSenders(endpoint, actionName) {
        const checkboxes = document.querySelectorAll('.unread-cb:checked');
        if (checkboxes.length === 0) {
            alert('Please select at least one sender.');
            return;
        }

        let totalEmails = 0;
        const senderEmails = [];
        checkboxes.forEach(cb => {
            const index = parseInt(cb.dataset.index);
            const r = this.results[index];
            totalEmails += r.count;
            senderEmails.push(r.email);
        });

        if (this.shouldConfirm() && !confirm(`${actionName.charAt(0).toUpperCase() + actionName.slice(1)} ${totalEmails} emails from ${checkboxes.length} senders?`)) {
            return;
        }

        this.showActionOverlay(actionName, checkboxes.length);

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ senders: senderEmails })
            });

            if (!response.ok) {
                throw new Error('Request failed');
            }

            await this.pollActionProgressWithOverlay(actionName, checkboxes);

        } catch (error) {
            this.hideActionOverlay();
            alert('Error: ' + error.message);
        }
    },

    async pollActionProgress(actionName, senders) {
        const maxRetries = this.MAX_POLL_RETRIES;
        return new Promise((resolve, reject) => {
            let retryCount = 0;
            const poll = async () => {
                try {
                    const response = await fetch('/api/unread-action-status');
                    const status = await response.json();

                    retryCount = 0; // Reset on successful response
                    if (status.done) {
                        if (status.error) {
                            reject(new Error(status.error));
                        } else {
                            resolve(status);
                        }
                    } else {
                        setTimeout(poll, 300);
                    }
                } catch (error) {
                    retryCount++;
                    if (retryCount >= maxRetries) {
                        reject(new Error(`Network error while polling action status after ${maxRetries} retries`));
                        return;
                    }
                    setTimeout(poll, 500);
                }
            };
            poll();
        });
    },

    async pollActionProgressWithOverlay(actionName, checkboxes, retryCount = 0) {
        try {
            const response = await fetch('/api/unread-action-status');
            const status = await response.json();

            this.updateActionOverlay(status);

            if (status.done) {
                this.hideActionOverlay();

                if (!status.error) {
                    GmailCleaner.UI.showSuccessToast(
                        `Successfully processed ${status.affected_count} emails from ${checkboxes.length} senders`
                    );

                    // Refresh results
                    const resultsResponse = await fetch('/api/unread-scan-results');
                    this.results = await resultsResponse.json();
                    this.displayResults();
                    document.getElementById('unreadSelectAll').checked = false;
                } else {
                    alert('Error: ' + status.error);
                }
            } else {
                setTimeout(() => this.pollActionProgressWithOverlay(actionName, checkboxes, 0), 300);
            }
        } catch (error) {
            if (retryCount >= this.MAX_POLL_RETRIES) {
                this.hideActionOverlay();
                alert(`Error: Network error while polling action status after ${this.MAX_POLL_RETRIES} retries`);
                return;
            }
            setTimeout(() => this.pollActionProgressWithOverlay(actionName, checkboxes, retryCount + 1), 500);
        }
    },

    showActionOverlay(actionName, senderCount) {
        this.hideActionOverlay();

        const overlay = document.createElement('div');
        overlay.id = 'unreadActionOverlay';
        overlay.className = 'delete-overlay';
        overlay.innerHTML = `
            <div class="delete-overlay-content">
                <svg class="delete-overlay-spinner spinner" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
                </svg>
                <h3>Processing...</h3>
                <div class="delete-progress-container">
                    <div class="delete-progress-bar" id="unreadActionProgressBar"></div>
                </div>
                <p id="unreadActionProgressText">Starting ${actionName}...</p>
                <p class="delete-stats" id="unreadActionStats">0/${senderCount} senders</p>
            </div>
        `;
        overlay.dataset.totalSenders = senderCount;
        document.body.appendChild(overlay);
    },

    updateActionOverlay(status) {
        const progressBar = document.getElementById('unreadActionProgressBar');
        const progressText = document.getElementById('unreadActionProgressText');
        const stats = document.getElementById('unreadActionStats');
        const overlay = document.getElementById('unreadActionOverlay');

        if (progressBar) {
            progressBar.style.width = status.progress + '%';
        }
        if (progressText) {
            progressText.textContent = status.message;
        }
        if (stats && overlay) {
            const totalSenders = overlay.dataset.totalSenders || status.total_senders;
            if (status.progress <= 40) {
                stats.textContent = `Scanning ${status.current_sender || 0}/${totalSenders} senders...`;
            } else {
                stats.textContent = `${status.affected_count || 0} emails processed`;
            }
        }
    },

    hideActionOverlay() {
        const overlay = document.getElementById('unreadActionOverlay');
        if (overlay) {
            overlay.remove();
        }
    }
};

// Global shortcuts
function startUnreadScan() { GmailCleaner.Unread.startScan(); }
function toggleUnreadSelectAll() { GmailCleaner.Unread.toggleSelectAll(); }
function toggleUnreadScope() { GmailCleaner.Unread.toggleScope(); }
function markReadSelected() { GmailCleaner.Unread.markReadSelected(); }
function markReadAndArchiveSelected() { GmailCleaner.Unread.markReadAndArchiveSelected(); }
function archiveUnreadSelected() { GmailCleaner.Unread.archiveSelected(); }
function deleteUnreadSelected() { GmailCleaner.Unread.deleteSelected(); }
