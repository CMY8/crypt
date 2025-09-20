// Application Data
const appData = {
  portfolio: {
    total_balance: 125000.00,
    available_balance: 98500.00,
    locked_balance: 26500.00,
    daily_pnl: 1250.50,
    unrealized_pnl: -320.75,
    assets: {
      USDT: {free: 45000, locked: 15000, total: 60000, percentage: 48.0},
      BTC: {free: 1.5, locked: 0.5, total: 2.0, percentage: 32.0},
      ETH: {free: 8.0, locked: 2.0, total: 10.0, percentage: 16.0},
      BNB: {free: 20.0, locked: 5.0, total: 25.0, percentage: 4.0}
    }
  },
  trades: [
    {id: 1, symbol: "BTCUSDT", side: "BUY", quantity: 0.1, price: 45000, pnl: 150.25, timestamp: "2025-09-17T10:30:00Z", strategy: "MomentumStrategy"},
    {id: 2, symbol: "ETHUSDT", side: "SELL", quantity: 2.0, price: 2800, pnl: -75.50, timestamp: "2025-09-17T09:15:00Z", strategy: "MeanReversion"},
    {id: 3, symbol: "BTCUSDT", side: "SELL", quantity: 0.05, price: 44800, pnl: 95.75, timestamp: "2025-09-17T08:45:00Z", strategy: "GridStrategy"}
  ],
  prices: {
    BTCUSDT: {price: 45250.00, change_24h: 2.5, volume: 15000000},
    ETHUSDT: {price: 2850.00, change_24h: -1.2, volume: 8000000},
    BNBUSDT: {price: 315.50, change_24h: 0.8, volume: 2500000}
  },
  open_positions: [
    {symbol: "BTCUSDT", side: "LONG", quantity: 0.25, entry_price: 44500, current_price: 45250, pnl: 187.50, strategy: "MomentumStrategy"},
    {symbol: "ETHUSDT", side: "SHORT", quantity: 1.5, entry_price: 2900, current_price: 2850, pnl: 75.00, strategy: "MeanReversion"}
  ],
  risk_metrics: {
    max_drawdown: 0.08,
    current_drawdown: 0.02,
    daily_loss_limit: 0.02,
    position_limit: 0.05,
    risk_level: "LOW",
    open_positions_count: 2,
    max_positions: 10
  },
  performance: {
    total_return: 0.15,
    sharpe_ratio: 1.8,
    win_rate: 0.65,
    profit_factor: 1.4,
    total_trades: 156,
    winning_trades: 101,
    losing_trades: 55
  },
  strategies: [
    {name: "MomentumStrategy", enabled: true, status: "ACTIVE", pnl: 1250.50, trades: 45},
    {name: "MeanReversion", enabled: true, status: "ACTIVE", pnl: -125.25, trades: 32},
    {name: "GridStrategy", enabled: false, status: "PAUSED", pnl: 875.75, trades: 28}
  ],
  system_status: {
    api_connected: true,
    websocket_connected: true,
    database_healthy: true,
    last_update: "2025-09-17T11:27:00Z",
    uptime: "2d 14h 32m"
  }
};

// Chart instances
let charts = {};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
  initializeNavigation();
  initializeOverviewPage();
  initializeLiveTradingPage();
  initializePortfolioPage();
  initializeRiskManagementPage();
  initializePerformancePage();
  initializeSettingsPage();
  
  // Start real-time updates
  startRealTimeUpdates();
});

// Navigation functionality
function initializeNavigation() {
  const navLinks = document.querySelectorAll('.nav-link');
  const pages = document.querySelectorAll('.page');

  navLinks.forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      
      const targetPageId = this.getAttribute('data-page');
      console.log('Navigating to:', targetPageId);
      
      // Update active nav link
      navLinks.forEach(l => l.classList.remove('active'));
      this.classList.add('active');
      
      // Show target page
      pages.forEach(page => {
        page.classList.remove('active');
      });
      
      const targetPage = document.getElementById(targetPageId);
      if (targetPage) {
        targetPage.classList.add('active');
        
        // Initialize page-specific content if needed
        switch(targetPageId) {
          case 'portfolio':
            updatePortfolioMetrics();
            break;
          case 'risk-management':
            populatePositionsTable();
            break;
          case 'performance':
            // Performance charts should already be initialized
            break;
        }
      }
    });
  });
}

// Overview Page
function initializeOverviewPage() {
  updateOverviewMetrics();
  populateRecentTrades();
  createPriceChart();
}

function updateOverviewMetrics() {
  document.getElementById('totalBalance').textContent = formatCurrency(appData.portfolio.total_balance);
  document.getElementById('availableBalance').textContent = formatCurrency(appData.portfolio.available_balance);
  document.getElementById('dailyPnl').textContent = formatCurrency(appData.portfolio.daily_pnl);
  document.getElementById('openPositions').textContent = appData.risk_metrics.open_positions_count;
  document.getElementById('successRate').textContent = Math.round(appData.performance.win_rate * 100);
  document.getElementById('lastUpdate').textContent = formatTime(new Date());
}

function populateRecentTrades() {
  const tbody = document.getElementById('recentTradesTable');
  if (tbody) {
    tbody.innerHTML = '';
    
    appData.trades.slice(0, 5).forEach(trade => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${trade.symbol}</td>
        <td class="${trade.side === 'BUY' ? 'positive' : 'negative'}">${trade.side}</td>
        <td>${trade.quantity}</td>
        <td>$${formatNumber(trade.price)}</td>
        <td class="${trade.pnl > 0 ? 'positive' : 'negative'}">$${formatNumber(trade.pnl)}</td>
      `;
      tbody.appendChild(row);
    });
  }
}

function createPriceChart() {
  const ctx = document.getElementById('priceChart');
  if (ctx) {
    const chartData = generatePriceData();
    
    charts.priceChart = new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels: chartData.labels,
        datasets: [{
          label: 'BTCUSDT',
          data: chartData.prices,
          borderColor: '#1FB8CD',
          backgroundColor: 'rgba(31, 184, 205, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          x: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          },
          y: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          }
        }
      }
    });
  }
}

// Live Trading Page
function initializeLiveTradingPage() {
  populateStrategies();
  setupTradingControls();
}

function populateStrategies() {
  const container = document.getElementById('strategiesContainer');
  if (container) {
    container.innerHTML = '';
    
    appData.strategies.forEach((strategy, index) => {
      const strategyElement = document.createElement('div');
      strategyElement.className = 'strategy-item';
      strategyElement.innerHTML = `
        <div class="strategy-info">
          <h4>${strategy.name}</h4>
          <div class="strategy-stats">
            PnL: <span class="${strategy.pnl > 0 ? 'positive' : 'negative'}">$${formatNumber(strategy.pnl)}</span> | 
            Trades: ${strategy.trades}
          </div>
        </div>
        <div class="strategy-toggle ${strategy.enabled ? 'active' : ''}" data-strategy-index="${index}"></div>
      `;
      container.appendChild(strategyElement);
    });
    
    // Add toggle functionality with event delegation
    container.addEventListener('click', function(e) {
      if (e.target.classList.contains('strategy-toggle')) {
        const strategyIndex = parseInt(e.target.getAttribute('data-strategy-index'));
        const strategy = appData.strategies[strategyIndex];
        
        if (strategy) {
          strategy.enabled = !strategy.enabled;
          strategy.status = strategy.enabled ? 'ACTIVE' : 'PAUSED';
          
          // Update the toggle visual state
          e.target.classList.toggle('active', strategy.enabled);
          
          console.log(`Strategy ${strategy.name} ${strategy.enabled ? 'enabled' : 'disabled'}`);
        }
      }
    });
  }
}

function setupTradingControls() {
  const emergencyStopBtn = document.getElementById('emergencyStop');
  if (emergencyStopBtn) {
    emergencyStopBtn.addEventListener('click', function() {
      showConfirmationDialog('Emergency Stop', 'Are you sure you want to stop all trading activities?', () => {
        alert('All trading activities have been stopped.');
      });
    });
  }
}

// Portfolio Page
function initializePortfolioPage() {
  updatePortfolioMetrics();
  createAllocationChart();
  createPortfolioChart();
  populateBalancesTable();
}

function updatePortfolioMetrics() {
  const totalEl = document.getElementById('portfolioTotal');
  const availableEl = document.getElementById('portfolioAvailable');
  const lockedEl = document.getElementById('portfolioLocked');
  
  if (totalEl) totalEl.textContent = formatCurrency(appData.portfolio.total_balance);
  if (availableEl) availableEl.textContent = formatCurrency(appData.portfolio.available_balance);
  if (lockedEl) lockedEl.textContent = formatCurrency(appData.portfolio.locked_balance);
}

function createAllocationChart() {
  const ctx = document.getElementById('allocationChart');
  if (ctx && !charts.allocationChart) {
    const assets = appData.portfolio.assets;
    
    charts.allocationChart = new Chart(ctx.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: Object.keys(assets),
        datasets: [{
          data: Object.values(assets).map(asset => asset.percentage),
          backgroundColor: ['#1FB8CD', '#FFC185', '#B4413C', '#5D878F'],
          borderWidth: 2,
          borderColor: '#fff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom'
          }
        }
      }
    });
  }
}

function createPortfolioChart() {
  const ctx = document.getElementById('portfolioChart');
  if (ctx && !charts.portfolioChart) {
    const chartData = generatePortfolioData();
    
    charts.portfolioChart = new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels: chartData.labels,
        datasets: [{
          label: 'Portfolio Value',
          data: chartData.values,
          borderColor: '#1FB8CD',
          backgroundColor: 'rgba(31, 184, 205, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          x: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          },
          y: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          }
        }
      }
    });
  }
}

function populateBalancesTable() {
  const tbody = document.getElementById('balancesTable');
  if (tbody) {
    tbody.innerHTML = '';
    
    Object.entries(appData.portfolio.assets).forEach(([asset, data]) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><strong>${asset}</strong></td>
        <td>${formatNumber(data.free)}</td>
        <td>${formatNumber(data.locked)}</td>
        <td>${formatNumber(data.total)}</td>
        <td>${data.percentage}%</td>
      `;
      tbody.appendChild(row);
    });
  }
}

// Risk Management Page
function initializeRiskManagementPage() {
  // This will be called when the page is first loaded and when navigating to it
}

function populatePositionsTable() {
  const tbody = document.getElementById('positionsTable');
  if (tbody) {
    tbody.innerHTML = '';
    
    appData.open_positions.forEach(position => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${position.symbol}</td>
        <td class="${position.side === 'LONG' ? 'positive' : 'negative'}">${position.side}</td>
        <td>${position.quantity}</td>
        <td>$${formatNumber(position.entry_price)}</td>
        <td>$${formatNumber(position.current_price)}</td>
        <td class="${position.pnl > 0 ? 'positive' : 'negative'}">$${formatNumber(position.pnl)}</td>
        <td>${position.strategy}</td>
      `;
      tbody.appendChild(row);
    });
  }
}

// Performance Page
function initializePerformancePage() {
  createEquityChart();
  createDistributionChart();
}

function createEquityChart() {
  const ctx = document.getElementById('equityChart');
  if (ctx && !charts.equityChart) {
    const chartData = generateEquityData();
    
    charts.equityChart = new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels: chartData.labels,
        datasets: [{
          label: 'Equity',
          data: chartData.values,
          borderColor: '#1FB8CD',
          backgroundColor: 'rgba(31, 184, 205, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          x: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          },
          y: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          }
        }
      }
    });
  }
}

function createDistributionChart() {
  const ctx = document.getElementById('distributionChart');
  if (ctx && !charts.distributionChart) {
    charts.distributionChart = new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Wins', 'Losses'],
        datasets: [{
          label: 'Trade Distribution',
          data: [appData.performance.winning_trades, appData.performance.losing_trades],
          backgroundColor: ['#1FB8CD', '#B4413C'],
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          x: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          },
          y: {
            display: true,
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          }
        }
      }
    });
  }
}

// Settings Page
function initializeSettingsPage() {
  const saveBtn = document.getElementById('saveSettings');
  if (saveBtn) {
    saveBtn.addEventListener('click', function() {
      alert('Settings saved successfully!');
    });
  }
}

// Real-time updates
function startRealTimeUpdates() {
  setInterval(() => {
    updatePrices();
    updateMetrics();
    updateLastUpdateTime();
  }, 5000);
}

function updatePrices() {
  // Simulate price changes
  Object.keys(appData.prices).forEach(symbol => {
    const change = (Math.random() - 0.5) * 100; // Random price change
    appData.prices[symbol].price += change;
    appData.prices[symbol].change_24h = (Math.random() - 0.5) * 5;
  });
  
  // Update position PnL
  appData.open_positions.forEach(position => {
    const newPrice = appData.prices[position.symbol].price;
    position.current_price = newPrice;
    if (position.side === 'LONG') {
      position.pnl = (newPrice - position.entry_price) * position.quantity;
    } else {
      position.pnl = (position.entry_price - newPrice) * position.quantity;
    }
  });
}

function updateMetrics() {
  // Update daily PnL based on position changes
  const totalUnrealizedPnl = appData.open_positions.reduce((sum, pos) => sum + pos.pnl, 0);
  appData.portfolio.unrealized_pnl = totalUnrealizedPnl;
  
  // Update overview metrics if on overview page
  if (document.getElementById('overview').classList.contains('active')) {
    updateOverviewMetrics();
  }
}

function updateLastUpdateTime() {
  const lastUpdateEl = document.getElementById('lastUpdate');
  if (lastUpdateEl) {
    lastUpdateEl.textContent = formatTime(new Date());
  }
}

// Utility functions
function formatCurrency(value) {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value);
}

function formatNumber(value) {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 8
  }).format(value);
}

function formatTime(date) {
  return new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(date);
}

// Mock data generators
function generatePriceData() {
  const labels = [];
  const prices = [];
  const basePrice = appData.prices.BTCUSDT.price;
  
  for (let i = 23; i >= 0; i--) {
    const time = new Date();
    time.setHours(time.getHours() - i);
    labels.push(time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }));
    
    const variation = (Math.random() - 0.5) * 1000;
    prices.push(basePrice + variation);
  }
  
  return { labels, prices };
}

function generatePortfolioData() {
  const labels = [];
  const values = [];
  const baseValue = appData.portfolio.total_balance;
  
  for (let i = 29; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    
    const growth = Math.random() * 0.02 + 0.995; // Small daily growth
    values.push(baseValue * Math.pow(growth, i));
  }
  
  return { labels, values };
}

function generateEquityData() {
  const labels = [];
  const values = [];
  let equity = 100000; // Starting equity
  
  for (let i = 29; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    
    const dailyReturn = (Math.random() - 0.4) * 0.02; // Slightly positive bias
    equity *= (1 + dailyReturn);
    values.push(equity);
  }
  
  return { labels, values };
}

function showConfirmationDialog(title, message, onConfirm) {
  const dialog = document.createElement('div');
  dialog.className = 'confirmation-dialog';
  dialog.innerHTML = `
    <div class="dialog-content">
      <h3>${title}</h3>
      <p>${message}</p>
      <div class="dialog-buttons">
        <button class="btn btn--outline" id="cancelBtn">Cancel</button>
        <button class="btn btn--primary" id="confirmBtn">Confirm</button>
      </div>
    </div>
  `;
  
  document.body.appendChild(dialog);
  
  document.getElementById('cancelBtn').addEventListener('click', () => {
    document.body.removeChild(dialog);
  });
  
  document.getElementById('confirmBtn').addEventListener('click', () => {
    onConfirm();
    document.body.removeChild(dialog);
  });
  
  // Close on backdrop click
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) {
      document.body.removeChild(dialog);
    }
  });
}