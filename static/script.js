let currentTaskId = null;
let pollInterval = null;
let allResults = [];
let currentFilter = 'all';

const $ = (sel) => document.querySelector(sel);

const startBtn = $('#startBtn');
const keywordsInput = $('#keywords');
const countInput = $('#count');
const progressSection = $('#progressSection');
const progressFill = $('#progressFill');
const statusText = $('#statusText');
const resultsSection = $('#resultsSection');
const resultsList = $('#resultsList');
const totalCount = $('#totalCount');
const exportBtn = $('#exportBtn');
const toast = $('#toast');

function showToast(msg) {
    toast.textContent = msg;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 4000);
}

function parseKeywords(raw) {
    return raw
        .split(/[\n,]+/)
        .map(s => s.trim())
        .filter(Boolean);
}

function renderResults() {
    const filtered = currentFilter === 'all'
        ? allResults
        : allResults.filter(r => r.type === currentFilter);

    resultsList.innerHTML = '';

    if (filtered.length === 0) {
        resultsList.innerHTML = '<p style="color:#8b98a5;text-align:center;padding:20px">Ничего не найдено</p>';
        return;
    }

    for (const item of filtered) {
        const div = document.createElement('div');
        div.className = 'result-item';
        div.innerHTML = `
            <div>
                <span class="badge ${item.type}">${item.type === 'group' ? 'Группа' : 'Юзер'}</span>
                <a class="link" href="${item.link}" target="_blank" rel="noopener">${item.link}</a>
            </div>
            <div class="name">${escapeHtml(item.name)}</div>
            ${item.extra ? `<div class="extra">${escapeHtml(item.extra)}</div>` : ''}
            <div class="matches">🔑 ${item.matched_keywords.join(', ')}</div>
        `;
        resultsList.appendChild(div);
    }
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

async function pollStatus() {
    if (!currentTaskId) return;
    try {
        const res = await fetch(`/api/status/${currentTaskId}`);
        const data = await res.json();

        if (data.status === 'error') {
            clearInterval(pollInterval);
            statusText.textContent = '❌ Ошибка: ' + data.message;
            startBtn.disabled = false;
            showToast(data.message);
            return;
        }

        const pct = data.total ? Math.round((data.progress / data.total) * 100) : 0;
        progressFill.style.width = pct + '%';
        statusText.textContent = `${data.message} (${pct}%)`;

        if (data.status === 'done') {
            clearInterval(pollInterval);
            await loadResults();
            startBtn.disabled = false;
            statusText.textContent = '✅ Готово!';
        }
    } catch (e) {
        clearInterval(pollInterval);
        showToast('Ошибка соединения');
        startBtn.disabled = false;
    }
}

async function loadResults() {
    const res = await fetch(`/api/results/${currentTaskId}`);
    const data = await res.json();
    allResults = data.results || [];
    totalCount.textContent = allResults.length;
    exportBtn.href = `/api/export/${currentTaskId}`;
    resultsSection.classList.remove('hidden');
    renderResults();
}

startBtn.addEventListener('click', async () => {
    const keywords = parseKeywords(keywordsInput.value);
    if (keywords.length === 0) {
        showToast('Введите хотя бы одно ключевое слово');
        return;
    }

    const count = parseInt(countInput.value, 10) || 30;

    startBtn.disabled = true;
    resultsSection.classList.add('hidden');
    progressSection.classList.remove('hidden');
    progressFill.style.width = '0%';
    statusText.textContent = 'Запуск...';

    try {
        const res = await fetch('/api/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keywords, count })
        });
        const data = await res.json();
        currentTaskId = data.task_id;
        pollInterval = setInterval(pollStatus, 1000);
        pollStatus();
    } catch (e) {
        showToast('Не удалось запустить парсинг');
        startBtn.disabled = false;
    }
});

document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
        document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        currentFilter = chip.dataset.filter;
        renderResults();
    });
});