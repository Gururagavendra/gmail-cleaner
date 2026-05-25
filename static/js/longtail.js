/**
 * Gmail Cleaner - Long Tail AI Classification Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.LongTail = {
    providers: [],

    async init() {
        await this.loadConfig();
    },

    async loadConfig() {
        try {
            const response = await fetch('/api/ai-config');
            const config = await response.json();
            this.providers = config.providers || [];
            this.populateProviders(config);
            this.renderConfigState(config);
        } catch (error) {
            GmailCleaner.UI.showErrorToast('Could not load AI settings');
        }
    },

    populateProviders(config) {
        const providerSelect = document.getElementById('aiProvider');
        if (!providerSelect) return;

        providerSelect.innerHTML = this.providers.map(provider => `
            <option value="${GmailCleaner.UI.escapeHtml(provider.id)}">
                ${GmailCleaner.UI.escapeHtml(provider.name)}
            </option>
        `).join('');

        providerSelect.value = config.default_provider || 'openai';
        this.applyProviderDefaults(false);
    },

    applyProviderDefaults(force = true) {
        const providerId = document.getElementById('aiProvider').value;
        const provider = this.providers.find(item => item.id === providerId);
        if (!provider) return;

        const baseUrlInput = document.getElementById('aiBaseUrl');
        const modelInput = document.getElementById('aiModel');

        if (force || !baseUrlInput.value) baseUrlInput.value = provider.base_url;
        if (force || !modelInput.value) modelInput.value = provider.model;
    },

    renderConfigState(config) {
        const status = document.getElementById('aiConfigStatus');
        const classifyBtn = document.getElementById('longTailClassifyBtn');
        if (!status) return;

        if (config.configured) {
            status.textContent = `${config.provider_name} configured with ${config.model}`;
            status.classList.remove('status-warning');
            status.classList.add('status-ok');
            if (classifyBtn) classifyBtn.disabled = false;
            document.getElementById('aiProvider').value = config.provider;
            document.getElementById('aiModel').value = config.model;
            document.getElementById('aiBaseUrl').value = config.base_url;
        } else {
            status.textContent = 'Add an AI provider and token to classify long-tail candidates';
            status.classList.remove('status-ok');
            status.classList.add('status-warning');
            if (classifyBtn) classifyBtn.disabled = true;
        }
    },

    async saveConfig() {
        const provider = document.getElementById('aiProvider').value;
        const apiKey = document.getElementById('aiApiKey').value.trim();
        const model = document.getElementById('aiModel').value.trim();
        const baseUrl = document.getElementById('aiBaseUrl').value.trim();

        if (!apiKey) {
            GmailCleaner.UI.showErrorToast('API token is required');
            return;
        }

        try {
            const response = await fetch('/api/ai-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider, api_key: apiKey, model, base_url: baseUrl })
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.detail || 'Could not save AI settings');
            }

            document.getElementById('aiApiKey').value = '';
            this.renderConfigState(result);
            GmailCleaner.UI.showSuccessToast('AI settings saved locally');
        } catch (error) {
            GmailCleaner.UI.showErrorToast(error.message);
        }
    },

    async classifyOne() {
        if (GmailCleaner.longTailScanning) return;

        const authResponse = await fetch('/api/auth-status');
        const authStatus = await authResponse.json();
        if (!authStatus.logged_in) {
            GmailCleaner.Auth.signIn();
            return;
        }

        GmailCleaner.longTailScanning = true;
        this.setClassifyButton(true);
        document.getElementById('longTailNoResult').classList.add('hidden');
        document.getElementById('longTailResultSection').classList.add('hidden');
        document.getElementById('longTailProgressCard').classList.remove('hidden');
        document.getElementById('longTailProgressText').textContent = 'Fetching inbox candidate...';

        try {
            const sender = document.getElementById('longTailSender').value.trim();
            const response = await fetch('/api/longtail/classify-one', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filters: GmailCleaner.Filters.get(),
                    sender: sender || null
                })
            });
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || 'Classification failed');
            }

            if (result.needs_ai_config) {
                GmailCleaner.UI.showErrorToast(result.message);
                await this.loadConfig();
                return;
            }

            GmailCleaner.longTailResult = result;
            this.displayResult(result);
        } catch (error) {
            GmailCleaner.UI.showErrorToast(error.message);
        } finally {
            GmailCleaner.longTailScanning = false;
            this.setClassifyButton(false);
            await this.loadConfig();
            document.getElementById('longTailProgressCard').classList.add('hidden');
        }
    },

    setClassifyButton(isLoading) {
        const btn = document.getElementById('longTailClassifyBtn');
        if (!btn) return;
        btn.disabled = isLoading;
        btn.innerHTML = isLoading ? `
            <svg class="spinner" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
            </svg>
            Classifying...
        ` : `
            <svg viewBox="0 0 24 24" width="18" height="18">
                <path fill="currentColor" d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z"/>
            </svg>
            Classify Candidate
        `;
    },

    async scanBulk() {
        if (GmailCleaner.longTailBulkScanning) return;

        const authResponse = await fetch('/api/auth-status');
        const authStatus = await authResponse.json();
        if (!authStatus.logged_in) {
            GmailCleaner.Auth.signIn();
            return;
        }

        GmailCleaner.longTailBulkScanning = true;
        this.setBulkScanButton(true);
        document.getElementById('longTailBulkSummarySection').classList.add('hidden');
        document.getElementById('longTailClassifyResultsSection').classList.add('hidden');
        document.getElementById('longTailBulkProgressCard').classList.remove('hidden');

        const limit = parseInt(document.getElementById('longTailScanLimit').value, 10);
        const senderThreshold = parseInt(document.getElementById('longTailSenderThreshold').value, 10) || 2;

        try {
            const response = await fetch('/api/longtail/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    limit,
                    sender_threshold: senderThreshold,
                    filters: GmailCleaner.Filters.get()
                })
            });
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || 'Long-tail scan failed');
            }

            this.pollBulkScan();
        } catch (error) {
            GmailCleaner.UI.showErrorToast(error.message);
            this.resetBulkScan();
        }
    },

    async pollBulkScan() {
        try {
            const response = await fetch('/api/longtail/scan-status');
            const status = await response.json();

            document.getElementById('longTailBulkProgressBar').style.width = `${status.progress || 0}%`;
            document.getElementById('longTailBulkProgressText').textContent = status.message || 'Scanning...';

            if (status.done) {
                if (status.error) {
                    GmailCleaner.UI.showErrorToast(status.error);
                } else {
                    const resultsResponse = await fetch('/api/longtail/scan-results');
                    GmailCleaner.longTailScanResults = await resultsResponse.json();
                    this.displayBulkScanResults();
                }
                this.resetBulkScan();
            } else {
                setTimeout(() => this.pollBulkScan(), 400);
            }
        } catch (error) {
            setTimeout(() => this.pollBulkScan(), 600);
        }
    },

    resetBulkScan() {
        GmailCleaner.longTailBulkScanning = false;
        this.setBulkScanButton(false);
        document.getElementById('longTailBulkProgressCard').classList.add('hidden');
    },

    setBulkScanButton(isLoading) {
        const btn = document.getElementById('longTailBulkScanBtn');
        if (!btn) return;
        btn.disabled = isLoading;
        btn.innerHTML = isLoading ? `
            <svg class="spinner" viewBox="0 0 24 24" width="18" height="18">
                <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="60" stroke-linecap="round"/>
            </svg>
            Scanning...
        ` : `
            <svg viewBox="0 0 24 24" width="18" height="18">
                <path fill="currentColor" d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
            </svg>
            Scan Long-tail
        `;
    },

    displayBulkScanResults() {
        const results = GmailCleaner.longTailScanResults || {};
        const summary = results.summary || {};
        const senders = results.senders || [];
        const emails = results.emails || [];
        const section = document.getElementById('longTailBulkSummarySection');
        const list = document.getElementById('longTailCandidateList');
        const classifyBtn = document.getElementById('longTailClassifyCandidatesBtn');
        const estimate = document.getElementById('longTailTokenEstimate');

        document.getElementById('longTailBulkSummary').textContent =
            `${summary.candidate_emails || 0} emails from ${summary.candidate_senders || 0} senders` +
            ` (threshold ${summary.sender_threshold || 2}, scanned ${summary.scanned_emails || 0})`;

        list.innerHTML = '';
        classifyBtn.disabled = emails.length === 0;

        senders.forEach(sender => {
            const item = document.createElement('div');
            item.className = 'result-item longtail-result-card';
            item.innerHTML = `
                <div class="result-content">
                    <div class="result-sender">${GmailCleaner.UI.escapeHtml(sender.email)}</div>
                    <div class="result-subject">${GmailCleaner.UI.escapeHtml((sender.subjects || [])[0] || 'No subject')}</div>
                    <div class="longtail-snippet">${GmailCleaner.UI.escapeHtml((sender.subjects || []).slice(1).join(' • '))}</div>
                </div>
                <span class="result-count">${sender.count} email${sender.count === 1 ? '' : 's'}</span>
            `;
            list.appendChild(item);
        });

        const estimatedTokens = this.estimateTokens(emails);
        estimate.textContent =
            `AI step is capped by the classify limit. Rough candidate estimate: ` +
            `${estimatedTokens.toLocaleString()} input tokens before cache savings.`;
        section.classList.remove('hidden');
    },

    estimateTokens(emails) {
        return emails.reduce((total, email) => {
            const text = [
                email.from_email,
                email.subject,
                email.snippet,
                (email.labels || []).join(' ')
            ].join(' ');
            return total + Math.ceil(text.length / 4) + 180;
        }, 0);
    },

    async classifyCandidates() {
        if (GmailCleaner.longTailClassifying) return;

        await this.loadConfig();
        GmailCleaner.longTailClassifying = true;
        this.setClassifyCandidatesButton(true);
        document.getElementById('longTailCancelClassifyBtn').disabled = false;
        document.getElementById('longTailClassifyProgressCard').classList.remove('hidden');
        document.getElementById('longTailClassifyResultsSection').classList.add('hidden');
        const maxEmails = parseInt(document.getElementById('longTailClassifyLimit').value, 10) || 25;

        try {
            const response = await fetch('/api/longtail/classify-candidates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_emails: maxEmails,
                    use_cache: true
                })
            });
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || 'Classification failed');
            }

            this.pollClassifyCandidates();
        } catch (error) {
            GmailCleaner.UI.showErrorToast(error.message);
            this.resetClassifyCandidates();
        }
    },

    async pollClassifyCandidates() {
        try {
            const response = await fetch('/api/longtail/classify-status');
            const status = await response.json();

            document.getElementById('longTailClassifyProgressBar').style.width = `${status.progress || 0}%`;
            document.getElementById('longTailClassifyProgressText').textContent = status.message || 'Classifying...';

            const resultsResponse = await fetch('/api/longtail/classify-results');
            GmailCleaner.longTailClassifyResults = await resultsResponse.json();
            this.displayClassifyResults();

            if (status.done) {
                if (status.error) {
                    GmailCleaner.UI.showErrorToast(status.error);
                }
                this.resetClassifyCandidates();
            } else {
                setTimeout(() => this.pollClassifyCandidates(), 700);
            }
        } catch (error) {
            setTimeout(() => this.pollClassifyCandidates(), 900);
        }
    },

    resetClassifyCandidates() {
        GmailCleaner.longTailClassifying = false;
        this.setClassifyCandidatesButton(false);
        document.getElementById('longTailCancelClassifyBtn').disabled = true;
        document.getElementById('longTailClassifyProgressCard').classList.add('hidden');
    },

    setClassifyCandidatesButton(isLoading) {
        const btn = document.getElementById('longTailClassifyCandidatesBtn');
        if (!btn) return;
        btn.disabled = isLoading || !(GmailCleaner.longTailScanResults || {}).emails?.length;
        btn.textContent = isLoading ? 'Classifying...' : 'Classify Candidates';
    },

    displayClassifyResults() {
        const results = GmailCleaner.longTailClassifyResults || [];
        const section = document.getElementById('longTailClassifyResultsSection');
        const list = document.getElementById('longTailClassifyResultsList');
        const badge = document.getElementById('longTailClassifyBadge');
        const selectBtn = document.getElementById('longTailSelectRecommendedBtn');
        const applyBtn = document.getElementById('longTailApplyActionsBtn');

        badge.textContent = results.length;
        list.innerHTML = '';
        selectBtn.disabled = results.length === 0;
        applyBtn.disabled = results.length === 0;

        results.forEach((result, index) => {
            const email = result.email || {};
            const classification = result.classification || {};
            const error = result.error;
            const recommendedAction = classification.recommended_action || 'manual_review';
            const isActionable = ['delete', 'archive'].includes(recommendedAction);
            const confidence = typeof classification.confidence === 'number'
                ? `${Math.round(classification.confidence * 100)}%`
                : '—';
            const item = document.createElement('div');
            item.className = 'result-item longtail-result-card';
            if (error) {
                item.innerHTML = `
                    <div class="result-content">
                        <div class="result-sender">${GmailCleaner.UI.escapeHtml(email.from_email)}</div>
                        <div class="result-subject">${GmailCleaner.UI.escapeHtml(email.subject)}</div>
                        <div class="longtail-snippet">${GmailCleaner.UI.escapeHtml(error)}</div>
                    </div>
                    <span class="classification-badge error">error</span>
                `;
                list.appendChild(item);
                return;
            }
            item.innerHTML = `
                <label class="checkbox-wrapper result-checkbox">
                    <input type="checkbox"
                        class="longtail-action-cb"
                        data-index="${index}"
                        data-message-id="${GmailCleaner.UI.escapeHtml(email.id || '')}"
                        data-action="${GmailCleaner.UI.escapeHtml(recommendedAction)}"
                        ${isActionable ? 'checked' : ''}
                        ${isActionable ? '' : 'disabled'}>
                    <span class="checkmark"></span>
                </label>
                <div class="result-content">
                    <div class="result-sender">${GmailCleaner.UI.escapeHtml(email.from_email)}</div>
                    <div class="result-subject">${GmailCleaner.UI.escapeHtml(email.subject)}</div>
                    <div class="longtail-snippet">${GmailCleaner.UI.escapeHtml(classification.reason || email.snippet || '')}</div>
                </div>
                ${result.cached ? '<span class="classification-badge">cached</span>' : ''}
                <span class="classification-badge">${GmailCleaner.UI.escapeHtml(classification.category || 'unknown')}</span>
                <span class="classification-badge">${GmailCleaner.UI.escapeHtml(classification.recommended_action || 'manual_review')}</span>
                <span class="result-count">${confidence}</span>
            `;
            list.appendChild(item);
        });

        section.classList.toggle('hidden', results.length === 0);
    },

    selectRecommendedActions() {
        document.querySelectorAll('.longtail-action-cb').forEach(cb => {
            cb.checked = !cb.disabled;
        });
    },

    async applyActions() {
        if (GmailCleaner.longTailApplying) return;

        const actions = [];
        document.querySelectorAll('.longtail-action-cb:checked').forEach(cb => {
            const action = cb.dataset.action;
            if (['delete', 'archive'].includes(action) && cb.dataset.messageId) {
                actions.push({
                    message_id: cb.dataset.messageId,
                    action
                });
            }
        });

        if (actions.length === 0) {
            GmailCleaner.UI.showErrorToast('Select at least one delete or archive action');
            return;
        }

        const deleteCount = actions.filter(action => action.action === 'delete').length;
        const archiveCount = actions.filter(action => action.action === 'archive').length;
        const message = `Apply ${actions.length} actions?\n\nMove to trash: ${deleteCount}\nArchive: ${archiveCount}`;
        if (!confirm(message)) return;

        GmailCleaner.longTailApplying = true;
        document.getElementById('longTailApplyActionsBtn').disabled = true;
        document.getElementById('longTailApplyProgressCard').classList.remove('hidden');

        try {
            const response = await fetch('/api/longtail/apply-actions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ actions })
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.detail || 'Could not apply actions');
            }
            this.pollApplyActions();
        } catch (error) {
            GmailCleaner.UI.showErrorToast(error.message);
            this.resetApplyActions();
        }
    },

    async pollApplyActions() {
        try {
            const response = await fetch('/api/longtail/apply-status');
            const status = await response.json();
            document.getElementById('longTailApplyProgressBar').style.width = `${status.progress || 0}%`;
            document.getElementById('longTailApplyProgressText').textContent = status.message || 'Applying actions...';

            if (status.done) {
                if (status.error) {
                    GmailCleaner.UI.showErrorToast(status.error);
                } else {
                    GmailCleaner.UI.showSuccessToast(status.message || 'Actions applied');
                    this.markAppliedRows();
                }
                this.resetApplyActions();
            } else {
                setTimeout(() => this.pollApplyActions(), 500);
            }
        } catch (error) {
            setTimeout(() => this.pollApplyActions(), 700);
        }
    },

    resetApplyActions() {
        GmailCleaner.longTailApplying = false;
        document.getElementById('longTailApplyActionsBtn').disabled = false;
        document.getElementById('longTailApplyProgressCard').classList.add('hidden');
    },

    markAppliedRows() {
        document.querySelectorAll('.longtail-action-cb:checked').forEach(cb => {
            cb.disabled = true;
            cb.checked = false;
            const row = cb.closest('.result-item');
            if (row) {
                const badge = document.createElement('span');
                badge.className = 'classification-badge';
                badge.textContent = 'applied';
                row.appendChild(badge);
            }
        });
    },

    async cancelClassification() {
        try {
            await fetch('/api/longtail/cancel-classification', { method: 'POST' });
            GmailCleaner.UI.showInfoToast('Cancellation requested');
        } catch (error) {
            GmailCleaner.UI.showErrorToast(error.message);
        }
    },

    displayResult(result) {
        if (!result.email) {
            document.getElementById('longTailNoResult').classList.remove('hidden');
            return;
        }

        const section = document.getElementById('longTailResultSection');
        const email = result.email;
        const classification = result.classification;
        const usage = classification.token_usage || {};
        const formatTokens = (value) => value === null || value === undefined ? '—' : value.toLocaleString();
        const confidence = typeof classification.confidence === 'number'
            ? `${Math.round(classification.confidence * 100)}%`
            : '—';
        const rawUsage = usage.raw && Object.keys(usage.raw).length
            ? JSON.stringify(usage.raw, null, 2)
            : 'No token usage returned by provider';
        const rawOutput = classification.raw_model_output || 'No raw model output captured';

        document.getElementById('longTailEmailMeta').innerHTML = `
            <div class="result-sender">${GmailCleaner.UI.escapeHtml(email.from_email)}</div>
            <div class="result-subject">${GmailCleaner.UI.escapeHtml(email.subject)}</div>
            <div class="longtail-snippet">${GmailCleaner.UI.escapeHtml(email.snippet)}</div>
            <div class="longtail-query">Search: ${GmailCleaner.UI.escapeHtml(email.search_query || 'in:inbox')}</div>
        `;

        document.getElementById('longTailClassification').innerHTML = `
            <div class="classification-grid">
                <div><span>Category</span><strong>${GmailCleaner.UI.escapeHtml(classification.category)}</strong></div>
                <div><span>Action</span><strong>${GmailCleaner.UI.escapeHtml(classification.recommended_action)}</strong></div>
                <div><span>Confidence</span><strong>${confidence}</strong></div>
                <div><span>Input tokens</span><strong>${formatTokens(usage.input_tokens)}</strong></div>
                <div><span>Output tokens</span><strong>${formatTokens(usage.output_tokens)}</strong></div>
                <div><span>Total tokens</span><strong>${formatTokens(usage.total_tokens)}</strong></div>
            </div>
            <p>${GmailCleaner.UI.escapeHtml(classification.reason || 'No reason returned')}</p>
            <details class="longtail-debug">
                <summary>Raw AI response details</summary>
                <div>
                    <strong>Model output</strong>
                    <pre>${GmailCleaner.UI.escapeHtml(rawOutput)}</pre>
                    <strong>Token usage</strong>
                    <pre>${GmailCleaner.UI.escapeHtml(rawUsage)}</pre>
                </div>
            </details>
        `;

        section.classList.remove('hidden');
    }
};

function saveAIConfig() { GmailCleaner.LongTail.saveConfig(); }
function classifyOneLongTailEmail() { GmailCleaner.LongTail.classifyOne(); }
function scanLongTailBulk() { GmailCleaner.LongTail.scanBulk(); }
function classifyLongTailCandidates() { GmailCleaner.LongTail.classifyCandidates(); }
function cancelLongTailClassification() { GmailCleaner.LongTail.cancelClassification(); }
function selectRecommendedLongTailActions() { GmailCleaner.LongTail.selectRecommendedActions(); }
function applyLongTailActions() { GmailCleaner.LongTail.applyActions(); }
