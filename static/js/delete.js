/**
 * Gmail Unsubscribe - Delete Emails Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Delete = {
    async startScan() {
        if (GmailCleaner.deleteScanning) return;
        
        const authResponse = await fetch('/api/auth-status');
        const authStatus = await authResponse.json();
        
        if (!authStatus.logged_in) {
            GmailCleaner.Auth.signIn();
            return;
        }
        
        GmailCleaner.deleteScanning = true;
        
        const scanBtn = document.getElementById('deleteScanBtn');
        const progressCard = document.getElementById('deleteProgressCard');
        
        scanBtn.disabled = true;
        scanBtn.innerHTML = `
            <svg class="spinner" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
            </svg>
            Scanning...
        `;
        progressCard.classList.remove('hidden');
        
        const limit = document.getElementById('deleteScanLimit').value;
        const filters = GmailCleaner.Filters.get();
        
        try {
            await fetch('/api/delete-scan', {
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
            const response = await fetch('/api/delete-scan-status');
            const status = await response.json();
            
            const progressBar = document.getElementById('deleteProgressBar');
            const progressText = document.getElementById('deleteProgressText');
            
            progressBar.style.width = status.progress + '%';
            progressText.textContent = status.message;
            
            if (status.done) {
                if (!status.error) {
                    const resultsResponse = await fetch('/api/delete-scan-results');
                    GmailCleaner.deleteResults = await resultsResponse.json();
                    this.displayResults();
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
        GmailCleaner.deleteScanning = false;
        const scanBtn = document.getElementById('deleteScanBtn');
        scanBtn.disabled = false;
        scanBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18">
                <path fill="currentColor" d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
            </svg>
            Scan Senders
        `;
    },

    displayResults() {
        const resultsList = document.getElementById('deleteResultsList');
        const resultsSection = document.getElementById('deleteResultsSection');
        const noResults = document.getElementById('deleteNoResults');
        const badge = document.getElementById('deleteSendersBadge');
        
        resultsList.innerHTML = '';
        badge.textContent = GmailCleaner.deleteResults.length;
        
        if (GmailCleaner.deleteResults.length === 0) {
            resultsSection.classList.add('hidden');
            noResults.classList.remove('hidden');
            return;
        }
        
        resultsSection.classList.remove('hidden');
        noResults.classList.add('hidden');
        
        GmailCleaner.deleteResults.forEach((r, i) => {
            const item = document.createElement('div');
            item.className = 'result-item';
            
            item.innerHTML = `
                <label class="checkbox-wrapper result-checkbox">
                    <input type="checkbox" class="delete-cb" data-index="${i}" data-email="${GmailCleaner.UI.escapeHtml(r.email)}">
                    <span class="checkmark"></span>
                </label>
                <div class="result-content">
                    <div class="result-sender">${GmailCleaner.UI.escapeHtml(r.email)}</div>
                    <div class="result-subject">${GmailCleaner.UI.escapeHtml(r.subjects[0] || 'No subject')}</div>
                    <span class="result-count">${r.count} emails</span>
                </div>
                <div class="result-actions">
                    <button class="unsub-btn delete-btn" id="delete-${i}" onclick="GmailCleaner.Delete.deleteSenderEmails(${i})">
                        Delete ${r.count}
                    </button>
                </div>
            `;
            resultsList.appendChild(item);
        });
    },

    toggleSelectAll() {
        const selectAll = document.getElementById('deleteSelectAll');
        document.querySelectorAll('.delete-cb').forEach(cb => {
            cb.checked = selectAll.checked;
        });
    },

    async deleteSenderEmails(index) {
        const r = GmailCleaner.deleteResults[index];
        const btn = document.getElementById('delete-' + index);
        
        if (!confirm(`Delete ALL ${r.count} emails from ${r.email}?\n\nThis will move them to Trash.`)) {
            return;
        }
        
        btn.disabled = true;
        btn.textContent = 'Deleting...';
        
        try {
            const response = await fetch('/api/delete-emails', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sender: r.email })
            });
            const result = await response.json();
            
            if (result.success) {
                btn.textContent = '✓ Deleted!';
                btn.classList.add('success');
                setTimeout(() => {
                    GmailCleaner.deleteResults = GmailCleaner.deleteResults.filter((_, i) => i !== index);
                    this.displayResults();
                }, 1000);
            } else {
                btn.textContent = 'Error';
                alert('Error: ' + result.error);
                btn.disabled = false;
                btn.textContent = `Delete ${r.count}`;
            }
        } catch (error) {
            alert('Error: ' + error.message);
            btn.disabled = false;
            btn.textContent = `Delete ${r.count}`;
        }
    },

    async deleteSelected() {
        const checkboxes = document.querySelectorAll('.delete-cb:checked');
        if (checkboxes.length === 0) {
            alert('Please select at least one sender to delete emails from.');
            return;
        }
        
        let totalEmails = 0;
        const senderEmails = [];
        checkboxes.forEach(cb => {
            const index = parseInt(cb.dataset.index);
            const r = GmailCleaner.deleteResults[index];
            totalEmails += r.count;
            senderEmails.push(r.email);
        });
        
        if (!confirm(`Delete ${totalEmails} emails from ${checkboxes.length} senders?\n\nThis will move them to Trash.`)) {
            return;
        }
        
        checkboxes.forEach(cb => {
            const index = parseInt(cb.dataset.index);
            const btn = document.getElementById('delete-' + index);
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Deleting...';
            }
        });
        
        try {
            const response = await fetch('/api/delete-emails-bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ senders: senderEmails })
            });
            const result = await response.json();
            
            if (result.success) {
                checkboxes.forEach(cb => {
                    const index = parseInt(cb.dataset.index);
                    const btn = document.getElementById('delete-' + index);
                    if (btn) {
                        btn.textContent = '✓ Deleted!';
                        btn.classList.add('success');
                    }
                });
                
                setTimeout(async () => {
                    const resultsResponse = await fetch('/api/delete-scan-results');
                    GmailCleaner.deleteResults = await resultsResponse.json();
                    this.displayResults();
                    document.getElementById('deleteSelectAll').checked = false;
                }, 800);
            } else {
                alert('Error: ' + result.error);
                checkboxes.forEach(cb => {
                    const index = parseInt(cb.dataset.index);
                    const r = GmailCleaner.deleteResults[index];
                    const btn = document.getElementById('delete-' + index);
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = `Delete ${r.count}`;
                    }
                });
            }
        } catch (error) {
            alert('Error: ' + error.message);
        }
    }
};

// Global shortcuts
function startDeleteScan() { GmailCleaner.Delete.startScan(); }
function toggleDeleteSelectAll() { GmailCleaner.Delete.toggleSelectAll(); }
function deleteSelectedSenders() { GmailCleaner.Delete.deleteSelected(); }
