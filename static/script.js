/**
 * Gmail Unsubscribe - Frontend JavaScript
 */

// State
let results = [];
let scanning = false;
let currentView = 'login';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
    checkWebAuthMode();
    setupNavigation();
});

// ============== Authentication ==============

async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth-status');
        const status = await response.json();
        updateAuthUI(status);
    } catch (error) {
        console.error('Error checking auth status:', error);
        showView('login');
    }
}

function updateAuthUI(authStatus) {
    const userSection = document.getElementById('userSection');
    
    if (authStatus.logged_in && authStatus.email) {
        const initial = authStatus.email.charAt(0).toUpperCase();
        userSection.innerHTML = `
            <span class="user-email">${authStatus.email}</span>
            <div class="user-avatar" onclick="showUserMenu()" title="${authStatus.email}">${initial}</div>
            <button class="btn btn-sm btn-secondary" onclick="signOut()">Sign Out</button>
        `;
        showView('unsubscribe');
    } else {
        userSection.innerHTML = '';
        showView('login');
    }
}

async function signIn() {
    try {
        const response = await fetch('/api/sign-in', { method: 'POST' });
        // Poll for login completion
        pollAuthStatus();
    } catch (error) {
        alert('Error signing in: ' + error.message);
    }
}

async function pollAuthStatus() {
    const response = await fetch('/api/auth-status');
    const status = await response.json();
    
    if (status.logged_in) {
        updateAuthUI(status);
    } else {
        setTimeout(pollAuthStatus, 1000);
    }
}

// ============== Web Auth (Docker/Headless) ==============

async function checkWebAuthMode() {
    try {
        const response = await fetch('/api/web-auth-status');
        const status = await response.json();
        
        // If in Docker mode and needs setup, show instructions
        if (status.web_auth_mode && status.needs_setup) {
            document.getElementById('dockerSetupSection')?.classList.remove('hidden');
            document.getElementById('signInBtn')?.classList.add('hidden');
        }
    } catch (error) {
        console.error('Error checking web auth mode:', error);
    }
}

async function signOut() {
    if (!confirm('Sign out of your Gmail account?')) return;
    
    try {
        await fetch('/api/sign-out', { method: 'POST' });
        // Clear all local state
        results = [];
        updateResultsBadge();
        displayResults();  // Clear the results list UI
        document.getElementById('selectAll').checked = false;
        checkAuthStatus();
    } catch (error) {
        alert('Error signing out: ' + error.message);
    }
}

// ============== Navigation ==============

function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.dataset.view;
            showView(view);
        });
    });
}

function showView(viewName) {
    currentView = viewName;
    
    // Hide all views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.add('hidden');
    });
    
    // Show requested view
    const viewId = viewName + 'View';
    const view = document.getElementById(viewId);
    if (view) {
        view.classList.remove('hidden');
    }
    
    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.view === viewName) {
            item.classList.add('active');
        }
    });
    
    // Special handling for unsubscribe view
    if (viewName === 'unsubscribe') {
        if (results.length === 0) {
            document.getElementById('noResults').classList.remove('hidden');
            document.getElementById('resultsSection').classList.add('hidden');
        } else {
            document.getElementById('noResults').classList.add('hidden');
            document.getElementById('resultsSection').classList.remove('hidden');
        }
    }
    
    // Refresh unread count when switching to Mark Read view
    if (viewName === 'markread') {
        refreshUnreadCount();
    }
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
}

// ============== Scanning ==============

async function startScan() {
    if (scanning) return;
    
    // Check auth first
    const authResponse = await fetch('/api/auth-status');
    const authStatus = await authResponse.json();
    
    if (!authStatus.logged_in) {
        signIn();
        return;
    }
    
    scanning = true;
    showView('unsubscribe');
    
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
    
    try {
        await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limit: parseInt(limit) })
        });
        pollScanProgress();
    } catch (error) {
        alert('Error: ' + error.message);
        resetScan();
    }
}

async function pollScanProgress() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        
        // Update progress bar
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
                results = await resultsResponse.json();
                displayResults();
                updateResultsBadge();
                
                // Auto switch to results if we have any
                if (results.length > 0) {
                    setTimeout(() => showView('unsubscribe'), 500);
                }
            } else {
                alert('Error: ' + status.error);
            }
            resetScan();
        } else {
            setTimeout(pollScanProgress, 300);
        }
    } catch (error) {
        setTimeout(pollScanProgress, 500);
    }
}

function resetScan() {
    scanning = false;
    const scanBtn = document.getElementById('scanBtn');
    scanBtn.disabled = false;
    scanBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
        Start Scanning
    `;
}

function updateResultsBadge() {
    const badge = document.getElementById('resultsBadge');
    badge.textContent = results.length;
    badge.style.display = results.length > 0 ? 'inline' : 'none';
}

// ============== Results ==============

function displayResults() {
    const resultsList = document.getElementById('resultsList');
    const resultsSection = document.getElementById('resultsSection');
    const noResults = document.getElementById('noResults');
    
    resultsList.innerHTML = '';
    
    if (results.length === 0) {
        resultsSection.classList.add('hidden');
        noResults.classList.remove('hidden');
        return;
    }
    
    resultsSection.classList.remove('hidden');
    noResults.classList.add('hidden');
    
    results.forEach((r, i) => {
        const item = document.createElement('div');
        item.className = 'result-item';
        
        // Only two types: one-click (Auto) or manual (Open Link)
        let actionButton;
        let typeLabel;
        
        if (r.type === 'one-click') {
            actionButton = `<button class="unsub-btn one-click" id="unsub-${i}" onclick="autoUnsubscribe(${i})">✓ Unsubscribe</button>`;
            typeLabel = `<span class="type-badge type-auto">Auto</span>`;
        } else {
            actionButton = `<button class="unsub-btn manual" id="unsub-${i}" onclick="openLink(${i})">Open Link →</button>`;
            typeLabel = `<span class="type-badge type-manual">Manual</span>`;
        }
        
        item.innerHTML = `
            <label class="checkbox-wrapper result-checkbox">
                <input type="checkbox" class="result-cb" data-index="${i}" data-type="${r.type || 'manual'}">
                <span class="checkmark"></span>
            </label>
            <div class="result-content">
                <div class="result-sender">${escapeHtml(r.domain)} ${typeLabel}</div>
                <div class="result-subject">${escapeHtml(r.subjects[0] || 'No subject')}</div>
                <span class="result-count">${r.count} emails</span>
            </div>
            <div class="result-actions">
                ${actionButton}
            </div>
        `;
        resultsList.appendChild(item);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll');
    document.querySelectorAll('.result-cb').forEach(cb => {
        cb.checked = selectAll.checked;
    });
}

async function unsubscribeSingle(index) {
    const r = results[index];
    const btn = document.getElementById('unsub-' + index);
    
    // Open the unsubscribe link in a new tab - user needs to complete it manually
    // Most sites require confirmation or login, so auto-unsubscribe doesn't work
    window.open(r.link, '_blank');
    
    // Mark as opened (user should confirm manually)
    btn.textContent = 'Opened ↗';
    btn.classList.add('success');
    btn.disabled = true;
}

// Auto-unsubscribe for one-click links
async function autoUnsubscribe(index) {
    const r = results[index];
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
            // Fall back to opening link
            btn.textContent = 'Open →';
            btn.classList.remove('one-click');
            btn.classList.add('manual');
            btn.onclick = () => openLink(index);
            btn.disabled = false;
        }
    } catch (error) {
        btn.textContent = 'Open →';
        btn.onclick = () => openLink(index);
        btn.disabled = false;
    }
}

// Open link for manual action
function openLink(index) {
    const r = results[index];
    const btn = document.getElementById('unsub-' + index);
    
    window.open(r.link, '_blank');
    btn.textContent = 'Opened ↗';
    btn.classList.add('success');
    btn.disabled = true;
}

async function unsubscribeSelected() {
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
    
    // Process auto-unsubscribe first
    for (const { index, type } of selected) {
        if (type === 'one-click') {
            await autoUnsubscribe(index);
            const btn = document.getElementById('unsub-' + index);
            if (btn.classList.contains('success')) autoSuccess++;
            await new Promise(r => setTimeout(r, 200));
        }
    }
    
    // Then open manual ones
    for (const { index, type } of selected) {
        if (type !== 'one-click') {
            openLink(index);
            manualOpened++;
            await new Promise(r => setTimeout(r, 400));
        }
    }
    
    let summary = '';
    if (autoSuccess > 0) summary += `✓ ${autoSuccess} auto-unsubscribed\n`;
    if (manualOpened > 0) summary += `🔗 ${manualOpened} opened (complete manually)`;
    alert(summary || 'Done!');
}

function exportResults() {
    if (!results.length) {
        alert('No results to export');
        return;
    }
    
    let text = 'Gmail Unsubscribe Links\n' + '='.repeat(50) + '\n\n';
    results.forEach((r, i) => {
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

// ============== Utilities ==============

function showUserMenu() {
    // Could add a dropdown menu here
    console.log('User menu clicked');
}

// ============== Mark as Read ==============

async function refreshUnreadCount() {
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
}

async function startMarkAsRead() {
    const btn = document.getElementById('markReadBtn');
    const progressCard = document.getElementById('markReadProgressCard');
    const countSelect = document.getElementById('markReadCount');
    
    let count = countSelect.value;
    if (count === 'all') {
        count = 999999;  // Large number to get all
    } else {
        count = parseInt(count);
    }
    
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
            body: JSON.stringify({ count })
        });
        pollMarkReadProgress();
    } catch (error) {
        alert('Error: ' + error.message);
        resetMarkReadBtn();
    }
}

async function pollMarkReadProgress() {
    try {
        const response = await fetch('/api/mark-read-status');
        const status = await response.json();
        
        const progressBar = document.getElementById('markReadProgressBar');
        const progressText = document.getElementById('markReadProgressText');
        
        progressBar.style.width = status.progress + '%';
        progressText.textContent = status.message;
        
        if (status.done) {
            resetMarkReadBtn();
            if (!status.error) {
                refreshUnreadCount();
            } else {
                alert('Error: ' + status.error);
            }
        } else {
            setTimeout(pollMarkReadProgress, 300);
        }
    } catch (error) {
        setTimeout(pollMarkReadProgress, 500);
    }
}

function resetMarkReadBtn() {
    const btn = document.getElementById('markReadBtn');
    btn.disabled = false;
    btn.innerHTML = `
        <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M18 7l-1.41-1.41-6.34 6.34 1.41 1.41L18 7zm4.24-1.41L11.66 16.17 7.48 12l-1.41 1.41L11.66 19l12-12-1.42-1.41zM.41 13.41L6 19l1.41-1.41L1.83 12 .41 13.41z"/>
        </svg>
        Mark as Read
    `;
}

// ============== Delete Emails ==============

let deleteResults = [];
let deleteScanning = false;

async function startDeleteScan() {
    if (deleteScanning) return;
    
    // Check auth first
    const authResponse = await fetch('/api/auth-status');
    const authStatus = await authResponse.json();
    
    if (!authStatus.logged_in) {
        signIn();
        return;
    }
    
    deleteScanning = true;
    
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
    
    try {
        await fetch('/api/delete-scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limit: parseInt(limit) })
        });
        pollDeleteScanProgress();
    } catch (error) {
        alert('Error: ' + error.message);
        resetDeleteScan();
    }
}

async function pollDeleteScanProgress() {
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
                deleteResults = await resultsResponse.json();
                displayDeleteResults();
            } else {
                alert('Error: ' + status.error);
            }
            resetDeleteScan();
        } else {
            setTimeout(pollDeleteScanProgress, 300);
        }
    } catch (error) {
        setTimeout(pollDeleteScanProgress, 500);
    }
}

function resetDeleteScan() {
    deleteScanning = false;
    const scanBtn = document.getElementById('deleteScanBtn');
    scanBtn.disabled = false;
    scanBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="18" height="18">
            <path fill="currentColor" d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
        Scan Senders
    `;
}

function displayDeleteResults() {
    const resultsList = document.getElementById('deleteResultsList');
    const resultsSection = document.getElementById('deleteResultsSection');
    const noResults = document.getElementById('deleteNoResults');
    const badge = document.getElementById('deleteSendersBadge');
    
    resultsList.innerHTML = '';
    badge.textContent = deleteResults.length;
    
    if (deleteResults.length === 0) {
        resultsSection.classList.add('hidden');
        noResults.classList.remove('hidden');
        return;
    }
    
    resultsSection.classList.remove('hidden');
    noResults.classList.add('hidden');
    
    deleteResults.forEach((r, i) => {
        const item = document.createElement('div');
        item.className = 'result-item';
        
        item.innerHTML = `
            <label class="checkbox-wrapper result-checkbox">
                <input type="checkbox" class="delete-cb" data-index="${i}" data-email="${escapeHtml(r.email)}">
                <span class="checkmark"></span>
            </label>
            <div class="result-content">
                <div class="result-sender">${escapeHtml(r.email)}</div>
                <div class="result-subject">${escapeHtml(r.subjects[0] || 'No subject')}</div>
                <span class="result-count">${r.count} emails</span>
            </div>
            <div class="result-actions">
                <button class="unsub-btn delete-btn" id="delete-${i}" onclick="deleteSenderEmails(${i})">
                    🗑️ Delete ${r.count}
                </button>
            </div>
        `;
        resultsList.appendChild(item);
    });
}

function toggleDeleteSelectAll() {
    const selectAll = document.getElementById('deleteSelectAll');
    document.querySelectorAll('.delete-cb').forEach(cb => {
        cb.checked = selectAll.checked;
    });
}

async function deleteSenderEmails(index) {
    const r = deleteResults[index];
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
            // Remove from list after a short delay
            setTimeout(() => {
                deleteResults = deleteResults.filter((_, i) => i !== index);
                displayDeleteResults();
            }, 1000);
        } else {
            btn.textContent = 'Error';
            alert('Error: ' + result.error);
            btn.disabled = false;
            btn.textContent = `🗑️ Delete ${r.count}`;
        }
    } catch (error) {
        alert('Error: ' + error.message);
        btn.disabled = false;
        btn.textContent = `🗑️ Delete ${r.count}`;
    }
}

async function deleteSelectedSenders() {
    const checkboxes = document.querySelectorAll('.delete-cb:checked');
    if (checkboxes.length === 0) {
        alert('Please select at least one sender to delete emails from.');
        return;
    }
    
    // Calculate total emails and collect sender emails
    let totalEmails = 0;
    const senderEmails = [];
    checkboxes.forEach(cb => {
        const index = parseInt(cb.dataset.index);
        const r = deleteResults[index];
        totalEmails += r.count;
        senderEmails.push(r.email);
    });
    
    if (!confirm(`Delete ${totalEmails} emails from ${checkboxes.length} senders?\n\nThis will move them to Trash.`)) {
        return;
    }
    
    // Disable all selected buttons
    checkboxes.forEach(cb => {
        const index = parseInt(cb.dataset.index);
        const btn = document.getElementById('delete-' + index);
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Deleting...';
        }
    });
    
    try {
        // Use BULK delete - much faster!
        const response = await fetch('/api/delete-emails-bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ senders: senderEmails })
        });
        const result = await response.json();
        
        if (result.success) {
            // Mark all as done
            checkboxes.forEach(cb => {
                const index = parseInt(cb.dataset.index);
                const btn = document.getElementById('delete-' + index);
                if (btn) {
                    btn.textContent = '✓ Deleted!';
                    btn.classList.add('success');
                }
            });
            
            // Refresh results after short delay
            setTimeout(async () => {
                const resultsResponse = await fetch('/api/delete-scan-results');
                deleteResults = await resultsResponse.json();
                displayDeleteResults();
                document.getElementById('deleteSelectAll').checked = false;
            }, 800);
        } else {
            alert('Error: ' + result.error);
            // Re-enable buttons
            checkboxes.forEach(cb => {
                const index = parseInt(cb.dataset.index);
                const r = deleteResults[index];
                const btn = document.getElementById('delete-' + index);
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = `🗑️ Delete ${r.count}`;
                }
            });
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
