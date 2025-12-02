/**
 * Gmail Unsubscribe - Scanner Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Scanner = {
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
            
            let actionButton;
            let typeLabel;
            
            if (r.type === 'one-click') {
                actionButton = `<button class="unsub-btn one-click" id="unsub-${i}" onclick="GmailCleaner.Scanner.autoUnsubscribe(${i})">✓ Unsubscribe</button>`;
                typeLabel = `<span class="type-badge type-auto">Auto</span>`;
            } else {
                actionButton = `<button class="unsub-btn manual" id="unsub-${i}" onclick="GmailCleaner.Scanner.openLink(${i})">Open Link →</button>`;
                typeLabel = `<span class="type-badge type-manual">Manual</span>`;
            }
            
            item.innerHTML = `
                <label class="checkbox-wrapper result-checkbox">
                    <input type="checkbox" class="result-cb" data-index="${i}" data-type="${r.type || 'manual'}">
                    <span class="checkmark"></span>
                </label>
                <div class="result-content">
                    <div class="result-sender">${GmailCleaner.UI.escapeHtml(r.domain)} ${typeLabel}</div>
                    <div class="result-subject">${GmailCleaner.UI.escapeHtml(r.subjects[0] || 'No subject')}</div>
                    <span class="result-count">${r.count} emails</span>
                </div>
                <div class="result-actions">
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
        
        let summary = '';
        if (autoSuccess > 0) summary += `✓ ${autoSuccess} auto-unsubscribed\n`;
        if (manualOpened > 0) summary += `🔗 ${manualOpened} opened (complete manually)`;
        alert(summary || 'Done!');
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
    }
};

// Global shortcuts
function startScan() { GmailCleaner.Scanner.startScan(); }
function toggleSelectAll() { GmailCleaner.Scanner.toggleSelectAll(); }
function unsubscribeSelected() { GmailCleaner.Scanner.unsubscribeSelected(); }
function exportResults() { GmailCleaner.Scanner.exportResults(); }
