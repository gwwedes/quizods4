const API_URL = "http://127.0.0.1:8000";

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
}

let questions = [];
let currentQuestionIndex = 0;
let score = 0;
let timeLeft = 60;
let timerInterval;
let progress = 0;
let historico = [];
let inicioQuestao = 0;

let currentUser = { name: "Convidado", avatar: "🎓" };
let rankingData = [];

let waveChartInstance = null;
let doughnutChartInstance = null;
let topicBarChartInstance = null;

const categoryElem = document.getElementById('category');
const questionElem = document.getElementById('question');
const answerButtons = document.querySelectorAll('.answer');
const scoreElem = document.getElementById('score');
const highScoreElem = document.getElementById('high-score');
const timeElem = document.getElementById('time');
const progressElem = document.getElementById('progress');
const startButton = document.getElementById('start');

if (localStorage.getItem('highScore') && highScoreElem) {
    highScoreElem.innerText = localStorage.getItem('highScore');
}

function switchView(viewId) {
    document.querySelectorAll('.view-section').forEach(section => {
        section.classList.remove('active');
    });

    const targetView = document.getElementById(viewId);
    if (targetView) {
        targetView.classList.add('active');
    }

    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    
    if (viewId === 'view-home') document.querySelectorAll('.nav-btn')[0].classList.add('active');
    if (viewId === 'view-dashboard') {
        document.querySelectorAll('.nav-btn')[2].classList.add('active');
        renderDashboardCharts();
    }
    if (viewId === 'view-ia') {
        generateAIAnalysis();
    }
    if (viewId === 'view-ranking') {
        renderRankingTable();
    }
}

function openLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.classList.add('active');
}

function closeLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.classList.remove('active');
}

async function handleUserSubmit(event) {
    event.preventDefault();
    const nameInput = document.getElementById('username').value.trim();
    const selectedAvatar = document.querySelector('input[name="avatar"]:checked').value;

    currentUser.name = nameInput || "Participante";
    currentUser.avatar = selectedAvatar;

    // Cria o usuário no banco
    try {
        const resposta = await fetch(`${API_URL}/api/usuarios`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nome: currentUser.name })
        });

        const dados = await resposta.json();

        if (dados.id) {
            localStorage.setItem('usuarioId', dados.id);
        }
    } catch (erro) {
        console.error("Erro ao criar usuário:", erro);
    }

    const nameDisp = document.getElementById('quiz-user-name');
    const avatarDisp = document.getElementById('quiz-user-avatar');
    if (nameDisp) nameDisp.innerText = currentUser.name;
    if (avatarDisp) avatarDisp.innerText = currentUser.avatar;

    closeLoginModal();
    switchView('view-quiz');
    startGame();
}
async function startGame() {
    score = 0;
    currentQuestionIndex = 0;
    historico = [];
    if (scoreElem) scoreElem.innerText = score;
    if (startButton) startButton.disabled = true;
    timeLeft = 0;
    if (timeElem) timeElem.innerText = timeLeft;

    try {
        const resposta = await fetch(`${API_URL}/api/perguntas`);
        questions = await resposta.json();
    } catch (erro) {
        if (questionElem) questionElem.innerText = 'Não consegui carregar as perguntas.';
        if (startButton) startButton.disabled = false;
        return;
    }

    if (!questions || questions.length === 0) {
        if (questionElem) questionElem.innerText = 'Nenhuma pergunta disponível.';
        if (startButton) startButton.disabled = false;
        return;
    }

    clearInterval(timerInterval);
    timerInterval = setInterval(updateTimer, 1000);
    loadQuestion();
}

function loadQuestion() {
    const questionData = questions[currentQuestionIndex];
    inicioQuestao = Date.now();
    if (categoryElem) categoryElem.innerText = `Categoria: ${questionData.categoria}`;
    if (questionElem) questionElem.innerText = questionData.enunciado;

    const opcoes = [...questionData.opcoes];

    answerButtons.forEach((btn, index) => {
        btn.innerHTML = `<span>${opcoes[index]}</span>`;
        btn.classList.remove('correct', 'incorrect');
        btn.disabled = false;
    });

    progress = ((currentQuestionIndex + 1) / questions.length) * 100;
    if (progressElem) progressElem.style.width = `${progress}%`;
}

function updateTimer() {
    timeLeft++;
    if (timeElem) timeElem.innerText = timeLeft;
}


async function checkAnswer(selectedIndex) {
    answerButtons.forEach(btn => btn.disabled = true);

    const questionData = questions[currentQuestionIndex];
    const escolhida = answerButtons[selectedIndex].innerText;

    let resultado;
    try {
        const resposta = await fetch(`${API_URL}/api/responder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pergunta_id: questionData.id,
                resposta: escolhida
            })
        });
        resultado = await resposta.json();
    } catch (erro) {
        answerButtons.forEach(btn => btn.disabled = false);
        return;
    }

    historico.push({
        categoria: questionData.categoria,
        dificuldade: questionData.dificuldade,
        enunciado: questionData.enunciado,
        acertou: !!resultado.acertou,
        tempo_gasto: Math.round((Date.now() - inicioQuestao) / 1000)
    });

    if (resultado.acertou) {
        answerButtons[selectedIndex].classList.add('correct');
        score++;
    } else {
        answerButtons[selectedIndex].classList.add('incorrect');
        answerButtons.forEach(btn => {
            if (btn.innerText === resultado.correta) btn.classList.add('correct');
        });
    }

    if (scoreElem) scoreElem.innerText = score;
    setTimeout(nextQuestion, 1000);
}

function nextQuestion() {
    currentQuestionIndex++;
    if (currentQuestionIndex < questions.length) {
        loadQuestion();
    } else {
        endGame();
    }
}

function endGame() {
    clearInterval(timerInterval);
    answerButtons.forEach(btn => btn.disabled = true);

    if (questionElem) questionElem.innerText = `Fim de jogo! Sua pontuação foi: ${score}`;
    if (categoryElem) categoryElem.innerText = "Parabéns!";

    const currentHighScore = Number(localStorage.getItem('highScore')) || 0;
    if (score > currentHighScore) {
        localStorage.setItem('highScore', score);
        if (highScoreElem) highScoreElem.innerText = score;
    }

    const usuarioId = localStorage.getItem('usuarioId');
    if (usuarioId) {
        fetch(`${API_URL}/api/pontuacao`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                usuario_id: Number(usuarioId),
                pontuacao: score,
                tempo_total: timeLeft
            })
        }).catch(erro => {});
    }

    rankingData.unshift({
        name: currentUser.name,
        avatar: currentUser.avatar,
        score: score,
        total: questions.length || 4,
        status: "Ativo"
    });

    if (startButton) {
        startButton.disabled = false;
        startButton.innerText = "Jogar Novamente";
    }

    if (typeof confetti === 'function' && score > 0) {
        confetti({ particleCount: 80, spread: 60, origin: { y: 0.6 } });
    }

    setTimeout(() => {
        switchView('view-dashboard');
    }, 1200);
}

function renderDashboardCharts() {
    const totalQ = questions.length || 4;
    const accuracyPct = totalQ > 0 ? Math.round((score / totalQ) * 100) : 0;

    const accElem = document.getElementById('dash-accuracy');
    if (accElem) accElem.innerText = `${accuracyPct}%`;

    if (waveChartInstance) waveChartInstance.destroy();
    if (doughnutChartInstance) doughnutChartInstance.destroy();
    if (topicBarChartInstance) topicBarChartInstance.destroy();

    const canvasWave = document.getElementById('waveChart');
    if (canvasWave) {
        const ctxWave = canvasWave.getContext('2d');
        waveChartInstance = new Chart(ctxWave, {
            type: 'line',
            data: {
                labels: ['Início', 'Fase 1', 'Fase 2', 'Pontuação Final'],
                datasets: [
                    {
                        label: 'Sua Pontuação',
                        data: [0, Math.round(score * 0.3), Math.round(score * 0.7), score],
                        borderColor: '#ffc815',
                        backgroundColor: 'rgba(255, 200, 21, 0.2)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Média Global',
                        data: [0, 1, 2, 3],
                        borderColor: '#3b82f6',
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#a7a4c8' } } },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#a7a4c8' } },
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#a7a4c8' } }
                }
            }
        });
    }

    const canvasDoughnut = document.getElementById('doughnutChart');
    if (canvasDoughnut) {
        const ctxDoughnut = canvasDoughnut.getContext('2d');
        doughnutChartInstance = new Chart(ctxDoughnut, {
            type: 'doughnut',
            data: {
                labels: ['Acertos', 'Erros'],
                datasets: [{
                    data: [score, Math.max(0, totalQ - score)],
                    backgroundColor: ['#1ed760', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { color: '#a7a4c8' } } }
            }
        });
    }

    const canvasBar = document.getElementById('topicBarChart');
    if (canvasBar) {
        const ctxBar = canvasBar.getContext('2d');
        topicBarChartInstance = new Chart(ctxBar, {
            type: 'bar',
            data: {
                labels: ['Sua Pontuação', 'Média Geral'],
                datasets: [{
                    label: 'Pontos',
                    data: [score, 2.5],
                    backgroundColor: ['#8b5cf6', '#3b82f6'],
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#a7a4c8' } },
                    x: { ticks: { color: '#a7a4c8' } }
                }
            }
        });
    }
}

// =========================
// ANÁLISE COM IA REAL (GROQ)
// =========================
async function generateAIAnalysis() {
    const totalQ = questions.length || 0;
    const acertos = score;

    const heading = document.getElementById('ai-performance-heading');
    const summary = document.getElementById('ai-performance-summary');
    const level = document.getElementById('ai-level');
    const strong = document.getElementById('ai-strong-point');
    const focus = document.getElementById('ai-focus-area');
    const recList = document.getElementById('ai-rec-list');

    if (!heading) return;

    if (historico.length === 0) {
        heading.innerText = "Aguardando resultado do Quiz...";
        summary.innerText = "Complete o quiz para gerar a análise de Inteligência Artificial.";
        level.innerText = "Pendente";
        strong.innerText = "-";
        focus.innerText = "-";
        recList.innerHTML = '<li><i class="fa-solid fa-check"></i> Faça uma partida no Quiz para sincronizar as métricas de aprendizagem.</li>';
        return;
    }

    heading.innerText = "Analisando com Inteligência Artificial...";
    summary.innerText = "Aguarde, a IA está gerando seu diagnóstico personalizado.";
    level.innerText = "...";
    strong.innerText = "...";
    focus.innerText = "...";
    recList.innerHTML = '<li><i class="fa-solid fa-spinner fa-spin"></i> Gerando análise com IA...</li>';
    const reportBox = document.getElementById('ai-report-body');
    if (reportBox) reportBox.textContent = 'Gerando relatório detalhado...';

    try {
        const resposta = await fetch(`${API_URL}/api/analise-ia`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                nome: currentUser.name || "Aluno",
                pontuacao: score,
                total_perguntas: totalQ,
                acertos: acertos,
                tempo_total: timeLeft,
                respostas: historico
            })
        });

        const dados = await resposta.json();

        if (!resposta.ok || !dados.analise) {
            throw new Error(dados.detail || "Resposta inválida da IA");
        }

        const a = dados.analise;
        heading.innerText = a.titulo || "Diagnóstico de Inteligência Artificial";
        summary.innerText = a.resumo || "";
        level.innerText = a.nivel || "-";
        strong.innerText = a.ponto_forte || "-";
        focus.innerText = a.area_melhorar || "-";

        const reportBody = document.getElementById('ai-report-body');
        if (reportBody) reportBody.textContent = a.relatorio || '';

        recList.innerHTML = "";
        (a.plano || []).forEach(item => {
            const li = document.createElement("li");
            li.innerHTML = '<i class="fa-solid fa-check"></i> ';
            li.appendChild(document.createTextNode(item));
            recList.appendChild(li);
        });
    } catch (erro) {
        console.error(erro);
        heading.innerText = "Erro ao conectar com a IA";
        summary.innerText = "Não foi possível gerar a análise. Verifique se a API está rodando.";
        level.innerText = "Erro";
        strong.innerText = "-";
        focus.innerText = "-";
        recList.innerHTML = '<li><i class="fa-solid fa-triangle-exclamation"></i> Erro: ' + erro.message + '</li>';
    }
}

// =========================
// RANKING (BUSCA DO BANCO)
// =========================
async function renderRankingTable(filterText = '') {
    const tbody = document.getElementById('ranking-tbody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6">Carregando ranking...</td></tr>';

    try {
        const resposta = await fetch(`${API_URL}/api/usuarios`);
        const usuarios = await resposta.json();

        // Mais pontos primeiro; empate -> menor tempo primeiro (sem tempo vai para o fim)
        usuarios.sort((a, b) =>
            (b.pontuacao - a.pontuacao) ||
            ((a.tempo_recorde ?? Infinity) - (b.tempo_recorde ?? Infinity))
        );

        const filtered = usuarios.filter(u => 
            u.nome.toLowerCase().includes(filterText.toLowerCase())
        );

        tbody.innerHTML = '';

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6">Nenhum jogador encontrado.</td></tr>';
            return;
        }

        filtered.forEach((user, idx) => {
            const tr = document.createElement('tr');
            if (user.nome === currentUser.name) tr.className = 'highlight-user';

            let badge = '-';
            if (idx === 0) badge = '🥇 Ouro';
            else if (idx === 1) badge = '🥈 Prata';
            else if (idx === 2) badge = '🥉 Bronze';

            tr.innerHTML = `
                <td>#${idx + 1}</td>
                <td>🎓 ${user.nome}</td>
                <td>${user.pontuacao}</td>
                <td>${user.tempo_recorde != null ? user.tempo_recorde + 's' : '-'}</td>
                <td>Ativo</td>
                <td>${badge}</td>
            `;
            tbody.appendChild(tr);
        });

    } catch (erro) {
        console.error(erro);
        tbody.innerHTML = '<tr><td colspan="6">Erro ao carregar ranking.</td></tr>';
    }
}

function filterRanking() {
    const query = document.getElementById('ranking-search').value;
    renderRankingTable(query);
}

document.addEventListener('DOMContentLoaded', () => {
    switchView('view-home');
});