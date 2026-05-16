const API_BASE_URL = "https://hyperdev5-nexus-api.hf.space";

/* ====================================
   Module Chips Logic (Navigation)
======================================*/
const chips = document.querySelectorAll('.chip');
const moduleMsg = document.getElementById('moduleMsg');
const searchInput = document.getElementById('searchInput');
let msgTimeout;

chips.forEach(chip => {
    chip.addEventListener('click', (e) => {
        // Remove active class from all
        chips.forEach(c => c.classList.remove('active'));
        // Add active to clicked
        e.target.classList.add('active');

        const moduleName = e.target.dataset.module;

        if (moduleName === 'movies') {
            // Normal mode
            moduleMsg.classList.add('hidden');
            searchInput.placeholder = "Enter target movie (e.g., Kalki)...";
            searchInput.disabled = false;
        } else {
            // Future modules mode
            clearTimeout(msgTimeout);
            moduleMsg.classList.remove('hidden');
            moduleMsg.innerHTML = `🚀 <b>${e.target.innerText}</b> engine is currently under construction.`;

            // Auto-hide the message after 4 seconds to keep UI clean
            msgTimeout = setTimeout(() => {
                moduleMsg.classList.add('hidden');
                // Automatically switch back to 'movies' chip after showing message
                chips.forEach(c => c.classList.remove('active'));
                document.querySelector('[data-module="movies"]').classList.add('active');
                searchInput.placeholder = "Enter target movie (e.g., Kalki)...";
                searchInput.disabled = false;
            }, 4000);
        }
    });
});

/* ====================================
   Modal Open/Close Logic (Settings & Episodes)
======================================*/
const settingsBtn = document.getElementById('settingsBtn');
const settingsDropdown = document.getElementById('settingsDropdown');

const episodesModal = document.getElementById('episodesModal');
const closeEpisodesModal = document.getElementById('closeEpisodesModal');

// Settings Dropdown Logic
settingsBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    settingsDropdown.classList.toggle('hidden');
});

// Episodes Modal Close Logic
closeEpisodesModal.addEventListener('click', () => {
    episodesModal.classList.add('hidden');
});

// Global Click (Closes dropdowns or modals if clicked outside)
document.addEventListener('click', (event) => {
    // Close Settings
    if (!settingsDropdown.contains(event.target) && event.target !== settingsBtn) {
        settingsDropdown.classList.add('hidden');
    }
    // Close Episodes Modal
    if (event.target === episodesModal) {
        episodesModal.classList.add('hidden');
    }
});

// Search Triggers
document.getElementById('searchInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') performSearch();
});
document.getElementById('searchBtn').addEventListener('click', performSearch);


/* ====================================
     Main Search Function (Unchanged)
======================================*/
function performSearch() {
    const query = document.getElementById('searchInput').value;
    if (!query) return;

    const grid = document.getElementById('resultsGrid');
    const loading = document.getElementById('loadingText');
    const searchBtn = document.getElementById('searchBtn');

    searchBtn.disabled = true;
    grid.innerHTML = '';
    loading.style.display = 'block';

    let resultsCount = 0;

    try {
        const limit = document.getElementById('limitSlider').value;
        const checkboxes = document.querySelectorAll('.source-cb:checked');
        const selectedSources = Array.from(checkboxes).map(cb => cb.value).join(',');

        if (!selectedSources) {
            alert("Error: Please select at least one network to scan!");
            searchBtn.disabled = false;
            loading.style.display = 'none';
            return;
        }

        settingsDropdown.classList.add('hidden');

        const apiUrl = `${API_BASE_URL}/search?q=${encodeURIComponent(query)}&limit=${limit}&sources=${selectedSources}`;
        const eventSource = new EventSource(apiUrl);

        eventSource.onmessage = function (event) {
            if (event.data === '[DONE]') {
                loading.style.display = 'none';
                searchBtn.disabled = false;
                eventSource.close();

                if (resultsCount === 0) {
                    grid.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">🚫</div>
                        <h2>Target Not Found</h2>
                        <p>The specified movie could not be located in the active databases.</p>
                    </div>`;
                }
                return;
            }

            const data = JSON.parse(event.data);

            data.results.forEach(movie => {
                resultsCount++;

                const card = document.createElement('div');
                card.className = 'card';
                card.id = `card-${movie.id}`;
                card.dataset.state = "idle";
                card.dataset.source = movie.source.toLowerCase();

                card.innerHTML = `
                <div class="card-img-wrapper">
                    <div class="source-badge">${movie.source.toUpperCase()}</div>
                    <img src="${movie.image}" referrerpolicy="no-referrer" alt="Movie Poster" onerror="this.src='https://placehold.co/300x450/111827/e5e7eb?text=No+Movie+Poster'">
                </div>
                <div class="card-content">
                    <h3>${movie.title}</h3>
                    <p class="status-text" id="status-${movie.id}">Click to extract direct links</p>
                    <div class="links-container" id="links-${movie.id}"></div>
                </div>
                `;

                card.onclick = (event) => extractLinks(event, movie.url, movie.source, movie.id);
                grid.appendChild(card);
            });
        };

        eventSource.onerror = function (error) {
            console.error("SSE Connection Error:", error);
            eventSource.close();
            loading.style.display = 'none';
            searchBtn.disabled = false;

            if (resultsCount === 0) {
                grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⚠️</div>
                    <h2 style="color: #ff4d4d;">Connection Failed</h2>
                    <p>Unable to connect to the backend engine. Check terminal logs.</p>
                </div>`;
            }
        };

    } catch (error) {
        console.error("Catch Block Error:", error);
    }
}


/* ====================================
    Link Extraction Function (Updated with Sorting)
======================================*/
async function extractLinks(event, detailUrl, source, id) {
    event.stopPropagation();
    const card = document.getElementById(`card-${id}`);
    const statusText = document.getElementById(`status-${id}`);
    const linksDiv = document.getElementById(`links-${id}`);

    if(card.dataset.state === "loading" || card.dataset.state === "done") return;

    card.dataset.state = "loading";
    card.classList.add("disabled");
    statusText.innerHTML = `<div class="spinner"></div> Bypassing ${source}...`;

    try {
        const response = await fetch(`${API_BASE_URL}/extract`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: detailUrl, source: source, mode: "packs" })
        });

        const data = await response.json();

        statusText.style.display = 'none';
        linksDiv.style.display = 'block';
        linksDiv.innerHTML = '';

        if(data.links && Object.keys(data.links).length > 0) {
            card.dataset.state = "done";

            let linksArray = Object.entries(data.links);

            linksArray.sort((a, b) => {
                let keyA = a[0].toLowerCase();
                let keyB = b[0].toLowerCase();

                // 1. Quality Scoring (Higher is better)
                const getQualityScore = (str) => {
                    if (str.includes('4k') || str.includes('2160p')) return 40;
                    if (str.includes('1080p') || str.includes('1080')) return 30;
                    if (str.includes('720p') || str.includes('720')) return 20;
                    if (str.includes('480p') || str.includes('480')) return 10;
                    return 0; // Unknown quality
                };

                // 2. Server Reliability Scoring (Higher is better)
                const getServerScore = (str) => {
                    // Best Servers
                    if (str.includes('pixeldrain') || str.includes('vip direct') || str.includes('10gbps') || str.includes('gofile')) return 50;
                    // Good Servers
                    if (str.includes('drive') || str.includes('hubcloud direct')) return 40;
                    // Average (Instant Links)
                    if (str.includes('instant')) return 30;
                    // Universal default for other scrapers like 9xflix/Filmyfly
                    if (!str.includes('fallback') && !str.includes('gateway') && !str.includes('raw')) return 20;
                    // Worst/Error Servers (Fallbacks, Gateways, Raw Links)
                    return 10;
                };

                let qScoreA = getQualityScore(keyA);
                let qScoreB = getQualityScore(keyB);

                // if quality is different, sort by quality first
                if (qScoreA !== qScoreB) {
                    return qScoreB - qScoreA;
                }

                // if quality is same, then sort by server reliability
                let sScoreA = getServerScore(keyA);
                let sScoreB = getServerScore(keyB);

                return sScoreB - sScoreA;
            });

            // render sorted links to UI
            for (const [quality, finalUrl] of linksArray) {
            // Handle different formats of finalUrl (string or object with url/link/href)
            let actualLink = typeof finalUrl === 'string' ? finalUrl : (finalUrl.url || finalUrl.link || finalUrl.href || Object.values(finalUrl)[0]);

            linksDiv.innerHTML += `<a href="${actualLink}" class="dl-btn" target="_blank" onclick="event.stopPropagation()">📥 Download ${quality.toUpperCase()}</a>`;
            }

            // check if it's a series by looking for keywords in the title (season, episode, s01, s1, etc.)
            const movieTitle = document.querySelector(`#card-${id} h3`).innerText.toLowerCase();
            const isSeries = movieTitle.includes('season') || movieTitle.includes('episode') || movieTitle.match(/s\d+/);

            // If source is HDHub4u and it's a series, show "Load Episodes" button
            if (source.toLowerCase() === 'hdhub4u' && isSeries) {
                linksDiv.innerHTML += `<button class="dl-btn" style="background: #eab308; color: #000; margin-top: 10px; position: sticky; bottom: 0;" onclick="event.stopPropagation(); loadEpisodes('${detailUrl}', '${source}')">📺 Load Episodes</button>`;
            }

        } else {
            // Handle edge case where only episodes exist (No Packs available)
            const movieTitle = document.querySelector(`#card-${id} h3`).innerText.toLowerCase();
            const isSeries = movieTitle.includes('season') || movieTitle.includes('episode') || movieTitle.match(/s\d+/);

            if (source.toLowerCase() === 'hdhub4u' && isSeries) {
                card.dataset.state = "done";
                statusText.style.display = 'block';
                statusText.innerHTML = '<span style="color:#eab308;">📂 This is a Web Series</span>';
                linksDiv.innerHTML = `<button class="dl-btn" style="background: #eab308; color: #000;" onclick="event.stopPropagation(); loadEpisodes('${detailUrl}', '${source}')">📺 Load Episodes</button>`;
            } else {
                card.dataset.state = "error";
                card.classList.remove("disabled");
                statusText.style.display = 'block';
                statusText.innerHTML = '<span style="color:red;">❌ Extraction Failed. Try again.</span>';
            }
        }
    } catch(e) {
        card.dataset.state = "error";
        card.classList.remove("disabled");
        statusText.innerHTML = '<span style="color:red;">❌ Server Error.</span>';
    }
}

window.loadEpisodes = loadEpisodes;

/* ====================================
    Episode Modal Caching & Fetch Logic
======================================*/

// Global Objects to maintain state without reloading the page
const episodesCache = {}; // Saves HTML content for already fetched URLs
const activeRequests = {}; // Tracks which URLs are currently fetching

// Make it globally accessible for inline HTML onclick
window.loadEpisodes = loadEpisodes;

async function loadEpisodes(url, source) {
    const modal = document.getElementById('episodesModal');
    const container = document.getElementById('episodesContainer');
    const loader = document.getElementById('episodesLoader');

    //  Track current active modal URL (to prevent mixing data if user clicks fast)
    modal.dataset.currentUrl = url;

    // Reset UI and Open Modal
    container.innerHTML = '';
    container.classList.add('hidden');
    loader.classList.remove('hidden');
    modal.classList.remove('hidden');

    // ===============================================
    // CASE 1: Data already cached! (Instant Load)
    // ===============================================
    if (episodesCache[url]) {
        console.log(`⚡ [Cache Hit] Loading episodes instantly for: ${url}`);
        loader.classList.add('hidden');
        container.innerHTML = episodesCache[url];
        container.classList.remove('hidden');
        return;
    }

    // ===============================================
    // CASE 2: Fetch already in progress in background!
    // ===============================================
    if (activeRequests[url]) {
        console.log(`⏳ [Wait] Fetch already running in background for: ${url}`);
        return; // Don't send another API request, let the ongoing one finish and update UI
    }

    // ===============================================
    // CASE 3: First time fetching from API
    // ===============================================
    console.log(`🌐 [API Request] Fetching episodes for: ${url}`);
    activeRequests[url] = true; // Lock this URL so duplicate clicks don't spam API

    let htmlContent = '';

    try {
        const response = await fetch(`${API_BASE_URL}/extract`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, source: source, mode: "episodes" })
        });

        const data = await response.json();

        if (data.links && Object.keys(data.links).length > 0) {
            for (const [quality, finalUrl] of Object.entries(data.links)) {
                htmlContent += `<a href="${finalUrl}" class="dl-btn" style="text-align: left;" target="_blank">📺 ${quality.toUpperCase()}</a>`;
            }

            // Save successful result to cache
            episodesCache[url] = htmlContent;
        } else {
            // Don't cache empty results, maybe it was a temporary server glitch
            htmlContent = '<p style="color: #ef4444; text-align: center; margin-top: 15px;">❌ No episodes found.</p>';
        }

    } catch (error) {
        console.error("Episode Fetch Error:", error);
        htmlContent = '<p style="color: #ef4444; text-align: center; margin-top: 15px;">❌ Network/Server Error occurred.</p>';
    } finally {
        activeRequests[url] = false; // Unlock this URL

        // Check if the user is STILL looking at the same movie's modal
        if (modal.dataset.currentUrl === url) {
            loader.classList.add('hidden');
            container.innerHTML = htmlContent;
            container.classList.remove('hidden');
        }
    }
}
