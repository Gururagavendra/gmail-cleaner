/**
 * Gmail Cleaner - Jobs Module
 * Long-running bulk email operations with cancellation support.
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Jobs = {
    pollInterval: null,

    onActionChange() {
        const action = document.getElementById('jobAction').value;
        document.getElementById('jobLabelGroup').classList.toggle('hidden', action !== 'label');
        document.getElementById('jobImportantGroup').classList.toggle('hidden', action !== 'mark_important');
    },

    async loadLabels() {
        try {
            const res = await fetch('/api/labels');
            if (!res.ok) return;
            const data = await res.json();

            // API returns { success, user_labels, system_labels }
            const userLabels = data.user_labels || [];

            // Populate the label picker (action=label)
            document.getElementById('jobLabelSelect').innerHTML = userLabels.length
                ? userLabels.map(l => `<option value="${GmailCleaner.UI.escapeHtml(l.id)}">${GmailCleaner.UI.escapeHtml(l.name)}</option>`).join('')
                : '<option value="">No labels found</option>';

            // Append custom labels to the mailbox dropdown (under a separator)
            const customLabels = userLabels;
            const mailboxSel = document.getElementById('jobMailbox');
            // Remove any previously appended custom labels before re-adding
            mailboxSel.querySelectorAll('.custom-label-opt').forEach(el => el.remove());
            if (customLabels.length > 0) {
                const sep = document.createElement('option');
                sep.disabled = true;
                sep.className = 'custom-label-opt';
                sep.textContent = '── Custom Labels ──';
                mailboxSel.appendChild(sep);
                customLabels.forEach(l => {
                    const opt = document.createElement('option');
                    opt.value = l.id;
                    opt.className = 'custom-label-opt';
                    opt.textContent = l.name;
                    mailboxSel.appendChild(opt);
                });
            }
        } catch (_) {
            // ignore — labels will just be empty
        }
    },

    async startJob() {
        const action = document.getElementById('jobAction').value;
        const labelId = action === 'label'
            ? document.getElementById('jobLabelSelect').value
            : null;
        const important = action === 'mark_important'
            ? document.getElementById('jobImportant').value === 'true'
            : true;

        if (action === 'label' && !labelId) {
            alert('Please select a label.');
            return;
        }

        const mailbox = document.getElementById('jobMailbox').value || null;
        const filters = GmailCleaner.Filters.get();
        const hasFilters = Object.values(filters).some(v => v);

        if (action === 'delete' || action === 'archive') {
            const actionLabel = action === 'delete' ? 'DELETE (move to trash)' : 'ARCHIVE (remove from inbox)';
            const scope = mailbox
                ? `mailbox: ${document.getElementById('jobMailbox').selectedOptions[0].textContent}`
                : 'All Mail';
            const filterSummary = hasFilters
                ? Object.entries(filters).filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`).join(', ')
                : 'none';
            const confirmed = window.confirm(
                `⚠️ Warning: This will ${actionLabel} ALL matching emails.\n\n` +
                `Scope: ${scope}\n` +
                `Filters: ${filterSummary}\n\n` +
                `This cannot be undone automatically. Are you sure you want to proceed?`
            );
            if (!confirmed) return;
        }

        const body = {
            action,
            label_id: labelId || null,
            important,
            mailbox,
            filters: hasFilters ? filters : null,
        };

        const startBtn = document.getElementById('jobStartBtn');
        startBtn.disabled = true;

        try {
            const res = await fetch('/api/job/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                alert(err.detail || 'Failed to start job.');
                startBtn.disabled = false;
                return;
            }

            this.showProgressCard(action);
            this.startPolling();
        } catch (e) {
            alert('Network error starting job.');
            startBtn.disabled = false;
        }
    },

    async cancelJob() {
        const cancelBtn = document.getElementById('jobCancelBtn');
        cancelBtn.disabled = true;
        cancelBtn.textContent = 'Cancelling...';

        try {
            await fetch('/api/job/cancel', { method: 'POST' });
        } catch (_) {
            // ignore — polling will pick up the cancelled state
        }
    },

    showProgressCard(action) {
        document.getElementById('jobFormCard').classList.add('hidden');
        document.getElementById('jobProgressCard').classList.remove('hidden');

        const titles = {
            search: 'Searching Emails',
            find_subscriptions: 'Scanning for Subscriptions',
            delete: 'Deleting Emails',
            archive: 'Archiving Emails',
            label: 'Applying Label',
            mark_important: 'Marking as Important',
        };
        document.getElementById('jobProgressTitle').textContent = titles[action] || 'Job Running';
        document.getElementById('jobProgressText').textContent = 'Starting...';
        document.getElementById('jobProgressBar').style.width = '0%';
        document.getElementById('jobBatchCount').textContent = '0';
        document.getElementById('jobEmailCount').textContent = '0';

        // Update counter label based on action
        const emailCountLabel = document.querySelector('#jobEmailCount + div');
        if (emailCountLabel) {
            const labels = { search: 'Emails found', find_subscriptions: 'Senders found' };
            emailCountLabel.textContent = labels[action] || 'Emails affected';
        }

        const cancelBtn = document.getElementById('jobCancelBtn');
        cancelBtn.disabled = false;
        cancelBtn.textContent = 'Cancel';
    },

    startPolling() {
        this.stopPolling();
        this.pollInterval = setInterval(() => this.pollStatus(), 500);
    },

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },

    async pollStatus() {
        try {
            const res = await fetch('/api/job/status');
            if (!res.ok) return;
            const s = await res.json();
            this.updateUI(s);
            if (s.done) this.stopPolling();
        } catch (_) {
            // ignore transient network errors
        }
    },

    updateUI(s) {
        const progressBar = document.getElementById('jobProgressBar');
        const progressText = document.getElementById('jobProgressText');
        const batchCount = document.getElementById('jobBatchCount');
        const emailCount = document.getElementById('jobEmailCount');
        const cancelBtn = document.getElementById('jobCancelBtn');

        progressBar.style.width = (s.progress || 0) + '%';
        progressText.textContent = s.error
            ? 'Error: ' + s.error
            : (s.message || 'Running...');
        batchCount.textContent = (s.batches_processed || 0).toLocaleString();
        emailCount.textContent = (s.emails_affected || 0).toLocaleString();

        if (s.done) {
            cancelBtn.disabled = false;
            cancelBtn.className = 'btn btn-secondary';
            cancelBtn.textContent = 'Start New Job';
            cancelBtn.onclick = () => this.resetToForm();

            if (s.action === 'find_subscriptions' && !s.cancelled && !s.error) {
                const card = document.getElementById('jobProgressCard');
                if (!card.querySelector('.job-view-results-btn')) {
                    const btn = document.createElement('button');
                    btn.className = 'btn btn-primary job-view-results-btn';
                    btn.style.marginTop = '1rem';
                    btn.style.marginLeft = '0.5rem';
                    btn.textContent = 'View Results';
                    btn.onclick = async () => {
                        try {
                            const res = await fetch('/api/results');
                            if (res.ok) {
                                GmailCleaner.results = await res.json();
                            }
                        } catch (_) {}
                        this.resetToForm();
                        GmailCleaner.Scanner.displayResults(GmailCleaner.results);
                        GmailCleaner.UI.showView('unsubscribe');
                    };
                    cancelBtn.insertAdjacentElement('afterend', btn);
                }
            }
        }
    },

    resetToForm() {
        this.stopPolling();
        document.getElementById('jobProgressCard').classList.add('hidden');
        document.getElementById('jobFormCard').classList.remove('hidden');
        document.getElementById('jobStartBtn').disabled = false;

        const cancelBtn = document.getElementById('jobCancelBtn');
        cancelBtn.className = 'btn btn-danger';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.onclick = () => this.cancelJob();

        document.querySelector('.job-view-results-btn')?.remove();
    },
};

// Load labels when the job view is shown
const _origShowView = GmailCleaner.UI && GmailCleaner.UI.showView
    ? GmailCleaner.UI.showView.bind(GmailCleaner.UI)
    : null;

document.addEventListener('DOMContentLoaded', () => {
    // Direct click listener on job nav item (most reliable trigger)
    const jobNavItem = document.querySelector('[data-view="job"]');
    if (jobNavItem) {
        jobNavItem.addEventListener('click', () => GmailCleaner.Jobs.loadLabels());
    }

    // Also patch showView for programmatic navigation
    if (GmailCleaner.UI) {
        const original = GmailCleaner.UI.showView.bind(GmailCleaner.UI);
        GmailCleaner.UI.showView = function(viewName) {
            original(viewName);
            if (viewName === 'job') {
                GmailCleaner.Jobs.loadLabels();
            }
        };
    }
});
