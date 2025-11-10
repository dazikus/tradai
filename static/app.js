// Locked in - Frontend Application

const API_BASE_URL = window.location.origin + '/api';
const MIN_REFRESH_INTERVAL = 30000; // 30 seconds
const MAX_REFRESH_INTERVAL = 60000; // 60 seconds

let refreshTimer = null;
let charts = {};
let isInitialLoad = true;
let authToken = null;

// Authentication check
function checkAuth() {
    authToken = localStorage.getItem('auth_token');
    if (!authToken) {
        window.location.href = '/';
        return false;
    }
    return true;
}

// Logout function
function logout() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('username');
    window.location.href = '/';
}

// Fetch with auth header
async function authenticatedFetch(url, options = {}) {
    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${authToken}`
    };
    
    const response = await fetch(url, { ...options, headers });
    
    // Handle 401 unauthorized - token expired
    if (response.status === 401) {
        logout();
        throw new Error('Session expired');
    }
    
    return response;
}

// Event type icons mapping
const EVENT_ICONS = {
    'scoreChange': '⚽',
    'yellowCard': '🟨',
    'redCard': '🟥',
    'substitution': '🔄',
    'shotOnTarget': '🎯',
    'shotOffTarget': '📍',
    'shotBlocked': '🚫',
    'shotSaved': '🧤',
    'cornerKick': '🚩',
    'freeKickWon': '🆓',
    'freeKickLost': '❌',
    'penalty': '⚡',
    'offside': '⚠️',
    'matchStarted': '▶️',
    'endFirstHalf': '⏸️',
    'endDelay': '▶️',
    'startDelay': '⏸️',
    'addedTime': '⏱️'
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    if (!checkAuth()) return;
    
    // Add logout button to header
    addLogoutButton();
    
    loadGames();
    startAutoRefresh();
});

// Add logout button to header
function addLogoutButton() {
    const headerStats = document.querySelector('.header-stats');
    const logoutBtn = document.createElement('button');
    logoutBtn.className = 'refresh-button';
    logoutBtn.title = 'Logout';
    logoutBtn.onclick = logout;
    logoutBtn.innerHTML = '<i data-lucide="log-out" class="refresh-icon"></i>';
    headerStats.appendChild(logoutBtn);
    
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

// Start auto-refresh with random interval
function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    
    const randomInterval = Math.floor(
        Math.random() * (MAX_REFRESH_INTERVAL - MIN_REFRESH_INTERVAL + 1) + MIN_REFRESH_INTERVAL
    );
    
    console.log(`Next auto-refresh in ${randomInterval / 1000} seconds`);
    refreshTimer = setTimeout(() => {
        loadGames();
        startAutoRefresh(); // Schedule next refresh
    }, randomInterval);
}

// Manual refresh triggered by user
function manualRefresh() {
    // Trigger refresh (loadGames handles button/spinner swap)
    loadGames();
    
    // Reset auto-refresh timer (restart the countdown)
    startAutoRefresh();
}

// Load games from API
async function loadGames() {
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const noGames = document.getElementById('noGames');
    const gamesContainer = document.getElementById('gamesContainer');
    const refreshIndicator = document.getElementById('refreshIndicator');
    const refreshButton = document.getElementById('manualRefresh');

    // On initial load, show full loading screen
    // On refresh, hide button and show spinner in same spot
    if (isInitialLoad) {
        loading.style.display = 'flex';
        error.style.display = 'none';
        noGames.style.display = 'none';
        gamesContainer.innerHTML = '';
    } else {
        // Hide button, show spinner (for both manual and auto refresh)
        refreshButton.style.display = 'none';
        refreshIndicator.style.display = 'flex';
    }

    try {
        const response = await authenticatedFetch(`${API_BASE_URL}/live-games`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        
        // Hide loading states, show button again
        loading.style.display = 'none';
        refreshIndicator.style.display = 'none';
        refreshButton.style.display = 'flex';

        // Re-initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

        // Update header stats
        updateHeaderStats(data);

        // Clear container before re-rendering
        gamesContainer.innerHTML = '';
        error.style.display = 'none';
        noGames.style.display = 'none';

        // Render games
        const allGames = [];
        Object.values(data.sports || {}).forEach(sport => {
            allGames.push(...(sport.games || []));
        });

        if (allGames.length === 0) {
            noGames.style.display = 'block';
        } else {
            allGames.forEach(game => renderGame(game));
        }

        // Mark that initial load is complete
        isInitialLoad = false;

    } catch (err) {
        loading.style.display = 'none';
        refreshIndicator.style.display = 'none';
        refreshButton.style.display = 'flex';
        
        // Only show error screen on initial load
        if (isInitialLoad) {
            error.style.display = 'block';
            document.getElementById('errorMessage').textContent = err.message;
        } else {
            // On refresh error, just log it and keep showing old data
            console.error('Refresh failed:', err);
        }
    }
}

// Update header statistics
function updateHeaderStats(data) {
    document.getElementById('totalGames').textContent = data.total_games || 0;
    
    if (data.timestamp) {
        const date = new Date(data.timestamp);
        document.getElementById('lastUpdate').textContent = date.toLocaleTimeString();
    }
}

// Render a single game card
function renderGame(game) {
    const container = document.getElementById('gamesContainer');
    const card = document.createElement('div');
    card.className = 'game-card';
    card.id = `game-${game.event_id}`;

    const liveData = game.live_data;
    const momentum = liveData?.momentum;

    card.innerHTML = `
        <!-- Compact Game Header -->
        <div class="game-header-compact">
            <div class="header-left">
                <span class="game-league">${game.sport}</span>
                <span class="live-status">
                    <span class="live-indicator"></span>
                    LIVE
                </span>
            </div>
            <div class="match-time-compact">${getTimeDisplay(liveData)}</div>
        </div>

        <!-- Compact Scoreboard - Soccer Style -->
        <div class="scoreboard-compact">
            <div class="team-row">
                <span class="team-name">${game.home_team}</span>
            </div>
            <div class="score-display">
                <span>${liveData?.home_score || 0}</span>
                <span class="score-separator">-</span>
                <span>${liveData?.away_score || 0}</span>
            </div>
            <div class="team-row">
                <span class="team-name">${game.away_team}</span>
            </div>
        </div>

        <!-- Compact Betting Odds -->
        <div class="betting-section-compact">
            <div class="odds-row">
                ${renderCompactOdds(game.moneyline)}
            </div>
        </div>

        <!-- Collapsible Sections -->
        <div class="collapsible-sections">
            ${momentum ? `
                <button class="collapse-toggle" onclick="toggleSection('momentum-${game.event_id}')">
                    <i data-lucide="activity"></i>
                    <span>Momentum & Stats</span>
                    <i data-lucide="chevron-down" class="chevron"></i>
                </button>
                <div id="momentum-${game.event_id}" class="collapse-content" style="display: none;">
                    ${renderMomentumSection(game)}
                </div>
            ` : ''}
            
            ${momentum?.recent_comments ? `
                <button class="collapse-toggle" onclick="toggleSection('comments-${game.event_id}')">
                    <i data-lucide="message-square"></i>
                    <span>Recent Events (${momentum.recent_comments.length})</span>
                    <i data-lucide="chevron-down" class="chevron"></i>
                </button>
                <div id="comments-${game.event_id}" class="collapse-content" style="display: none;">
                    ${renderCommentsSection(momentum.recent_comments, game.home_team, game.away_team)}
                </div>
            ` : ''}
            
            <div class="external-links">
                <a href="${game.polymarket_url}" target="_blank" class="external-link polymarket">
                    <i data-lucide="trending-up"></i>
                    <span>Polymarket</span>
                </a>
                ${liveData?.event_id ? `
                    <a href="https://www.sofascore.com/event/${liveData.event_id}" target="_blank" class="external-link sofascore">
                        <i data-lucide="activity"></i>
                        <span>SofaScore</span>
                    </a>
                ` : ''}
            </div>
        </div>
    `;

    container.appendChild(card);

    // Create momentum chart if data exists
    if (momentum?.momentum_graph) {
        setTimeout(() => createMomentumChart(game.event_id, momentum.momentum_graph, game.home_team, game.away_team), 100);
    }

    // Re-initialize Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

// Get time display
function getTimeDisplay(liveData) {
    if (!liveData) return 'Live';
    
    if (liveData.status && liveData.status.toLowerCase().includes('halftime')) {
        return 'Halftime';
    }
    
    if (liveData.current_minute !== null && liveData.current_minute !== undefined) {
        return `${liveData.current_minute}'`;
    }
    
    return liveData.status || 'Live';
}

// Render betting odds
function renderOdds(moneyline) {
    if (!moneyline || !moneyline.outcomes) return '<p>No odds available</p>';

    return moneyline.outcomes.map(outcome => `
        <div class="odds-card">
            <div class="odds-team-name">${outcome.name}</div>
            <div class="odds-price">${(outcome.price * 100).toFixed(1)}%</div>
            <div class="odds-spread">Spread: ${(outcome.spread * 100).toFixed(2)}%</div>
        </div>
    `).join('');
}

// Render compact betting odds
function renderCompactOdds(moneyline) {
    if (!moneyline || !moneyline.outcomes) return '<span class="no-odds">No odds available</span>';

    return moneyline.outcomes.map(outcome => `
        <div class="odds-item">
            <span class="odds-label">${outcome.name}</span>
            <span class="odds-value">${(outcome.price * 100).toFixed(1)}%</span>
        </div>
    `).join('');
}

// Toggle collapsible section
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const button = section.previousElementSibling;
    const chevron = button.querySelector('.chevron');
    
    if (section.style.display === 'none') {
        section.style.display = 'block';
        chevron.style.transform = 'rotate(180deg)';
    } else {
        section.style.display = 'none';
        chevron.style.transform = 'rotate(0deg)';
    }
    
    // Re-initialize Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

// Render momentum section
function renderMomentumSection(game) {
    const momentum = game.live_data.momentum;
    const value = momentum.momentum_value || 0;
    
    let momentumIcon = '↔️';
    let momentumText = 'Evenly Matched';
    let momentumClass = 'neutral';
    
    // Improved momentum logic based on actual values
    // Positive = Home advantage, Negative = Away advantage
    if (value >= 35) {
        momentumIcon = '🔥';
        momentumText = `${game.home_team} Dominating`;
        momentumClass = 'home-strong';
    } else if (value >= 10) {
        momentumIcon = '↗️';
        momentumText = `${game.home_team} Ahead`;
        momentumClass = 'home';
    } else if (value <= -35) {
        momentumIcon = '🔥';
        momentumText = `${game.away_team} Dominating`;
        momentumClass = 'away-strong';
    } else if (value <= -10) {
        momentumIcon = '↘️';
        momentumText = `${game.away_team} Ahead`;
        momentumClass = 'away';
    } else {
        // -10 to +10 is truly balanced
        momentumIcon = '↔️';
        momentumText = 'Evenly Matched';
        momentumClass = 'neutral';
    }

    return `
        <div class="momentum-section">
            <h3 class="section-title">Game Momentum & Statistics</h3>
            
            ${momentum.momentum_value !== null ? `
                <div class="momentum-indicator ${momentumClass}">
                    <span class="momentum-icon">${momentumIcon}</span>
                    <span class="momentum-text">${momentumText}</span>
                    <span class="momentum-value">(${momentum.momentum_value > 0 ? '+' : ''}${momentum.momentum_value})</span>
                </div>
            ` : ''}
            
            ${momentum.momentum_graph ? `
                <div class="chart-container">
                    <canvas id="chart-${game.event_id}"></canvas>
                </div>
            ` : ''}
            
            ${renderStats(momentum, game.home_team, game.away_team)}
        </div>
    `;
}

// Render statistics
function renderStats(momentum, homeTeam, awayTeam) {
    const stats = [];
    
    if (momentum.possession_home !== null && momentum.possession_away !== null) {
        stats.push({
            name: 'Possession',
            home: momentum.possession_home,
            away: momentum.possession_away,
            isPercentage: true
        });
    }
    
    if (momentum.attacks_home !== null && momentum.attacks_away !== null) {
        stats.push({
            name: 'Attacks',
            home: momentum.attacks_home,
            away: momentum.attacks_away,
            isPercentage: false
        });
    }
    
    if (momentum.dangerous_attacks_home !== null && momentum.dangerous_attacks_away !== null) {
        stats.push({
            name: 'Dangerous Attacks',
            home: momentum.dangerous_attacks_home,
            away: momentum.dangerous_attacks_away,
            isPercentage: false
        });
    }
    
    if (stats.length === 0) return '';
    
    return `
        <div class="stats-grid">
            ${stats.map(stat => {
                const total = stat.home + stat.away;
                const homePercent = total > 0 ? (stat.home / total) * 100 : 50;
                
                return `
                    <div class="stat-card">
                        <div class="stat-name">${stat.name}</div>
                        <div class="stat-bar">
                            <div class="stat-bar-fill" style="width: ${homePercent}%"></div>
                        </div>
                        <div class="stat-values">
                            <span class="stat-home">${homeTeam}: ${stat.home}${stat.isPercentage ? '%' : ''}</span>
                            <span class="stat-away">${awayTeam}: ${stat.away}${stat.isPercentage ? '%' : ''}</span>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// Render comments section
function renderCommentsSection(comments, homeTeam, awayTeam) {
    if (!comments || comments.length === 0) return '';

    return `
        <div class="comments-section">
            <h3 class="section-title">Recent Events</h3>
            <div class="comments-list">
                ${comments.map(comment => {
                    const icon = EVENT_ICONS[comment.event_type] || '▪️';
                    const teamClass = comment.is_home ? 'home' : 'away';
                    const teamSide = comment.is_home ? '🏠' : '✈️';
                    
                    return `
                        <div class="comment-item ${teamClass}">
                            <div class="comment-icon">${icon}</div>
                            <div class="comment-content">
                                <div class="comment-header">
                                    <span class="comment-time">${comment.time}'</span>
                                    <span class="comment-type">${teamSide} ${comment.event_type}</span>
                                </div>
                                <div class="comment-text">${comment.text}</div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

// Create momentum chart using Chart.js
function createMomentumChart(eventId, graphData, homeTeam, awayTeam) {
    const canvas = document.getElementById(`chart-${eventId}`);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    // Destroy existing chart if exists
    if (charts[eventId]) {
        charts[eventId].destroy();
    }

    // Prepare data
    const labels = graphData.map(point => `${point.minute}'`);
    const values = graphData.map(point => point.value);

    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 250);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.5)');
    gradient.addColorStop(0.5, 'rgba(99, 102, 241, 0.1)');
    gradient.addColorStop(1, 'rgba(139, 92, 246, 0.5)');

    charts[eventId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Momentum',
                data: values,
                borderColor: '#6366f1',
                backgroundColor: gradient,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#6366f1',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1a1f3a',
                    titleColor: '#fff',
                    bodyColor: '#a0aec0',
                    borderColor: '#2d3748',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: (context) => `Minute ${context[0].label}`,
                        label: (context) => {
                            const value = context.parsed.y;
                            const team = value > 0 ? homeTeam : awayTeam;
                            return `${team}: ${Math.abs(value)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#2d3748',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#718096',
                        maxTicksLimit: 12
                    }
                },
                y: {
                    grid: {
                        color: '#2d3748',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#718096',
                        callback: function(value) {
                            return Math.abs(value);
                        }
                    },
                    border: {
                        display: false
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

// Cleanup
window.addEventListener('beforeunload', () => {
    if (refreshTimer) clearInterval(refreshTimer);
    Object.values(charts).forEach(chart => chart.destroy());
});

