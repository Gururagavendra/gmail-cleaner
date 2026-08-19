/**
 * Gmail Unsubscribe - Main Entry Point
 * Initializes the application and loads all modules
 */

// Global state
window.GmailCleaner = window.GmailCleaner || {};
Object.assign(window.GmailCleaner, {
    results: [],
    deleteResults: [],
    scanning: false,
    deleteScanning: false,
    currentView: 'login'
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    GmailCleaner.Auth.checkStatus();
    GmailCleaner.Auth.checkWebAuthMode();
    GmailCleaner.UI.setupNavigation();
    GmailCleaner.Filters.setup();
});
