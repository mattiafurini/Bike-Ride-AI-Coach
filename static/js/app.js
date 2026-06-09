let map;
let pathLayer;
let charts = {};


function initMap() {
    map = L.map('map').setView([0, 0], 2);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);
}
function initCharts() {
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: { grid: { color: 'rgba(255,255,255,0.05)' } }
        },
        elements: {
            point: { radius: 0 },
            line: { tension: 0.4, borderWidth: 2 }
        }
    };

    const ctxElevation = document.getElementById('elevationChart').getContext('2d');
    charts.elevation = new Chart(ctxElevation, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Elevation (m)', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.1)', fill: true }] },
        options: { ...commonOptions, plugins: { title: { display: true, text: 'Elevation', color: '#94a3b8' } } }
    });

    const ctxSpeed = document.getElementById('speedChart').getContext('2d');
    charts.speed = new Chart(ctxSpeed, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Speed (km/h)', data: [], borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)', fill: true }] },
        options: { ...commonOptions, plugins: { title: { display: true, text: 'Speed', color: '#94a3b8' } } }
    });

    const ctxHR = document.getElementById('hrChart').getContext('2d');
    charts.hr = new Chart(ctxHR, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Heart Rate (bpm)', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', fill: true }] },
        options: { ...commonOptions, plugins: { title: { display: true, text: 'Heart Rate', color: '#94a3b8' } } }
    });

    const ctxCadence = document.getElementById('cadenceChart').getContext('2d');
    charts.cadence = new Chart(ctxCadence, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Cadence (rpm)', data: [], borderColor: '#a855f7', backgroundColor: 'rgba(168, 85, 247, 0.1)', fill: true }] },
        options: { ...commonOptions, plugins: { title: { display: true, text: 'Cadence', color: '#94a3b8' } } }
    });
}

let compareMode = false;
let selectedRidesForCompare = [];
let chatHistory = [];

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    initCharts();
    loadRideList();
    setupUpload();
    
    document.getElementById('backBtn').addEventListener('click', showHome);
    document.getElementById('compareBtn').addEventListener('click', toggleCompareMode);
    document.getElementById('closeModalBtn').addEventListener('click', () => {
        document.getElementById('aiModal').classList.add('hidden');
    });
    
    document.getElementById('settingsBtn').addEventListener('click', openSettingsModal);
    document.getElementById('closeSettingsBtn').addEventListener('click', closeSettingsModal);
    document.getElementById('saveSettingsBtn').addEventListener('click', saveApiKey);
    
    document.getElementById('viewNotesBtn').addEventListener('click', viewNotes);
    document.getElementById('closeNotesBtn').addEventListener('click', () => {
        document.getElementById('notesModal').classList.add('hidden');
    });
    document.getElementById('saveNotesBtn').addEventListener('click', saveNotes);
    
    document.getElementById('startAnalysisBtn').addEventListener('click', runAICompare);
    document.getElementById('sendChatBtn').addEventListener('click', sendChatMessage);
    document.getElementById('chatInput').addEventListener('keypress', (e) => {
        if(e.key === 'Enter') sendChatMessage();
    });
});

function toggleCompareMode() {
    compareMode = !compareMode;
    const btn = document.getElementById('compareBtn');
    selectedRidesForCompare = [];
    document.querySelectorAll('.select-month-btn').forEach(btn => {
        if(compareMode) btn.classList.remove('hidden');
        else btn.classList.add('hidden');
    });
    document.querySelectorAll('.ride-card').forEach(c => c.classList.remove('selected'));
    document.getElementById('startAnalysisBtn').classList.add('hidden');
    
    if(compareMode) {
        btn.classList.replace('btn-secondary', 'btn-primary');
        btn.textContent = 'Cancel Compare';
        document.querySelector('.home-title p').textContent = 'Seleziona 2 o più allenamenti per il confronto...';
    } else {
        btn.classList.replace('btn-primary', 'btn-secondary');
        btn.textContent = 'Compare Rides (VS)';
        document.querySelector('.home-title p').textContent = 'Select a ride to view your performance data';
    }
}

function addChatBubble(role, content) {
    const container = document.getElementById('chatHistory');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;
    
    if(role === 'ai') {
        bubble.innerHTML = marked.parse(content);
    } else {
        bubble.textContent = content;
    }
    
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

async function runAICompare() {
    const apiKey = localStorage.getItem('gemini_api_key');
    if(!apiKey) {
        alert('Please configure your Gemini API Key in Settings first.');
        return;
    }

    document.getElementById('startAnalysisBtn').classList.add('hidden');
    document.getElementById('aiModal').classList.remove('hidden');
    document.getElementById('aiLoading').classList.remove('hidden');
    
    document.getElementById('chatHistory').innerHTML = '';
    chatHistory = [];
    
    document.getElementById('chatInput').disabled = true;
    document.getElementById('sendChatBtn').disabled = true;
    
    try {
        const response = await fetch('/api/compare', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                rides: selectedRidesForCompare,
                api_key: apiKey
            })
        });
        const data = await response.json();
        
        document.getElementById('aiLoading').classList.add('hidden');
        if(data.error) {
            addChatBubble('ai', `**Error:** ${data.error}`);
        } else {
            chatHistory.push({role: 'user', content: data.prompt});
            chatHistory.push({role: 'assistant', content: data.analysis});
            addChatBubble('ai', data.analysis);
            
            document.getElementById('chatInput').disabled = false;
            document.getElementById('sendChatBtn').disabled = false;
            document.getElementById('chatInput').focus();
        }
    } catch (e) {
        document.getElementById('aiLoading').classList.add('hidden');
        addChatBubble('ai', `**Error:** Failed to connect to AI.`);
    }
    
    toggleCompareMode();
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if(!text) return;
    
    input.value = '';
    input.disabled = true;
    document.getElementById('sendChatBtn').disabled = true;
    
    addChatBubble('user', text);
    chatHistory.push({role: 'user', content: text});
    
    const apiKey = localStorage.getItem('gemini_api_key');
    if(!apiKey) return;

    document.getElementById('aiLoading').classList.remove('hidden');
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ history: chatHistory, api_key: apiKey })
        });
        const data = await response.json();
        
        document.getElementById('aiLoading').classList.add('hidden');
        
        if(data.error) {
            addChatBubble('ai', `**Error:** ${data.error}`);
        } else {
            addChatBubble('ai', data.reply);
            chatHistory.push({role: 'assistant', content: data.reply});
        }
    } catch (e) {
        document.getElementById('aiLoading').classList.add('hidden');
        addChatBubble('ai', `**Error:** Failed to connect to AI.`);
    }
    
    input.disabled = false;
    document.getElementById('sendChatBtn').disabled = false;
    input.focus();
}

function showHome() {
    document.getElementById('rideView').classList.add('hidden');
    document.getElementById('homeView').classList.remove('hidden');
}

function showRideView() {
    document.getElementById('homeView').classList.add('hidden');
    document.getElementById('rideView').classList.remove('hidden');
}

function formatMonth(folderStr) {
    if(folderStr === 'unknown') return 'Unknown Date';
    const [year, month] = folderStr.split('-');
    const date = new Date(parseInt(year), parseInt(month) - 1);
    return date.toLocaleString('en-US', { month: 'long', year: 'numeric' });
}

// Settings Logic
function openSettingsModal() {
    const key = localStorage.getItem('gemini_api_key') || '';
    document.getElementById('apiKeyInput').value = key;
    document.getElementById('settingsFeedback').classList.add('hidden');
    document.getElementById('settingsModal').classList.remove('hidden');
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.add('hidden');
}

function saveApiKey() {
    const key = document.getElementById('apiKeyInput').value.trim();
    if(key) {
        localStorage.setItem('gemini_api_key', key);
    } else {
        localStorage.removeItem('gemini_api_key');
    }
    
    document.getElementById('settingsFeedback').classList.remove('hidden');
    setTimeout(() => {
        closeSettingsModal();
    }, 1000);
}

// Notes Logic
async function viewNotes() {
    document.getElementById('notesModal').classList.remove('hidden');
    document.getElementById('notesLoading').classList.remove('hidden');
    document.getElementById('notesText').innerHTML = '';
    
    try {
        const response = await fetch('/api/notes');
        const data = await response.json();
        document.getElementById('notesLoading').classList.add('hidden');
        if (data.notes) {
            document.getElementById('notesText').innerHTML = marked.parse(data.notes);
        } else {
            document.getElementById('notesText').textContent = 'Errore nel caricamento degli appunti.';
        }
    } catch(e) {
        document.getElementById('notesLoading').classList.add('hidden');
        document.getElementById('notesText').textContent = 'Errore di connessione.';
    }
}

async function saveNotes() {
    const apiKey = localStorage.getItem('gemini_api_key');
    if(!apiKey) {
        alert('Configura prima la tua API Key nelle impostazioni.');
        return;
    }
    
    if(chatHistory.length === 0) {
        alert('Non c\'è ancora nessuna conversazione da riassumere!');
        return;
    }
    
    const btn = document.getElementById('saveNotesBtn');
    const originalText = btn.textContent;
    btn.textContent = '⏳ Salvataggio...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/api/notes/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ history: chatHistory, api_key: apiKey })
        });
        const data = await response.json();
        
        if (data.success) {
            btn.textContent = '✅ Salvato!';
        } else {
            alert('Errore: ' + data.error);
            btn.textContent = originalText;
            btn.disabled = false;
        }
    } catch(e) {
        alert('Errore di connessione.');
        btn.textContent = originalText;
        btn.disabled = false;
    }
    
    setTimeout(() => {
        if(btn.textContent === '✅ Salvato!') {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }, 3000);
}

async function loadRideList() {
    try {
        const response = await fetch('/api/rides');
        const rides = await response.json();
        
        const container = document.getElementById('monthsContainer');
        container.innerHTML = '';
        
        if(rides.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary)">No rides found. Upload a .FIT file to get started!</p>';
            return;
        }

        // Group by month
        const groups = {};
        rides.forEach(ride => {
            const parts = ride.split('/');
            const month = parts.length > 1 ? parts[0] : 'unknown';
            if(!groups[month]) groups[month] = [];
            groups[month].push(ride);
        });

        // Sort months descending
        const sortedMonths = Object.keys(groups).sort((a,b) => b.localeCompare(a));

        function updateStartAnalysisButton() {
            const startBtn = document.getElementById('startAnalysisBtn');
            if(selectedRidesForCompare.length >= 2) {
                startBtn.textContent = `🚀 Start Analysis (${selectedRidesForCompare.length} selected)`;
                startBtn.classList.remove('hidden');
            } else {
                startBtn.classList.add('hidden');
            }
        }

        sortedMonths.forEach(month => {
            const section = document.createElement('div');
            section.className = 'month-section';
            
            const header = document.createElement('div');
            header.style.display = 'flex';
            header.style.justifyContent = 'flex-start';
            header.style.alignItems = 'center';
            header.style.gap = '1rem';
            header.style.marginBottom = '1rem';
            
            const title = document.createElement('h2');
            title.textContent = formatMonth(month);
            title.style.margin = '0';
            header.appendChild(title);
            
            const selectMonthBtn = document.createElement('button');
            selectMonthBtn.className = 'btn btn-secondary btn-small select-month-btn';
            
            const allSelected = groups[month].every(ride => selectedRidesForCompare.includes(ride));
            selectMonthBtn.textContent = allSelected ? 'Deselect All' : 'Select All';
            
            if(!compareMode) selectMonthBtn.classList.add('hidden');
            
            selectMonthBtn.onclick = () => {
                const cards = section.querySelectorAll('.ride-card');
                const isAllSelected = groups[month].every(ride => selectedRidesForCompare.includes(ride));
                
                if (isAllSelected) {
                    // Deselect all
                    groups[month].forEach(ride => {
                        selectedRidesForCompare = selectedRidesForCompare.filter(r => r !== ride);
                    });
                    cards.forEach(c => c.classList.remove('selected'));
                    selectMonthBtn.textContent = 'Select All';
                } else {
                    // Select all
                    groups[month].forEach(ride => {
                        if(!selectedRidesForCompare.includes(ride)) {
                            selectedRidesForCompare.push(ride);
                        }
                    });
                    cards.forEach(c => c.classList.add('selected'));
                    selectMonthBtn.textContent = 'Deselect All';
                }
                updateStartAnalysisButton();
            };
            
            header.appendChild(selectMonthBtn);
            section.appendChild(header);
            
            const grid = document.createElement('div');
            grid.className = 'ride-grid';
            
            // Sort rides in month descending
            groups[month].sort((a,b) => b.localeCompare(a)).forEach(ride => {
                const card = document.createElement('div');
                card.className = 'ride-card';
                if(selectedRidesForCompare.includes(ride)) card.classList.add('selected');
                
                const filename = ride.split('/').pop().replace('.csv', '');
                
                card.innerHTML = `
                    <h3>${filename}</h3>
                    <p>Click to view details &rarr;</p>
                `;
                
                card.onclick = () => {
                    if(compareMode) {
                        if(selectedRidesForCompare.includes(ride)) {
                            selectedRidesForCompare = selectedRidesForCompare.filter(r => r !== ride);
                            card.classList.remove('selected');
                        } else {
                            selectedRidesForCompare.push(ride);
                            card.classList.add('selected');
                        }
                        updateStartAnalysisButton();
                    } else {
                        loadRideDetails(ride);
                    }
                };
                
                grid.appendChild(card);
            });
            
            section.appendChild(grid);
            container.appendChild(section);
        });
        
    } catch (e) {
        console.error('Error loading ride list', e);
    }
}

async function loadRideDetails(filename) {
    showRideView();
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('dashboardData').classList.add('hidden');
    document.getElementById('rideTitle').textContent = filename.split('/').pop().replace('.csv', '');

    try {
        const response = await fetch(`/api/rides/${filename}`);
        const data = await response.json();
        
        if(data.error) {
            alert(data.error);
            return;
        }

        processAndRender(data);
        
        document.getElementById('loading').classList.add('hidden');
        document.getElementById('dashboardData').classList.remove('hidden');
        
        // Force Leaflet to recalculate its size now that the container is visible
        setTimeout(() => {
            map.invalidateSize();
            if(pathLayer) {
                map.fitBounds(pathLayer.getBounds());
            }
        }, 100);
        
    } catch (e) {
        console.error('Error loading ride details', e);
        document.getElementById('loading').classList.add('hidden');
    }
}

function processAndRender(data) {
    if(!data || data.length === 0) return;

    // Filter valid data points
    const validData = data.filter(d => d.timestamp);
    if(validData.length === 0) return;

    // --- Statistics ---
    // Distance (assuming meters) -> km
    let distances = validData.map(d => d.distance).filter(d => typeof d === 'number');
    let maxDistance = distances.length > 0 ? Math.max(...distances) : 0;
    document.getElementById('statDistance').textContent = (maxDistance / 1000).toFixed(2) + ' km';

    // Time
    const startTime = new Date(validData[0].timestamp);
    const endTime = new Date(validData[validData.length-1].timestamp);
    const diffMs = endTime - startTime;
    const diffHrs = Math.floor(diffMs / 3600000);
    const diffMins = Math.floor((diffMs % 3600000) / 60000);
    const diffSecs = Math.floor((diffMs % 60000) / 1000);
    document.getElementById('statTime').textContent = 
        `${diffHrs.toString().padStart(2,'0')}:${diffMins.toString().padStart(2,'0')}:${diffSecs.toString().padStart(2,'0')}`;

    // Speed (assuming m/s) -> km/h
    let speeds = validData.map(d => (d.enhanced_speed || d.speed || 0) * 3.6).filter(s => s > 0);
    let avgSpeed = speeds.length > 0 ? speeds.reduce((a,b)=>a+b,0)/speeds.length : 0;
    document.getElementById('statSpeed').textContent = avgSpeed.toFixed(1) + ' km/h';

    // Heart Rate
    let hrs = validData.map(d => d.heart_rate).filter(h => typeof h === 'number' && h > 0);
    let avgHr = hrs.length > 0 ? Math.round(hrs.reduce((a,b)=>a+b,0)/hrs.length) : '--';
    document.getElementById('statHR').textContent = avgHr + ' bpm';

    // Cadence
    let cadences = validData.map(d => d.cadence).filter(c => typeof c === 'number' && c > 0);
    let avgCadence = cadences.length > 0 ? Math.round(cadences.reduce((a,b)=>a+b,0)/cadences.length) : '--';
    document.getElementById('statCadence').textContent = avgCadence + ' rpm';

    // --- Map ---
    let coordinates = [];
    validData.forEach(d => {
        if(typeof d.lat === 'number' && typeof d.lng === 'number') {
            coordinates.push([d.lat, d.lng]);
        }
    });

    if(pathLayer) map.removeLayer(pathLayer);
    
    if(coordinates.length > 0) {
        pathLayer = L.polyline(coordinates, {color: '#f97316', weight: 4, opacity: 0.8}).addTo(map);
        map.fitBounds(pathLayer.getBounds());
    }

    // --- Charts ---
    const labels = validData.map(d => d.timestamp);
    
    // Elevation
    charts.elevation.data.labels = labels;
    charts.elevation.data.datasets[0].data = validData.map(d => d.enhanced_altitude || d.altitude || null);
    charts.elevation.update();

    // Speed
    charts.speed.data.labels = labels;
    charts.speed.data.datasets[0].data = validData.map(d => ((d.enhanced_speed || d.speed || 0) * 3.6));
    charts.speed.update();

    // Heart Rate
    charts.hr.data.labels = labels;
    charts.hr.data.datasets[0].data = validData.map(d => d.heart_rate || null);
    charts.hr.update();

    // Cadence
    charts.cadence.data.labels = labels;
    charts.cadence.data.datasets[0].data = validData.map(d => d.cadence || null);
    charts.cadence.update();
}

function setupUpload() {
    const uploadInput = document.getElementById('fitUpload');
    uploadInput.addEventListener('change', async (e) => {
        const files = e.target.files;
        if(files.length === 0) return;

        const formData = new FormData();
        for(let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        document.getElementById('rideTitle').textContent = `Uploading ${files.length} file(s)...`;
        document.getElementById('loading').classList.remove('hidden');

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            
            if(result.success) {
                if(result.errors && result.errors.length > 0) {
                    alert('Uploaded with some errors: ' + result.errors.join(', '));
                }
                await loadRideList(); // Reload list
            } else {
                alert('Upload failed: ' + result.error);
            }
        } catch(err) {
            console.error('Upload error', err);
            alert('Upload failed');
        } finally {
            document.getElementById('loading').classList.add('hidden');
            uploadInput.value = ''; // reset
        }
    });
}
