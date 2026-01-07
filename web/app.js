/**
 * ZeroChess - WebSocket Client & Dashboard Logic
 */

// --- State ---
let ws = null;
let activeGames = new Map();
let winHistory = [];
let chart = null;

// --- Elements ---
const elements = {
    statusBadge: document.getElementById('status-badge'),
    statusText: document.querySelector('.status-text'),

    numGames: document.getElementById('num-games'),
    concurrent: document.getElementById('concurrent'),
    timeControl: document.getElementById('time-control'),
    increment: document.getElementById('increment'),

    btnStart: document.getElementById('btn-start'),
    btnPause: document.getElementById('btn-pause'),
    btnStop: document.getElementById('btn-stop'),

    completed: document.getElementById('completed'),
    total: document.getElementById('total'),
    progressFill: document.getElementById('progress-fill'),

    engine1Name: document.getElementById('engine1-name'),
    engine1Score: document.getElementById('engine1-score'),
    engine1Wins: document.getElementById('engine1-wins'),
    engine2Name: document.getElementById('engine2-name'),
    engine2Score: document.getElementById('engine2-score'),
    engine2Wins: document.getElementById('engine2-wins'),
    draws: document.getElementById('draws'),
    eloDiff: document.getElementById('elo-diff'),

    gamesGrid: document.getElementById('games-grid'),
    gameCount: document.getElementById('game-count'),

    gamesPerSecond: document.getElementById('games-per-second'),
};

// --- WebSocket ---
function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        console.log('Connected to ZeroChess server');
        updateStatus('Ready', '');
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleEvent(message.event, message.data);
    };

    ws.onclose = () => {
        console.log('Disconnected, reconnecting in 3s...');
        updateStatus('Disconnected', '');
        setTimeout(connect, 3000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function send(command, data = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command, ...data }));
    }
}

// --- Event Handlers ---
function handleEvent(event, data) {
    switch (event) {
        case 'state':
            handleState(data);
            break;
        case 'started':
            handleStarted(data);
            break;
        case 'game_start':
            handleGameStart(data);
            break;
        case 'move':
            handleMove(data);
            break;
        case 'game_end':
            handleGameEnd(data);
            break;
        case 'stats':
            updateStats(data);
            break;
        case 'paused':
            updateStatus('Paused', 'paused');
            break;
        case 'resumed':
            updateStatus('Running', 'running');
            break;
        case 'stopped':
        case 'completed':
            handleCompleted(data);
            break;
        case 'error':
            console.error('Server error:', data.message);
            break;
    }
}

function handleState(data) {
    if (data.running) {
        updateStatus(data.paused ? 'Paused' : 'Running', data.paused ? 'paused' : 'running');
        setButtonsRunning(true, data.paused);
    }

    if (data.stats) {
        updateStats(data.stats);

        // Populate chart from existing data
        if (data.stats.completed > 0 && winHistory.length === 0) {
            // Create a single point from current totals
            winHistory.push({
                engine1_score: data.stats.engine1_score || 0,
                engine2_score: data.stats.engine2_score || 0,
                completed: data.stats.completed || 0
            });
            updateChart();
        }
    }

    if (data.active_games) {
        data.active_games.forEach(game => {
            addGameBoard(game);
        });
    }
}

function handleStarted(data) {
    updateStatus('Running', 'running');
    setButtonsRunning(true, false);
    elements.total.textContent = data.config?.num_games || '?';
}

function handleGameStart(data) {
    addGameBoard(data);
    updateGameCount();
}

function handleMove(data) {
    const board = document.getElementById(`board-${data.game_id}`);
    if (board) {
        renderBoard(board, data.fen);

        const moveCount = document.querySelector(`#game-${data.game_id} .game-move-count`);
        if (moveCount) {
            moveCount.textContent = `Move ${data.move_count}`;
        }
    }
}

function handleGameEnd(data) {
    removeGameBoard(data.game_id);
    updateGameCount();

    if (data.stats) {
        updateStats(data.stats);
    }

    // Track for chart
    winHistory.push({
        engine1_score: data.stats?.engine1_score || 0,
        engine2_score: data.stats?.engine2_score || 0,
        completed: data.stats?.completed || 0
    });
    updateChart();
}

function handleCompleted(data) {
    updateStatus('Completed', '');
    setButtonsRunning(false, false);

    if (data.stats) {
        updateStats(data.stats);
    }

    // Clear active games
    elements.gamesGrid.innerHTML = '';
    activeGames.clear();
    updateGameCount();
}

// --- UI Updates ---
function updateStatus(text, className) {
    elements.statusText.textContent = text;
    elements.statusBadge.className = `status-badge ${className}`;
}

function setButtonsRunning(running, paused) {
    elements.btnStart.disabled = running;
    elements.btnPause.disabled = !running;
    elements.btnStop.disabled = !running;

    elements.btnPause.textContent = paused ? '▶ Resume' : '⏸ Pause';
}

function updateStats(stats) {
    if (!stats) return;

    // Animate value changes
    animateValue(elements.completed, stats.completed || 0);
    animateValue(elements.engine1Score, stats.engine1_score || 0);
    animateValue(elements.engine2Score, stats.engine2_score || 0);
    animateValue(elements.engine1Wins, stats.engine1_wins || 0);
    animateValue(elements.engine2Wins, stats.engine2_wins || 0);
    animateValue(elements.draws, stats.draws || 0);

    // Engine names
    if (stats.engine1_name) {
        elements.engine1Name.textContent = stats.engine1_name;
    }
    if (stats.engine2_name) {
        elements.engine2Name.textContent = stats.engine2_name;
    }

    // Progress
    const total = stats.total_games || parseInt(elements.numGames.value);
    elements.total.textContent = total;
    const pct = total > 0 ? (stats.completed / total) * 100 : 0;
    elements.progressFill.style.width = `${pct}%`;

    // Elo (calculate from win rate)
    const e1 = stats.engine1_wins || 0;
    const e2 = stats.engine2_wins || 0;
    const d = stats.draws || 0;
    const totalGames = e1 + e2 + d;

    if (totalGames > 0) {
        const score = (e1 + d * 0.5) / totalGames;
        const clampedScore = Math.max(0.001, Math.min(0.999, score));
        const eloDiff = -400 * Math.log10(1 / clampedScore - 1);
        elements.eloDiff.textContent = `${eloDiff >= 0 ? '+' : ''}${eloDiff.toFixed(0)}`;
    }
}

function animateValue(element, newValue) {
    const currentValue = parseFloat(element.textContent) || 0;
    if (currentValue !== newValue) {
        element.textContent = typeof newValue === 'number' && newValue % 1 !== 0
            ? newValue.toFixed(1)
            : newValue;
        element.classList.add('updated');
        setTimeout(() => element.classList.remove('updated'), 300);
    }
}

function updateGameCount() {
    elements.gameCount.textContent = `(${activeGames.size})`;
}

// --- Chess Board ---
const PIECE_SYMBOLS = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
};

function fenToBoard(fen) {
    const parts = fen.split(' ');
    const rows = parts[0].split('/');
    const board = [];

    for (const row of rows) {
        const boardRow = [];
        for (const char of row) {
            if (/\d/.test(char)) {
                for (let i = 0; i < parseInt(char); i++) {
                    boardRow.push('');
                }
            } else {
                boardRow.push(PIECE_SYMBOLS[char] || '');
            }
        }
        board.push(boardRow);
    }

    return board;
}

function renderBoard(container, fen) {
    const board = fenToBoard(fen);
    container.innerHTML = '';

    for (let row = 0; row < 8; row++) {
        for (let col = 0; col < 8; col++) {
            const square = document.createElement('div');
            square.className = `square ${(row + col) % 2 === 0 ? 'light' : 'dark'}`;
            square.textContent = board[row][col];
            container.appendChild(square);
        }
    }
}

function addGameBoard(game) {
    activeGames.set(game.game_id, game);

    const gameEl = document.createElement('div');
    gameEl.id = `game-${game.game_id}`;
    gameEl.className = 'game-board';

    gameEl.innerHTML = `
        <div class="game-header">
            <div class="game-players">
                <span>${game.white}</span>
                <span style="color: var(--text-muted)">vs</span>
                <span>${game.black}</span>
            </div>
            <span class="game-move-count">Move ${game.moves?.length || 0}</span>
        </div>
        <div class="game-opening" style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 8px;">
            ${game.eco} ${game.opening}
        </div>
        <div class="board-container" id="board-${game.game_id}"></div>
    `;

    elements.gamesGrid.appendChild(gameEl);

    const boardContainer = document.getElementById(`board-${game.game_id}`);
    renderBoard(boardContainer, game.fen);
}

function removeGameBoard(gameId) {
    activeGames.delete(gameId);
    const el = document.getElementById(`game-${gameId}`);
    if (el) {
        el.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => el.remove(), 300);
    }
}

// --- Chart ---
function initChart() {
    const canvas = document.getElementById('win-chart');
    if (!canvas) {
        console.error('Chart canvas not found');
        return;
    }

    // Check if Chart.js loaded
    if (typeof Chart === 'undefined') {
        console.error('Chart.js not loaded');
        canvas.parentElement.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);">Chart library not available</div>';
        return;
    }

    const ctx = canvas.getContext('2d');

    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'LC0 Score',
                    data: [],
                    borderColor: '#7c3aed',
                    backgroundColor: 'rgba(124, 58, 237, 0.1)',
                    fill: true,
                    tension: 0.4,
                },
                {
                    label: 'Stockfish Score',
                    data: [],
                    borderColor: '#0ea5e9',
                    backgroundColor: 'rgba(14, 165, 233, 0.1)',
                    fill: true,
                    tension: 0.4,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    display: true,
                    title: { display: true, text: 'Games Completed', color: '#8888a0' },
                    ticks: { color: '#8888a0' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y: {
                    display: true,
                    title: { display: true, text: 'Score', color: '#8888a0' },
                    ticks: { color: '#8888a0' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#f0f0f5' }
                }
            }
        }
    });
}

function updateChart() {
    if (!chart || winHistory.length === 0) return;

    // Sample at most 100 points
    const step = Math.max(1, Math.floor(winHistory.length / 100));
    const sampled = winHistory.filter((_, i) => i % step === 0);

    chart.data.labels = sampled.map(d => d.completed);
    chart.data.datasets[0].data = sampled.map(d => d.engine1_score);
    chart.data.datasets[1].data = sampled.map(d => d.engine2_score);
    chart.update('none');
}

// --- Button Handlers ---
elements.btnStart.addEventListener('click', () => {
    const config = {
        num_games: parseInt(elements.numGames.value),
        concurrent_games: parseInt(elements.concurrent.value),
        time_control: parseInt(elements.timeControl.value),
        increment: parseFloat(elements.increment.value),
    };

    winHistory = [];
    send('start', { config });
});

elements.btnPause.addEventListener('click', () => {
    if (elements.btnPause.textContent.includes('Resume')) {
        send('resume');
    } else {
        send('pause');
    }
});

elements.btnStop.addEventListener('click', () => {
    send('stop');
});

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    connect();
});
