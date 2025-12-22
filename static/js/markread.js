/**
 * Gmail Unsubscribe - Mark as Read Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.MarkRead = {
    async refreshUnreadCount() {
        const countEl = document.querySelector('#unreadCount .count-number');
        countEl.textContent = '...';

        try {
            const response = await fetch('/api/unread-count');
            const data = await response.json();

            if (data.error) {
                countEl.textContent = 'Error';
            } else {
                countEl.textContent = data.count.toLocaleString();
            }
        } catch (error) {
            countEl.textContent = 'Error';
        }
    },

    async start() {
        const btn = document.getElementById('markReadBtn');
        const progressCard = document.getElementById('markReadProgressCard');
        const countSelect = document.getElementById('markReadCount');

        let count = countSelect.value;
        if (count === 'all') {
            count = 0;
        } else {
            count = parseInt(count);
        }

        const filters = GmailCleaner.Filters.get();

        btn.disabled = true;
        btn.innerHTML = `
            <svg class="spinner" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/>
            </svg>
            Working...
        `;
        progressCard.classList.remove('hidden');

        try {
            await fetch('/api/mark-read', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    count,
                    filters: filters
                })
            });
            this.pollProgress();
        } catch (error) {
            GmailCleaner.UI.showErrorToast('Error: ' + error.message);
            this.resetButton();
        }
    },

    async pollProgress() {
        try {
            const response = await fetch('/api/mark-read-status');
            const status = await response.json();

            const progressBar = document.getElementById('markReadProgressBar');
            const progressText = document.getElementById('markReadProgressText');

            progressBar.style.width = status.progress + '%';
            progressText.textContent = status.message;

            if (status.done) {
                this.resetButton();
                if (!status.error) {
                    // Show toast notification
                    if (status.marked_count > 0) {
                        GmailCleaner.UI.showSuccessToast(
                            `Successfully marked ${status.marked_count.toLocaleString()} emails as read. Your inbox is cleaner now!`
                        );
                    } else {
                        GmailCleaner.UI.showInfoToast('No unread emails found matching the selected filters.');
                    }
                    this.refreshUnreadCount();
                } else {
                    GmailCleaner.UI.showErrorToast('Error: ' + status.error);
                }
            } else {
                setTimeout(() => this.pollProgress(), 300);
            }
        } catch (error) {
            setTimeout(() => this.pollProgress(), 500);
        }
    },

    resetButton() {
        const btn = document.getElementById('markReadBtn');
        btn.disabled = false;
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18">
                <path fill="currentColor" d="M18 7l-1.41-1.41-6.34 6.34 1.41 1.41L18 7zm4.24-1.41L11.66 16.17 7.48 12l-1.41 1.41L11.66 19l12-12-1.42-1.41zM.41 13.41L6 19l1.41-1.41L1.83 12 .41 13.41z"/>
            </svg>
            Mark as Read
        `;
    }
};

// Global shortcuts
function startMarkAsRead() { GmailCleaner.MarkRead.start(); }
function refreshUnreadCount() { GmailCleaner.MarkRead.refreshUnreadCount(); }
