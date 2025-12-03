/**
 * Gmail Unsubscribe - Filters Module
 */

window.GmailCleaner = window.GmailCleaner || {};

GmailCleaner.Filters = {
    litepicker: null,

    setup() {
        const clearBtn = document.getElementById('filterClearBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clear());
        }

        // Setup date range picker
        this.setupDateRangePicker();

        // Listen for "Older than" dropdown changes
        const olderThanSelect = document.getElementById('filterOlderThan');
        if (olderThanSelect) {
            olderThanSelect.addEventListener('change', (e) => this.handleOlderThanChange(e));
        }
    },

    setupDateRangePicker() {
        const dateRangeInput = document.getElementById('dateRangePicker');
        if (!dateRangeInput || !window.Litepicker) return;

        try {
            // Calculate default dates: today and 7 days ago
            const today = new Date();
            const sevenDaysAgo = new Date(today);
            sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
            
            // Initialize Litepicker with 7-day default window using Date objects
            this.litepicker = new Litepicker({
                element: dateRangeInput,
                singleMode: false,
                format: 'YYYY-MM-DD',
                returnFormat: 'YYYY-MM-DD',
                startDate: sevenDaysAgo,
                endDate: today,
                showTooltip: true,
                tooltipText: ['Start date', 'End date'],
                minDate: new Date(1970, 0, 1),
                maxDate: today,
                autoApply: true,
                inlineMode: false,
                position: 'bottom',
                allowEmptyRange: true,
                disallowEmptyRange: false,
                lang: 'en',
            });

            // Allow manual typing in the date input field
            dateRangeInput.removeAttribute('readonly');
            dateRangeInput.placeholder = 'YYYY-MM-DD - YYYY-MM-DD';
            
            dateRangeInput.addEventListener('click', () => {
                // Ensure widget shows when clicking the input
                if (this.litepicker) {
                    this.litepicker.show();
                }
            });
            
            dateRangeInput.addEventListener('keydown', (e) => {
                // Allow typing and common keys
                if (!['Tab', 'Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Enter'].includes(e.key) && 
                    !e.key.match(/[0-9\-\s]/)) {
                    e.preventDefault();
                }
            });
        } catch (error) {
            console.error('Error initializing Litepicker:', error);
        }
    },

    handleOlderThanChange(event) {
        const value = event.target.value;
        const dateRangeGroup = document.getElementById('dateRangeGroup');
        
        if (value === 'custom') {
            // Show custom date range picker
            dateRangeGroup?.classList.remove('hidden');
            // Reinitialize the picker to ensure it's fresh when shown
            if (!this.litepicker || !this.litepicker.getStartDate()) {
                this.setupDateRangePicker();
            }
        } else {
            // Hide custom date range picker - but DON'T clear the dates
            // so they persist if user switches back
            dateRangeGroup?.classList.add('hidden');
        }
    },

    get() {
        const olderThanSelect = document.getElementById('filterOlderThan');
        const olderThanValue = olderThanSelect?.value || '';
        let olderThan = '';
        let afterDate = '';
        let beforeDate = '';

        // If custom date range is selected, use after/before date format
        if (olderThanValue === 'custom') {
            const dateRangeInput = document.getElementById('dateRangePicker');
            if (dateRangeInput && dateRangeInput.value) {
                // Parse the date range from the input (format: YYYY-MM-DD - YYYY-MM-DD)
                const dateRangeText = dateRangeInput.value;
                const dates = dateRangeText.split(' - ');
                
                if (dates.length === 2) {
                    const startDateStr = dates[0].trim();
                    const endDateStr = dates[1].trim();
                    
                    // Validate date formats
                    if (/^\d{4}-\d{2}-\d{2}$/.test(startDateStr) && /^\d{4}-\d{2}-\d{2}$/.test(endDateStr)) {
                        // Convert YYYY-MM-DD to YYYY/MM/DD format for Gmail API
                        afterDate = startDateStr.replace(/-/g, '/');
                        // Add 1 day to end date for exclusive upper bound (before date)
                        const endDate = new Date(endDateStr + 'T00:00:00');
                        endDate.setDate(endDate.getDate() + 1);
                        beforeDate = endDate.toISOString().split('T')[0].replace(/-/g, '/');
                        
                        console.log('Date range filter:', { startDateStr, endDateStr, afterDate, beforeDate });
                    }
                }
            }
        } else {
            olderThan = olderThanValue !== 'custom' ? olderThanValue : '';
        }

        const largerThan = document.getElementById('filterLargerThan')?.value || '';
        const category = document.getElementById('filterCategory')?.value || '';
        const sender = document.getElementById('filterSender')?.value?.trim() || '';
        
        return {
            older_than: olderThan,
            after_date: afterDate,
            before_date: beforeDate,
            larger_than: largerThan,
            category: category,
            sender: sender
        };
    },

    clear() {
        const olderThan = document.getElementById('filterOlderThan');
        const largerThan = document.getElementById('filterLargerThan');
        const category = document.getElementById('filterCategory');
        const sender = document.getElementById('filterSender');
        const dateRangeGroup = document.getElementById('dateRangeGroup');
        
        if (olderThan) olderThan.value = '';
        if (largerThan) largerThan.value = '';
        if (category) category.value = '';
        if (sender) sender.value = '';
        
        // Clear date picker
        if (this.litepicker) {
            this.litepicker.setDateRange(null, null);
        }
        
        // Hide date range group
        if (dateRangeGroup) {
            dateRangeGroup.classList.add('hidden');
        }
    },

    showBar(show) {
        const filterBar = document.getElementById('filterBar');
        const mainContent = document.querySelector('.main-content');
        
        if (filterBar) {
            if (show) {
                filterBar.classList.remove('hidden');
            } else {
                filterBar.classList.add('hidden');
            }
        }
        if (mainContent) {
            if (show) {
                mainContent.classList.add('with-filters');
            } else {
                mainContent.classList.remove('with-filters');
            }
        }
    }
};

// Global shortcut
function clearFilters() { GmailCleaner.Filters.clear(); }
