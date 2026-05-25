/**
 * Gmail Unsubscribe - Main Entry Point
 * Initializes the application and loads all modules
 */

// Global state
window.GmailCleaner = {
    results: [],
    deleteResults: [],
    longTailResult: null,
    longTailScanResults: null,
    longTailClassifyResults: [],
    scanning: false,
    deleteScanning: false,
    longTailScanning: false,
    longTailBulkScanning: false,
    longTailClassifying: false,
    longTailApplying: false,
    currentView: 'login'
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    GmailCleaner.Auth.checkStatus();
    GmailCleaner.Auth.checkWebAuthMode();
    GmailCleaner.UI.setupNavigation();
    GmailCleaner.Filters.setup();
    GmailCleaner.LongTail.init();
});
