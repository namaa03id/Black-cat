// Omni-Engine - Advanced Web Scraper JavaScript

class OmniEngine {
    constructor() {
        this.currentResults = [];
        this.currentQuery = '';
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadStats();
        this.loadRecentSearches();
    }

    bindEvents() {
        // Search form
        const searchForm = document.getElementById('searchForm');
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.performSearch();
        });

        // Search input (Enter key)
        const searchInput = document.getElementById('searchInput');
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.performSearch();
            }
        });

        // Export buttons
        document.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.exportResults(btn.dataset.format);
            });
        });

        // Clear cache button
        document.getElementById('clearCacheBtn').addEventListener('click', () => {
            this.clearCache();
        });

        // Modal close buttons
        document.getElementById('closeError').addEventListener('click', () => {
            this.hideModal('errorModal');
        });

        document.getElementById('closeSuccess').addEventListener('click', () => {
            this.hideModal('successModal');
        });

        // Click outside modal to close
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideModal(modal.id);
                }
            });
        });

        // Recent search items (delegated event)
        document.getElementById('recentSearches').addEventListener('click', (e) => {
            const recentItem = e.target.closest('.recent-item');
            if (recentItem) {
                const query = recentItem.querySelector('.recent-query').textContent;
                document.getElementById('searchInput').value = query;
                this.performSearch();
            }
        });

        // Auto-refresh stats every 30 seconds
        setInterval(() => {
            this.loadStats();
        }, 30000);
    }

    async performSearch() {
        const searchInput = document.getElementById('searchInput');
        const searchBtn = document.getElementById('searchBtn');
        const loading = document.getElementById('loading');
        const resultsSection = document.getElementById('resultsSection');

        const query = searchInput.value.trim();
        if (!query) {
            this.showError('Please enter a search query');
            return;
        }

        // Update UI state
        this.currentQuery = query;
        searchBtn.disabled = true;
        searchBtn.innerHTML = `
            <div class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
            <span>Searching...</span>
        `;
        loading.classList.add('show');
        resultsSection.classList.remove('show');

        try {
            const maxResults = parseInt(document.getElementById('maxResults').value);
            const useCache = document.getElementById('useCache').checked;

            const response = await fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    max_results: maxResults,
                    use_cache: useCache
                })
            });

            const data = await response.json();

            if (data.success) {
                this.currentResults = data.results;
                this.displayResults(data);
                this.loadRecentSearches(); // Refresh recent searches
                this.loadStats(); // Refresh stats
            } else {
                this.showError(data.error || 'Search failed');
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showError('Network error occurred. Please try again.');
        } finally {
            // Reset UI state
            searchBtn.disabled = false;
            searchBtn.innerHTML = `
                <span class="search-icon">🔎</span>
                <span class="search-text">Search</span>
            `;
            loading.classList.remove('show');
        }
    }

    displayResults(data) {
        const resultsSection = document.getElementById('resultsSection');
        const resultsTitle = document.getElementById('resultsTitle');
        const resultsCount = document.getElementById('resultsCount');
        const resultsContainer = document.getElementById('resultsContainer');

        // Update header
        resultsTitle.textContent = `Results for "${data.query}"`;
        resultsCount.textContent = `${data.results_count} results found`;

        // Clear previous results
        resultsContainer.innerHTML = '';

        if (data.results.length === 0) {
            resultsContainer.innerHTML = `
                <div style="text-align: center; padding: 60px 20px; color: var(--text-muted);">
                    <div style="font-size: 3rem; margin-bottom: 20px;">🔍</div>
                    <h3 style="margin-bottom: 10px;">No Results Found</h3>
                    <p>Try different keywords or check your spelling.</p>
                </div>
            `;
        } else {
            // Display results
            data.results.forEach((result, index) => {
                const resultElement = this.createResultElement(result, index + 1);
                resultsContainer.appendChild(resultElement);
            });
        }

        // Show results section
        resultsSection.classList.add('show');
        
        // Smooth scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    createResultElement(result, index) {
        const div = document.createElement('div');
        div.className = 'result-item';
        div.style.animationDelay = `${index * 0.1}s`;
        
        // Format timestamp
        const timestamp = new Date(result.timestamp).toLocaleString();
        
        // Truncate content for display
        const maxSnippetLength = 200;
        const maxContentLength = 300;
        
        const snippet = result.snippet.length > maxSnippetLength 
            ? result.snippet.substring(0, maxSnippetLength) + '...' 
            : result.snippet;
            
        const content = result.content.length > maxContentLength 
            ? result.content.substring(0, maxContentLength) + '...' 
            : result.content;

        div.innerHTML = `
            <div class="result-header">
                <a href="${this.sanitizeUrl(result.url)}" target="_blank" rel="noopener noreferrer" class="result-title">
                    ${this.escapeHtml(result.title)}
                </a>
                <div class="result-meta">
                    <div class="result-source">${this.escapeHtml(result.source)}</div>
                    <div class="result-score">Score: ${result.relevance_score.toFixed(3)}</div>
                </div>
            </div>
            <div class="result-url">${this.escapeHtml(result.url)}</div>
            <div class="result-snippet">${this.escapeHtml(snippet)}</div>
            ${content ? `<div class="result-content">${this.escapeHtml(content)}</div>` : ''}
        `;

        return div;
    }

    async exportResults(format) {
        if (this.currentResults.length === 0) {
            this.showError('No results to export');
            return;
        }

        try {
            const response = await fetch('/export', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: this.currentQuery,
                    format: format,
                    results: this.currentResults
                })
            });

            const data = await response.json();

            if (data.success) {
                // Show success modal with download link
                const downloadLink = document.getElementById('downloadLink');
                downloadLink.href = `/download/${data.filename}`;
                downloadLink.style.display = 'block';
                downloadLink.textContent = `Download ${format.toUpperCase()} File`;
                
                this.showSuccess(`Export successful! Your ${format.toUpperCase()} file is ready for download.`);
            } else {
                this.showError(data.error || 'Export failed');
            }
        } catch (error) {
            console.error('Export error:', error);
            this.showError('Export failed. Please try again.');
        }
    }

    async clearCache() {
        if (!confirm('Are you sure you want to clear the cache? This will remove all stored search results.')) {
            return;
        }

        try {
            const response = await fetch('/clear-cache', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess('Cache cleared successfully!');
                this.loadStats(); // Refresh stats
                this.loadRecentSearches(); // Refresh recent searches
            } else {
                this.showError(data.error || 'Failed to clear cache');
            }
        } catch (error) {
            console.error('Clear cache error:', error);
            this.showError('Failed to clear cache. Please try again.');
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/stats');
            const data = await response.json();

            if (data.success) {
                document.getElementById('cached-count').textContent = 
                    data.total_cached_results.toLocaleString();
                document.getElementById('queries-today').textContent = 
                    data.unique_queries_today.toLocaleString();
                document.getElementById('engines-count').textContent = 
                    data.supported_engines.length;
            }
        } catch (error) {
            console.error('Stats loading error:', error);
            // Silently fail for stats
        }
    }

    async loadRecentSearches() {
        try {
            const response = await fetch('/recent');
            const data = await response.json();

            if (data.success) {
                this.displayRecentSearches(data.recent_searches);
            }
        } catch (error) {
            console.error('Recent searches loading error:', error);
        }
    }

    displayRecentSearches(searches) {
        const container = document.getElementById('recentSearches');
        
        if (searches.length === 0) {
            container.innerHTML = '<p class="no-recent">No recent searches</p>';
            return;
        }

        container.innerHTML = searches.map(search => {
            const timestamp = new Date(search.timestamp);
            const timeAgo = this.getTimeAgo(timestamp);
            
            return `
                <div class="recent-item">
                    <div class="recent-query">${this.escapeHtml(search.query)}</div>
                    <div class="recent-meta">
                        <span>${search.results_count} results</span>
                        <span>${timeAgo}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    getTimeAgo(date) {
        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 1) return 'Just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        return date.toLocaleDateString();
    }

    showError(message) {
        document.getElementById('errorMessage').textContent = message;
        this.showModal('errorModal');
    }

    showSuccess(message) {
        document.getElementById('successMessage').textContent = message;
        this.showModal('successModal');
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.add('show');
        
        // Focus trap
        const focusableElements = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        }
    }

    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');
        
        // Reset download link
        if (modalId === 'successModal') {
            document.getElementById('downloadLink').style.display = 'none';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    sanitizeUrl(url) {
        try {
            const parsedUrl = new URL(url);
            return parsedUrl.href;
        } catch {
            return '#';
        }
    }
}

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.omniEngine = new OmniEngine();
    
    // Add some nice loading animations
    const style = document.createElement('style');
    style.textContent = `
        .result-item {
            opacity: 0;
            transform: translateY(20px);
            animation: slideInUp 0.6s ease forwards;
        }
        
        @keyframes slideInUp {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .search-btn {
            position: relative;
            overflow: hidden;
        }
        
        .search-btn::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.1);
            transform: translate(-50%, -50%);
            transition: width 0.4s, height 0.4s;
        }
        
        .search-btn:active::after {
            width: 300px;
            height: 300px;
        }
    `;
    document.head.appendChild(style);
    
    console.log(`
    ╔═══════════════════════════════════════════╗
    ║         OMNI-ENGINE INITIALIZED           ║
    ║      Advanced Web Scraping Ready          ║
    ╚═══════════════════════════════════════════╝
    `);
});

// Global error handler
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    if (window.omniEngine) {
        window.omniEngine.showError('An unexpected error occurred. Please refresh the page.');
    }
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    if (window.omniEngine) {
        window.omniEngine.showError('A network error occurred. Please check your connection.');
    }
});