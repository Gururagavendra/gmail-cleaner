/**
 * Gmail Cleaner - Label Management Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Labels = {
    labels: {
        system: [],
        user: []
    },

    async loadLabels() {
        try {
            const response = await fetch('/api/labels');
            const data = await response.json();

            if (data.success) {
                this.labels.system = data.system_labels || [];
                this.labels.user = data.user_labels || [];
                return this.labels;
            } else {
                console.error('Failed to load labels:', data.error);
                return null;
            }
        } catch (error) {
            console.error('Error loading labels:', error);
            return null;
        }
    },

    async createLabel(name) {
        try {
            const response = await fetch('/api/labels', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            const result = await response.json();

            if (result.success) {
                // Add to local cache
                this.labels.user.push(result.label);
                this.labels.user.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
            }

            return result;
        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    async deleteLabel(labelId) {
        try {
            const response = await fetch(`/api/labels/${encodeURIComponent(labelId)}`, {
                method: 'DELETE'
            });
            const result = await response.json();

            if (result.success) {
                // Remove from local cache
                this.labels.user = this.labels.user.filter(l => l.id !== labelId);
            }

            return result;
        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    async applyLabelToSenders(labelId, senders) {
        try {
            const response = await fetch('/api/apply-label', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label_id: labelId, senders })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    async removeLabelFromSenders(labelId, senders) {
        try {
            const response = await fetch('/api/remove-label', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label_id: labelId, senders })
            });
            return await response.json();
        } catch (error) {
            return { success: false, error: error.message };
        }
    },

    async pollLabelOperation(onComplete) {
        try {
            const response = await fetch('/api/label-operation-status');
            const status = await response.json();

            if (status.done) {
                onComplete(status);
            } else {
                setTimeout(() => this.pollLabelOperation(onComplete), 300);
            }

            return status;
        } catch (error) {
            setTimeout(() => this.pollLabelOperation(onComplete), 500);
        }
    },

    // Show label dropdown for selecting/creating labels
    showLabelDropdown(buttonElement, onSelect) {
        // Remove any existing dropdown
        this.hideLabelDropdown();

        const dropdown = document.createElement('div');
        dropdown.id = 'labelDropdown';
        dropdown.className = 'label-dropdown';

        // Build dropdown content
        let html = '<div class="label-dropdown-content">';
        html += '<div class="label-dropdown-header">Select or Create Label</div>';

        // Create new label input
        html += `
            <div class="label-create-section">
                <input type="text" id="newLabelInput" placeholder="New label name..." class="label-input">
                <button id="createLabelBtn" class="label-create-btn">Create</button>
            </div>
        `;

        // Existing labels
        if (this.labels.user.length > 0) {
            html += '<div class="label-list-header">Your Labels</div>';
            html += '<div class="label-list">';
            this.labels.user.forEach(label => {
                html += `
                    <div class="label-item" data-id="${GmailCleaner.UI.escapeHtml(label.id)}" data-name="${GmailCleaner.UI.escapeHtml(label.name)}">
                        <span class="label-icon">🏷️</span>
                        <span class="label-name">${GmailCleaner.UI.escapeHtml(label.name)}</span>
                    </div>
                `;
            });
            html += '</div>';
        } else {
            html += '<div class="label-empty">No custom labels yet</div>';
        }

        html += '</div>';
        dropdown.innerHTML = html;

        // Position dropdown
        const rect = buttonElement.getBoundingClientRect();
        dropdown.style.position = 'fixed';
        dropdown.style.top = (rect.bottom + 5) + 'px';
        dropdown.style.left = rect.left + 'px';
        dropdown.style.zIndex = '10000';

        document.body.appendChild(dropdown);

        // Event handlers
        dropdown.querySelectorAll('.label-item').forEach(item => {
            item.addEventListener('click', () => {
                const labelId = item.dataset.id;
                const labelName = item.dataset.name;
                this.hideLabelDropdown();
                onSelect({ id: labelId, name: labelName });
            });
        });

        const createBtn = dropdown.querySelector('#createLabelBtn');
        const newLabelInput = dropdown.querySelector('#newLabelInput');

        createBtn.addEventListener('click', async () => {
            const name = newLabelInput.value.trim();
            if (!name) return;

            createBtn.disabled = true;
            createBtn.textContent = '...';

            const result = await this.createLabel(name);

            if (result.success) {
                this.hideLabelDropdown();
                onSelect(result.label);
            } else {
                alert('Error: ' + result.error);
                createBtn.disabled = false;
                createBtn.textContent = 'Create';
            }
        });

        newLabelInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                createBtn.click();
            }
        });

        // Close on click outside
        setTimeout(() => {
            document.addEventListener('click', this._dropdownClickHandler = (e) => {
                if (!dropdown.contains(e.target) && e.target !== buttonElement) {
                    this.hideLabelDropdown();
                }
            });
        }, 10);
    },

    hideLabelDropdown() {
        const dropdown = document.getElementById('labelDropdown');
        if (dropdown) {
            dropdown.remove();
        }
        if (this._dropdownClickHandler) {
            document.removeEventListener('click', this._dropdownClickHandler);
            this._dropdownClickHandler = null;
        }
    },

    // Show label operation overlay
    showLabelOverlay(action, labelName, emailCount) {
        this.hideLabelOverlay();

        const actionText = action === 'apply' ? 'Applying' : 'Removing';
        const overlay = document.createElement('div');
        overlay.id = 'labelOverlay';
        overlay.className = 'label-overlay';
        overlay.innerHTML = `
            <div class="label-overlay-content">
                <svg class="label-overlay-spinner spinner" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
                </svg>
                <h3>${actionText} Label "${GmailCleaner.UI.escapeHtml(labelName)}"...</h3>
                <div class="label-progress-container">
                    <div class="label-progress-bar" id="labelProgressBar"></div>
                </div>
                <p id="labelProgressText">Starting...</p>
            </div>
        `;
        document.body.appendChild(overlay);
    },

    updateLabelOverlay(status) {
        const progressBar = document.getElementById('labelProgressBar');
        const progressText = document.getElementById('labelProgressText');

        if (progressBar) {
            progressBar.style.width = status.progress + '%';
        }
        if (progressText) {
            progressText.textContent = status.message;
        }
    },

    hideLabelOverlay() {
        const overlay = document.getElementById('labelOverlay');
        if (overlay) {
            overlay.remove();
        }
    },

    // Show apply label dropdown
    async showApplyLabelDropdown(event) {
        event.stopPropagation();

        // Check if senders are selected
        const checkboxes = document.querySelectorAll('.delete-cb:checked');
        if (checkboxes.length === 0) {
            alert('Please select at least one sender first.');
            return;
        }

        // Load labels if not loaded
        if (this.labels.user.length === 0 && this.labels.system.length === 0) {
            await this.loadLabels();
        }

        this.showLabelDropdown(event.target.closest('button'), async (label) => {
            await this.applyLabelToSelected(label);
        });
    },

    // Show remove label dropdown
    async showRemoveLabelDropdown(event) {
        event.stopPropagation();

        // Check if senders are selected
        const checkboxes = document.querySelectorAll('.delete-cb:checked');
        if (checkboxes.length === 0) {
            alert('Please select at least one sender first.');
            return;
        }

        // Load labels if not loaded
        if (this.labels.user.length === 0 && this.labels.system.length === 0) {
            await this.loadLabels();
        }

        this.showLabelDropdown(event.target.closest('button'), async (label) => {
            await this.removeLabelFromSelected(label);
        });
    },

    // Apply label to selected senders
    async applyLabelToSelected(label) {
        const checkboxes = document.querySelectorAll('.delete-cb:checked');
        const senders = [];

        checkboxes.forEach(cb => {
            senders.push(cb.dataset.email);
        });

        this.showLabelOverlay('apply', label.name, senders.length);

        try {
            const result = await this.applyLabelToSenders(label.id, senders);

            if (result.status === 'started') {
                // Poll for progress
                this.pollLabelOperation((status) => {
                    this.updateLabelOverlay(status);
                    if (status.done) {
                        this.hideLabelOverlay();
                        if (status.error) {
                            alert('Error: ' + status.error);
                        } else {
                            alert(`Label "${label.name}" applied to emails from ${senders.length} sender(s)`);
                        }
                    }
                });
            } else if (result.error) {
                this.hideLabelOverlay();
                alert('Error: ' + result.error);
            }
        } catch (error) {
            this.hideLabelOverlay();
            alert('Error: ' + error.message);
        }
    },

    // Remove label from selected senders
    async removeLabelFromSelected(label) {
        const checkboxes = document.querySelectorAll('.delete-cb:checked');
        const senders = [];

        checkboxes.forEach(cb => {
            senders.push(cb.dataset.email);
        });

        this.showLabelOverlay('remove', label.name, senders.length);

        try {
            const result = await this.removeLabelFromSenders(label.id, senders);

            if (result.status === 'started') {
                // Poll for progress
                this.pollLabelOperation((status) => {
                    this.updateLabelOverlay(status);
                    if (status.done) {
                        this.hideLabelOverlay();
                        if (status.error) {
                            alert('Error: ' + status.error);
                        } else {
                            alert(`Label "${label.name}" removed from emails from ${senders.length} sender(s)`);
                        }
                    }
                });
            } else if (result.error) {
                this.hideLabelOverlay();
                alert('Error: ' + result.error);
            }
        } catch (error) {
            this.hideLabelOverlay();
            alert('Error: ' + error.message);
        }
    },

    // Archive selected senders' emails
    async archiveSelected() {
        const checkboxes = document.querySelectorAll('.delete-cb:checked');
        if (checkboxes.length === 0) {
            alert('Please select at least one sender first.');
            return;
        }

        const senders = [];
        let totalEmails = 0;
        checkboxes.forEach(cb => {
            senders.push(cb.dataset.email);
            const index = parseInt(cb.dataset.index);
            totalEmails += GmailCleaner.deleteResults[index]?.count || 0;
        });

        if (!confirm(`Archive emails from ${senders.length} sender(s)?\n\nThis will remove ${totalEmails} emails from your inbox but keep them in "All Mail".`)) {
            return;
        }

        this.showArchiveOverlay(senders.length);

        try {
            const response = await fetch('/api/archive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ senders })
            });

            const result = await response.json();

            if (result.status === 'started') {
                this.pollArchiveStatus();
            } else if (result.error) {
                this.hideArchiveOverlay();
                alert('Error: ' + result.error);
            }
        } catch (error) {
            this.hideArchiveOverlay();
            alert('Error: ' + error.message);
        }
    },

    async pollArchiveStatus() {
        try {
            const response = await fetch('/api/archive-status');
            const status = await response.json();

            this.updateArchiveOverlay(status);

            if (status.done) {
                this.hideArchiveOverlay();
                if (status.error) {
                    alert('Error: ' + status.error);
                } else {
                    alert(`Archived ${status.archived_count} emails from ${status.total_senders} sender(s)`);
                }
            } else {
                setTimeout(() => this.pollArchiveStatus(), 300);
            }
        } catch (error) {
            setTimeout(() => this.pollArchiveStatus(), 500);
        }
    },

    showArchiveOverlay(senderCount) {
        this.hideLabelOverlay();
        this.hideArchiveOverlay();

        const overlay = document.createElement('div');
        overlay.id = 'archiveOverlay';
        overlay.className = 'label-overlay';
        overlay.innerHTML = `
            <div class="label-overlay-content">
                <svg class="label-overlay-spinner spinner" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
                </svg>
                <h3>Archiving Emails...</h3>
                <div class="label-progress-container">
                    <div class="label-progress-bar" id="archiveProgressBar" style="background: #f59e0b;"></div>
                </div>
                <p id="archiveProgressText">Starting...</p>
                <p class="label-stats">0/${senderCount} senders processed</p>
            </div>
        `;
        document.body.appendChild(overlay);
    },

    updateArchiveOverlay(status) {
        const progressBar = document.getElementById('archiveProgressBar');
        const progressText = document.getElementById('archiveProgressText');

        if (progressBar) {
            progressBar.style.width = status.progress + '%';
        }
        if (progressText) {
            progressText.textContent = status.message;
        }
    },

    hideArchiveOverlay() {
        const overlay = document.getElementById('archiveOverlay');
        if (overlay) {
            overlay.remove();
        }
    },

    // Mark selected senders' emails as important
    async markImportantSelected() {
        const checkboxes = document.querySelectorAll('.delete-cb:checked');
        if (checkboxes.length === 0) {
            alert('Please select at least one sender first.');
            return;
        }

        const senders = [];
        let totalEmails = 0;
        checkboxes.forEach(cb => {
            senders.push(cb.dataset.email);
            const index = parseInt(cb.dataset.index);
            totalEmails += GmailCleaner.deleteResults[index]?.count || 0;
        });

        if (!confirm(`Mark ${totalEmails} emails from ${senders.length} sender(s) as important?`)) {
            return;
        }

        this.showImportantOverlay(senders.length);

        try {
            const response = await fetch('/api/mark-important', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ senders, important: true })
            });

            const result = await response.json();

            if (result.status === 'started') {
                this.pollImportantStatus();
            } else if (result.error) {
                this.hideImportantOverlay();
                alert('Error: ' + result.error);
            }
        } catch (error) {
            this.hideImportantOverlay();
            alert('Error: ' + error.message);
        }
    },

    async pollImportantStatus() {
        try {
            const response = await fetch('/api/important-status');
            const status = await response.json();

            this.updateImportantOverlay(status);

            if (status.done) {
                this.hideImportantOverlay();
                if (status.error) {
                    alert('Error: ' + status.error);
                } else {
                    alert(`Marked ${status.affected_count} emails as important`);
                }
            } else {
                setTimeout(() => this.pollImportantStatus(), 300);
            }
        } catch (error) {
            setTimeout(() => this.pollImportantStatus(), 500);
        }
    },

    showImportantOverlay(senderCount) {
        this.hideLabelOverlay();
        this.hideArchiveOverlay();
        this.hideImportantOverlay();

        const overlay = document.createElement('div');
        overlay.id = 'importantOverlay';
        overlay.className = 'label-overlay';
        overlay.innerHTML = `
            <div class="label-overlay-content">
                <svg class="label-overlay-spinner spinner" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="#eab308" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
                </svg>
                <h3>Marking as Important...</h3>
                <div class="label-progress-container">
                    <div class="label-progress-bar" id="importantProgressBar" style="background: #eab308;"></div>
                </div>
                <p id="importantProgressText">Starting...</p>
                <p class="label-stats">0/${senderCount} senders processed</p>
            </div>
        `;
        document.body.appendChild(overlay);
    },

    updateImportantOverlay(status) {
        const progressBar = document.getElementById('importantProgressBar');
        const progressText = document.getElementById('importantProgressText');

        if (progressBar) {
            progressBar.style.width = status.progress + '%';
        }
        if (progressText) {
            progressText.textContent = status.message;
        }
    },

    hideImportantOverlay() {
        const overlay = document.getElementById('importantOverlay');
        if (overlay) {
            overlay.remove();
        }
    }
};

// Initialize labels when auth is confirmed
document.addEventListener('DOMContentLoaded', async () => {
    // Load labels after a short delay to ensure auth check completes
    setTimeout(async () => {
        const authResponse = await fetch('/api/auth-status');
        const authStatus = await authResponse.json();
        if (authStatus.logged_in) {
            await GmailCleaner.Labels.loadLabels();
        }
    }, 500);
});
