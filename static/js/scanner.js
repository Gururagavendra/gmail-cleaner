/**
 * Gmail Unsubscribe - Scanner Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Scanner = {
    formatDateRange(firstDate, lastDate) {
        /**
         * Parse RFC 2822 date string and format as MM/DD/YYYY
         * Example: "Wed, 15 Nov 2025 10:30:00 +0000" -> "11/15/2025"
         * Returns date range from oldest to newest
         */
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

        // Compare dates to determine order (oldest to newest)
        const firstDateObj = new Date(firstDate);
        const lastDateObj = new Date(lastDate);

        if (firstDateObj <= lastDateObj) {
            return `${first} to ${last}`;
        } else {
            return `${last} to ${first}`;
        }
    },

    async startScan() {
        if (GmailCleaner.scanning) return;

        const authResponse = await fetch('/api/auth-status');
        const authStatus = await authResponse.json();

        if (!authStatus.logged_in) {
            GmailCleaner.Auth.signIn();
            return;
        }

        GmailCleaner.scanning = true;
        GmailCleaner.UI.showView('unsubscribe');

        const scanBtn = document.getElementById('scanBtn');
        const progressCard = document.getElementById('progressCard');

        scanBtn.disabled = true;
        scanBtn.innerHTML = `
            <svg class="spinner" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
            </svg>
            Scanning...
        `;
        progressCard.classList.remove('hidden');

        const limit = document.getElementById('emailLimit').value;
        const filters = GmailCleaner.Filters.get();

        try {
            await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    limit: parseInt(limit),
                    filters: filters
                })
            });
            this.pollProgress();
        } catch (error) {
            alert('Error: ' + error.message);
            this.resetScan();
        }
    },

    async pollProgress() {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();

            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            const storageUsed = document.getElementById('storageUsed');
            const storageText = document.getElementById('storageText');

            progressBar.style.width = status.progress + '%';
            progressText.textContent = status.message;
            storageUsed.style.width = status.progress + '%';
            storageText.textContent = status.message;

            if (status.done) {
                if (!status.error) {
                    const resultsResponse = await fetch('/api/results');
                    GmailCleaner.results = await resultsResponse.json();
                    this.displayResults();
                    this.updateResultsBadge();

                    if (GmailCleaner.results.length > 0) {
                        setTimeout(() => GmailCleaner.UI.showView('unsubscribe'), 500);
                    }
                } else {
                    alert('Error: ' + status.error);
                }
                this.resetScan();
            } else {
                setTimeout(() => this.pollProgress(), 300);
            }
        } catch (error) {
            setTimeout(() => this.pollProgress(), 500);
        }
    },

    resetScan() {
        GmailCleaner.scanning = false;
        const scanBtn = document.getElementById('scanBtn');
        scanBtn.disabled = false;
        scanBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18">
                <path fill="currentColor" d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
            </svg>
            Start Scanning
        `;
    },

    updateResultsBadge() {
        const badge = document.getElementById('resultsBadge');
        badge.textContent = GmailCleaner.results.length;
        badge.style.display = GmailCleaner.results.length > 0 ? 'inline' : 'none';
    },

    displayResults() {
        const resultsList = document.getElementById('resultsList');
        const resultsSection = document.getElementById('resultsSection');
        const noResults = document.getElementById('noResults');

        resultsList.innerHTML = '';

        if (GmailCleaner.results.length === 0) {
            resultsSection.classList.add('hidden');
            noResults.classList.remove('hidden');
            return;
        }

        resultsSection.classList.remove('hidden');
        noResults.classList.add('hidden');

        GmailCleaner.results.forEach((r, i) => {
            const item = document.createElement('div');
            item.className = 'result-item';
            item.id = `result-item-${i}`;

            let actionButton;
            let comboButton;
            let typeLabel;

            if (r.type === 'one-click') {
                actionButton = `<button class="unsub-btn one-click" id="unsub-${i}" onclick="GmailCleaner.Scanner.autoUnsubscribe(${i})" title="Stop receiving emails from this sender. Existing emails remain in your inbox.">✓ Unsubscribe</button>`;
                comboButton = `<button class="unsub-btn combo-btn" id="combo-${i}" onclick="GmailCleaner.Scanner.unsubscribeAndDelete(${i})" title="Unsubscribe from this sender, then move all their emails to Trash.">Unsub & Delete</button>`;
                typeLabel = `<span class="type-badge type-auto">Auto</span>`;
            } else {
                actionButton = `<button class="unsub-btn manual" id="unsub-${i}" onclick="GmailCleaner.Scanner.openLink(${i})" title="Opens the unsubscribe page in a new tab. Complete the process there.">Open Link →</button>`;
                comboButton = `<button class="unsub-btn combo-btn" id="combo-${i}" onclick="GmailCleaner.Scanner.unsubscribeAndDelete(${i})" title="Opens unsubscribe page and moves all emails to Trash.">Unsub & Delete</button>`;
                typeLabel = `<span class="type-badge type-manual">Manual</span>`;
            }

            const deleteButton = `<button class="unsub-btn delete-btn" id="del-${i}" onclick="GmailCleaner.Scanner.deleteSubscriptionEmails(${i})" title="Move all emails from this sender to Trash. You can still unsubscribe afterward.">Delete ${r.count}</button>`;

            item.innerHTML = `
                <label class="checkbox-wrapper result-checkbox">
                    <input type="checkbox" class="result-cb" data-index="${i}" data-type="${r.type || 'manual'}" data-email="${GmailCleaner.UI.escapeHtml(r.email || '')}">
                    <span class="checkmark"></span>
                </label>
                <div class="result-content">
                    <div class="result-sender">${GmailCleaner.UI.escapeHtml(r.domain)} ${typeLabel}</div>
                    <div class="result-subject">${GmailCleaner.UI.escapeHtml(r.subjects[0] || 'No subject')}</div>
                </div>
                <div class="result-meta">
                    ${r.first_date && r.last_date ? `<div class="result-date-range">${GmailCleaner.Scanner.formatDateRange(r.first_date, r.last_date)}</div>` : ''}
                    <span class="result-count" id="count-${i}">${r.count} emails</span>
                </div>
                <div class="result-actions">
                    ${deleteButton}
                    ${comboButton}
                    ${actionButton}
                </div>
            `;
            resultsList.appendChild(item);
        });
    },

    async autoUnsubscribe(index) {
        const r = GmailCleaner.results[index];
        const btn = document.getElementById('unsub-' + index);

        btn.disabled = true;
        btn.textContent = 'Working...';

        try {
            const response = await fetch('/api/unsubscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain: r.domain, link: r.link })
            });
            const result = await response.json();

            if (result.success) {
                btn.textContent = '✓ Done!';
                btn.classList.remove('one-click');
                btn.classList.add('success');
                GmailCleaner.UI.showSuccessToast(`Successfully unsubscribed from ${r.domain}. You should stop receiving their emails.`);
            } else {
                btn.textContent = 'Open →';
                btn.classList.remove('one-click');
                btn.classList.add('manual');
                btn.onclick = () => this.openLink(index);
                btn.disabled = false;
            }
        } catch (error) {
            btn.textContent = 'Open →';
            btn.onclick = () => this.openLink(index);
            btn.disabled = false;
        }
    },

    openLink(index) {
        const r = GmailCleaner.results[index];
        const btn = document.getElementById('unsub-' + index);

        window.open(r.link, '_blank');
        btn.textContent = 'Opened ↗';
        btn.classList.add('success');
        // Keep button clickable so user can re-open if needed
    },

    toggleSelectAll() {
        const selectAll = document.getElementById('selectAll');
        document.querySelectorAll('.result-cb').forEach(cb => {
            cb.checked = selectAll.checked;
        });
    },

    async unsubscribeSelected() {
        const selected = [];
        document.querySelectorAll('.result-cb:checked').forEach(cb => {
            const index = parseInt(cb.dataset.index);
            const type = cb.dataset.type;
            const btn = document.getElementById('unsub-' + index);
            if (!btn.classList.contains('success')) {
                selected.push({ index, type });
            }
        });

        if (selected.length === 0) {
            alert('No items selected!');
            return;
        }

        const oneClick = selected.filter(s => s.type === 'one-click').length;
        const manual = selected.filter(s => s.type !== 'one-click').length;

        let message = `Selected ${selected.length} senders:\n`;
        if (oneClick > 0) message += `• ${oneClick} will auto-unsubscribe\n`;
        if (manual > 0) message += `• ${manual} will open in new tabs\n`;
        message += `\nContinue?`;

        if (!confirm(message)) return;

        let autoSuccess = 0;
        let manualOpened = 0;

        for (const { index, type } of selected) {
            if (type === 'one-click') {
                await this.autoUnsubscribe(index);
                const btn = document.getElementById('unsub-' + index);
                if (btn.classList.contains('success')) autoSuccess++;
                await new Promise(r => setTimeout(r, 200));
            }
        }

        for (const { index, type } of selected) {
            if (type !== 'one-click') {
                this.openLink(index);
                manualOpened++;
                await new Promise(r => setTimeout(r, 400));
            }
        }

        // Show toast notification
        let toastMessage = '';
        if (autoSuccess > 0 && manualOpened > 0) {
            toastMessage = `Successfully unsubscribed from ${autoSuccess} senders, ${manualOpened} links opened in tabs`;
        } else if (autoSuccess > 0) {
            toastMessage = `Successfully unsubscribed from ${autoSuccess} senders. You should stop receiving their emails.`;
        } else if (manualOpened > 0) {
            toastMessage = `Opened ${manualOpened} unsubscribe links in new tabs. Complete the process on each page.`;
            GmailCleaner.UI.showInfoToast(toastMessage);
            return;
        }

        if (toastMessage) {
            GmailCleaner.UI.showSuccessToast(toastMessage);
        }
    },

    exportResults() {
        if (!GmailCleaner.results.length) {
            alert('No results to export');
            return;
        }

        let text = 'Gmail Unsubscribe Links\n' + '='.repeat(50) + '\n\n';
        GmailCleaner.results.forEach((r, i) => {
            text += `${i + 1}. ${r.domain}\n`;
            text += `   Emails: ${r.count}\n`;
            text += `   Link: ${r.link}\n\n`;
        });

        const blob = new Blob([text], { type: 'text/plain' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'unsubscribe_links.txt';
        a.click();
    },

    async deleteSubscriptionEmails(index) {
        const r = GmailCleaner.results[index];
        const btn = document.getElementById('del-' + index);

        if (!r.email) {
            alert('No sender email found for this subscription.');
            return;
        }

        if (!confirm(`Delete ALL ${r.count} emails from ${r.email}?\n\nThis will move them to Trash.`)) {
            return;
        }

        btn.disabled = true;
        btn.classList.add('btn-deleting');
        btn.innerHTML = `
            <svg class="spinner" viewBox="0 0 24 24" width="14" height="14">
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
            </svg>
            Deleting...
        `;

        try {
            const response = await fetch('/api/delete-emails', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sender: r.email })
            });
            const result = await response.json();

            if (result.success) {
                btn.classList.remove('btn-deleting');
                btn.innerHTML = 'Deleted!';
                btn.classList.add('success');
                GmailCleaner.UI.showSuccessToast(`Moved ${result.deleted} emails from ${r.domain} to Trash.`);
                // Update count display to show deleted status
                const countEl = document.getElementById('count-' + index);
                if (countEl) {
                    countEl.textContent = '0 emails (deleted)';
                    countEl.classList.add('deleted');
                }
                // Disable combo button since emails are gone
                const comboBtn = document.getElementById('combo-' + index);
                if (comboBtn) {
                    comboBtn.disabled = true;
                    comboBtn.classList.add('success');
                    comboBtn.innerHTML = 'Deleted!';
                }
                // Mark result as deleted in memory
                r.deleted = true;
                r.count = 0;
            } else {
                btn.classList.remove('btn-deleting');
                btn.innerHTML = 'Error';
                alert('Error: ' + result.message);
                btn.disabled = false;
                btn.innerHTML = `Delete ${r.count}`;
            }
        } catch (error) {
            alert('Error: ' + error.message);
            btn.classList.remove('btn-deleting');
            btn.disabled = false;
            btn.innerHTML = `Delete ${r.count}`;
        }
    },

    async unsubscribeAndDelete(index) {
        const r = GmailCleaner.results[index];
        const comboBtn = document.getElementById('combo-' + index);
        const unsubBtn = document.getElementById('unsub-' + index);
        const delBtn = document.getElementById('del-' + index);

        if (!r.email) {
            alert('No sender email found for this subscription.');
            return;
        }

        const isOneClick = r.type === 'one-click';
        const confirmMsg = isOneClick
            ? `Unsubscribe from ${r.domain} and delete ALL ${r.count} emails?\n\nThis will:\n1. Stop future emails from this sender\n2. Move ${r.count} existing emails to Trash`
            : `Open unsubscribe page and delete ALL ${r.count} emails from ${r.domain}?\n\nThis will:\n1. Open the unsubscribe page (complete unsubscription there)\n2. Move ${r.count} existing emails to Trash`;

        if (!confirm(confirmMsg)) {
            return;
        }

        comboBtn.disabled = true;
        comboBtn.classList.add('btn-deleting');
        comboBtn.innerHTML = `
            <svg class="spinner" viewBox="0 0 24 24" width="14" height="14">
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
            </svg>
            Working...
        `;

        try {
            let unsubSuccess = false;

            if (isOneClick) {
                // One-click: Unsubscribe via API first
                const unsubResponse = await fetch('/api/unsubscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ domain: r.domain, link: r.link })
                });
                const unsubResult = await unsubResponse.json();
                unsubSuccess = unsubResult.success;

                if (unsubSuccess && unsubBtn) {
                    unsubBtn.textContent = '✓ Done!';
                    unsubBtn.classList.remove('one-click');
                    unsubBtn.classList.add('success');
                    unsubBtn.disabled = true;
                }
            } else {
                // Manual: Open link in new tab
                window.open(r.link, '_blank');
                unsubSuccess = true;
                if (unsubBtn) {
                    unsubBtn.textContent = 'Opened ↗';
                    unsubBtn.classList.add('success');
                }
            }

            // Now delete emails
            const deleteResponse = await fetch('/api/delete-emails', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sender: r.email })
            });
            const deleteResult = await deleteResponse.json();

            if (deleteResult.success) {
                comboBtn.classList.remove('btn-deleting');
                comboBtn.innerHTML = 'Done!';
                comboBtn.classList.add('success');

                // Update delete button
                if (delBtn) {
                    delBtn.innerHTML = 'Deleted!';
                    delBtn.classList.add('success');
                    delBtn.disabled = true;
                }

                // Update count display
                const countEl = document.getElementById('count-' + index);
                if (countEl) {
                    countEl.textContent = '0 emails (deleted)';
                    countEl.classList.add('deleted');
                }

                // Mark result as deleted in memory
                r.deleted = true;
                r.count = 0;

                const toastMsg = isOneClick
                    ? `Unsubscribed from ${r.domain} and moved ${deleteResult.deleted} emails to Trash.`
                    : `Opened unsubscribe page and moved ${deleteResult.deleted} emails to Trash.`;
                GmailCleaner.UI.showSuccessToast(toastMsg);
            } else {
                comboBtn.classList.remove('btn-deleting');
                comboBtn.innerHTML = 'Error';
                alert('Delete failed: ' + deleteResult.message);
                comboBtn.disabled = false;
                comboBtn.innerHTML = 'Unsub & Delete';
            }
        } catch (error) {
            alert('Error: ' + error.message);
            comboBtn.classList.remove('btn-deleting');
            comboBtn.disabled = false;
            comboBtn.innerHTML = 'Unsub & Delete';
        }
    },

    async deleteSelectedSubscriptions() {
        const checkboxes = document.querySelectorAll('.result-cb:checked');
        if (checkboxes.length === 0) {
            alert('Please select at least one subscription to delete emails from.');
            return;
        }

        let totalEmails = 0;
        const senderEmails = [];
        const indices = [];

        checkboxes.forEach(cb => {
            const index = parseInt(cb.dataset.index);
            const r = GmailCleaner.results[index];
            if (r && r.email) {
                totalEmails += r.count;
                senderEmails.push(r.email);
                indices.push(index);
            }
        });

        if (senderEmails.length === 0) {
            alert('No valid sender emails found for selected subscriptions.');
            return;
        }

        if (!confirm(`Delete ${totalEmails} emails from ${senderEmails.length} senders?\n\nThis will move them to Trash.`)) {
            return;
        }

        this.showDeleteOverlay(senderEmails.length, totalEmails);

        checkboxes.forEach(cb => {
            const index = parseInt(cb.dataset.index);
            const btn = document.getElementById('del-' + index);
            if (btn) {
                btn.disabled = true;
                btn.classList.add('btn-deleting');
                btn.innerHTML = `
                    <svg class="spinner" viewBox="0 0 24 24" width="14" height="14">
                        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
                    </svg>
                    Deleting...
                `;
            }
        });

        try {
            await fetch('/api/delete-emails-bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ senders: senderEmails })
            });

            this.pollDeleteProgress(checkboxes, indices);
        } catch (error) {
            this.hideDeleteOverlay();
            alert('Error: ' + error.message);
        }
    },

    async pollDeleteProgress(checkboxes, indices) {
        try {
            const response = await fetch('/api/delete-bulk-status');
            const status = await response.json();

            this.updateDeleteOverlay(status);

            if (status.done) {
                this.hideDeleteOverlay();

                if (!status.error) {
                    checkboxes.forEach(cb => {
                        const index = parseInt(cb.dataset.index);
                        const r = GmailCleaner.results[index];

                        // Update delete button
                        const btn = document.getElementById('del-' + index);
                        if (btn) {
                            btn.classList.remove('btn-deleting');
                            btn.innerHTML = 'Deleted!';
                            btn.classList.add('success');
                            btn.disabled = true;
                        }

                        // Update combo button
                        const comboBtn = document.getElementById('combo-' + index);
                        if (comboBtn) {
                            comboBtn.disabled = true;
                            comboBtn.classList.add('success');
                            comboBtn.innerHTML = 'Deleted!';
                        }

                        // Update count display
                        const countEl = document.getElementById('count-' + index);
                        if (countEl) {
                            countEl.textContent = '0 emails (deleted)';
                            countEl.classList.add('deleted');
                        }

                        // Mark result as deleted in memory
                        if (r) {
                            r.deleted = true;
                            r.count = 0;
                        }

                        // Uncheck the checkbox
                        cb.checked = false;
                    });

                    GmailCleaner.UI.showSuccessToast(`Moved ${status.deleted_count} emails to Trash.`);
                    document.getElementById('selectAll').checked = false;
                } else {
                    alert('Error: ' + status.error);
                    checkboxes.forEach(cb => {
                        const index = parseInt(cb.dataset.index);
                        const r = GmailCleaner.results[index];
                        const btn = document.getElementById('del-' + index);
                        if (btn && r) {
                            btn.classList.remove('btn-deleting');
                            btn.disabled = false;
                            btn.innerHTML = `Delete ${r.count}`;
                        }
                    });
                }
            } else {
                setTimeout(() => this.pollDeleteProgress(checkboxes, indices), 300);
            }
        } catch (error) {
            setTimeout(() => this.pollDeleteProgress(checkboxes, indices), 500);
        }
    },

    showDeleteOverlay(senderCount, emailCount) {
        this.hideDeleteOverlay();

        const overlay = document.createElement('div');
        overlay.id = 'scannerDeleteOverlay';
        overlay.className = 'delete-overlay';
        overlay.innerHTML = `
            <div class="delete-overlay-content">
                <svg class="delete-overlay-spinner spinner" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
                </svg>
                <h3>Deleting Emails...</h3>
                <div class="delete-progress-container">
                    <div class="delete-progress-bar" id="scannerDeleteProgressBar"></div>
                </div>
                <p id="scannerDeleteProgressText">Starting deletion...</p>
                <p class="delete-stats" id="scannerDeleteStats">0/${senderCount} senders | 0 emails deleted</p>
            </div>
        `;
        overlay.dataset.totalSenders = senderCount;
        document.body.appendChild(overlay);
    },

    updateDeleteOverlay(status) {
        const progressBar = document.getElementById('scannerDeleteProgressBar');
        const progressText = document.getElementById('scannerDeleteProgressText');
        const stats = document.getElementById('scannerDeleteStats');
        const overlay = document.getElementById('scannerDeleteOverlay');

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
                stats.textContent = `${status.deleted_count || 0} emails deleted`;
            }
        }
    },

    hideDeleteOverlay() {
        const overlay = document.getElementById('scannerDeleteOverlay');
        if (overlay) {
            overlay.remove();
        }
    },

    async unsubscribeAndDeleteSelected() {
        const checkboxes = document.querySelectorAll('.result-cb:checked');
        if (checkboxes.length === 0) {
            alert('Please select at least one subscription.');
            return;
        }

        let totalEmails = 0;
        const selected = [];

        checkboxes.forEach(cb => {
            const index = parseInt(cb.dataset.index);
            const r = GmailCleaner.results[index];
            if (r && r.email && !r.deleted) {
                totalEmails += r.count;
                selected.push({ index, r, type: r.type });
            }
        });

        if (selected.length === 0) {
            alert('No valid subscriptions selected (already deleted?).');
            return;
        }

        const oneClickCount = selected.filter(s => s.type === 'one-click').length;
        const manualCount = selected.filter(s => s.type !== 'one-click').length;

        let confirmMsg = `Unsubscribe and delete ${totalEmails} emails from ${selected.length} senders?\n\n`;
        if (oneClickCount > 0) confirmMsg += `• ${oneClickCount} will auto-unsubscribe\n`;
        if (manualCount > 0) confirmMsg += `• ${manualCount} will open unsubscribe pages\n`;
        confirmMsg += `\nAll ${totalEmails} emails will be moved to Trash.`;

        if (!confirm(confirmMsg)) {
            return;
        }

        this.showDeleteOverlay(selected.length, totalEmails);

        // Disable all buttons for selected items
        selected.forEach(({ index }) => {
            const delBtn = document.getElementById('del-' + index);
            const comboBtn = document.getElementById('combo-' + index);
            const unsubBtn = document.getElementById('unsub-' + index);
            if (delBtn) { delBtn.disabled = true; }
            if (comboBtn) {
                comboBtn.disabled = true;
                comboBtn.classList.add('btn-deleting');
                comboBtn.innerHTML = `<svg class="spinner" viewBox="0 0 24 24" width="14" height="14"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/></svg> Working...`;
            }
            if (unsubBtn) { unsubBtn.disabled = true; }
        });

        let processedCount = 0;
        let deletedEmails = 0;

        for (const { index, r, type } of selected) {
            try {
                // Step 1: Unsubscribe
                if (type === 'one-click') {
                    const unsubResponse = await fetch('/api/unsubscribe', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ domain: r.domain, link: r.link })
                    });
                    const unsubResult = await unsubResponse.json();
                    const unsubBtn = document.getElementById('unsub-' + index);
                    if (unsubResult.success && unsubBtn) {
                        unsubBtn.textContent = '✓ Done!';
                        unsubBtn.classList.add('success');
                    }
                } else {
                    // Manual: open link
                    window.open(r.link, '_blank');
                    const unsubBtn = document.getElementById('unsub-' + index);
                    if (unsubBtn) {
                        unsubBtn.textContent = 'Opened ↗';
                        unsubBtn.classList.add('success');
                    }
                    await new Promise(resolve => setTimeout(resolve, 300));
                }

                // Step 2: Delete emails
                const deleteResponse = await fetch('/api/delete-emails', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sender: r.email })
                });
                const deleteResult = await deleteResponse.json();

                if (deleteResult.success) {
                    deletedEmails += deleteResult.deleted;

                    // Update UI
                    const delBtn = document.getElementById('del-' + index);
                    const comboBtn = document.getElementById('combo-' + index);
                    const countEl = document.getElementById('count-' + index);

                    if (delBtn) {
                        delBtn.innerHTML = 'Deleted!';
                        delBtn.classList.add('success');
                    }
                    if (comboBtn) {
                        comboBtn.classList.remove('btn-deleting');
                        comboBtn.innerHTML = 'Done!';
                        comboBtn.classList.add('success');
                    }
                    if (countEl) {
                        countEl.textContent = '0 emails (deleted)';
                        countEl.classList.add('deleted');
                    }

                    r.deleted = true;
                    r.count = 0;
                }

                processedCount++;
                this.updateDeleteOverlay({
                    progress: Math.round((processedCount / selected.length) * 100),
                    message: `Processing ${processedCount}/${selected.length}...`,
                    deleted_count: deletedEmails
                });

            } catch (error) {
                console.error(`Error processing ${r.domain}:`, error);
            }
        }

        this.hideDeleteOverlay();

        // Uncheck all
        checkboxes.forEach(cb => cb.checked = false);
        document.getElementById('selectAll').checked = false;

        GmailCleaner.UI.showSuccessToast(`Processed ${processedCount} senders, moved ${deletedEmails} emails to Trash.`);
    }
};

// Global shortcuts
function startScan() { GmailCleaner.Scanner.startScan(); }
function toggleSelectAll() { GmailCleaner.Scanner.toggleSelectAll(); }
function unsubscribeSelected() { GmailCleaner.Scanner.unsubscribeSelected(); }
function exportResults() { GmailCleaner.Scanner.exportResults(); }
function deleteSelectedSubscriptions() { GmailCleaner.Scanner.deleteSelectedSubscriptions(); }
function unsubscribeAndDeleteSelected() { GmailCleaner.Scanner.unsubscribeAndDeleteSelected(); }
