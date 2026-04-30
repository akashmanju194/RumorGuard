
    // --- GLOBAL CONFIG & STATE ---
    const API_BASE = "http://127.0.0.1:8000";
    let currentUser = localStorage.getItem('currentUser') || null;
    let currentAnalysisId = null;
    let authMode = 'login'; // 'login' or 'register'

    // --- INITIALIZATION ---
    function init() {
      renderNavAuth();
    }

    function renderNavAuth() {
      const section = document.getElementById('authSection');
      if (currentUser) {
        section.innerHTML = `
          <span class="user-greeting">@${currentUser}</span>
          <button class="btn-outline" onclick="logout()">Sign Out</button>
        `;
      } else {
        section.innerHTML = `
          <button class="btn-outline" onclick="openAuthModal('login')">Sign In</button>
          <button class="btn-primary" onclick="openAuthModal('register')">Sign Up</button>
        `;
      }
    }

    // --- UI HELPERS ---
    function fillExample(el) {
      document.getElementById('claim-input').value = el.textContent;
      document.getElementById('claim-input').focus();
    }
    function scrollToHero() { window.scrollTo({ top: 0, behavior: 'smooth' }); }
    function closeAllModals() {
      document.getElementById('authModal').style.display = 'none';
      document.getElementById('shareModal').style.display = 'none';
      document.getElementById('recentChecksModal').style.display = 'none';
      document.getElementById('modalOverlay').style.display = 'none';
    }

    // --- AUTHENTICATION ---
    function openAuthModal(mode) {
      authMode = mode;
      document.getElementById('authUsername').value = '';
      document.getElementById('authPassword').value = '';
      document.getElementById('authError').style.display = 'none';
      
      updateAuthUI();
      
      document.getElementById('authModal').style.display = 'block';
      document.getElementById('modalOverlay').style.display = 'block';
    }

    function closeAuthModal() {
      document.getElementById('authModal').style.display = 'none';
      document.getElementById('modalOverlay').style.display = 'none';
    }

    function toggleAuthMode(e) {
      e.preventDefault();
      authMode = authMode === 'login' ? 'register' : 'login';
      updateAuthUI();
    }

    function updateAuthUI() {
      const isLogin = authMode === 'login';
      document.getElementById('authModalTitle').textContent = isLogin ? 'Sign In' : 'Sign Up';
      document.getElementById('authSubmitBtn').textContent = isLogin ? 'Sign In' : 'Create Account';
      document.getElementById('authSwitchText').textContent = isLogin ? "Don't have an account?" : "Already have an account?";
      document.getElementById('authSwitchLink').textContent = isLogin ? "Sign Up" : "Sign In";
    }

    async function handleAuth(e) {
      e.preventDefault();
      const username = document.getElementById('authUsername').value.trim();
      const password = document.getElementById('authPassword').value;
      const errorEl = document.getElementById('authError');
      const btn = document.getElementById('authSubmitBtn');
      
      errorEl.style.display = 'none';
      btn.disabled = true;
      btn.textContent = 'Processing...';

      const endpoint = authMode === 'login' ? '/login' : '/register';
      
      try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password })
        });

        const data = await res.json();
        
        if (!res.ok) {
          throw new Error(data.detail || data.error || 'Authentication failed');
        }

        // Success
        currentUser = username;
        localStorage.setItem('currentUser', username);
        renderNavAuth();
        closeAuthModal();
        
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.style.display = 'block';
      } finally {
        btn.disabled = false;
        updateAuthUI();
      }
    }

    function logout() {
      currentUser = null;
      localStorage.removeItem('currentUser');
      renderNavAuth();
    }

    // --- CLAIM ANALYSIS ---
    async function checkClaim() {
      const input = document.getElementById('claim-input');
      const claim = input.value.trim();

      if (!claim) {
        input.style.border = "1px solid var(--red)";
        setTimeout(() => input.style.border = "1px solid var(--border)", 1500);
        return;
      }

      const btn = document.getElementById('checkBtn');
      const spinner = document.getElementById('spinner');
      const btnText = document.getElementById('btnText');

      btn.disabled = true;
      spinner.style.display = 'inline-block';
      btnText.textContent = 'Analyzing...';
      
      // Close previous result card if visible
      document.getElementById('resultCard').style.display = 'none';

      try {
        const payload = { 
          text: claim, 
          url: "",
          username: currentUser || "GuestUser"
        };
        
        const response = await fetch(`${API_BASE}/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("API connection error");

        const data = await response.json();
        if (data.error) {
          alert("Error: " + data.error);
          return;
        }

        parseAndShowResult(data);

      } catch (e) {
        console.error(e);
        alert("Failed to connect to backend. Is uvicorn running?");
      } finally {
        btn.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = 'Initiate Scan';
      }
    }

    function parseAndShowResult(data) {
      const aiLines = data.ai_analysis.split('\n');
      let label = "Uncertain";
      let desc = "Analysis complete.";
      let confidence = 50;

      for (let line of aiLines) {
        if (line.startsWith("Verdict:")) label = line.replace("Verdict:", "").trim();
        if (line.startsWith("Reason:")) desc = line.replace("Reason:", "").trim();
        if (line.startsWith("Confidence:")) {
          const confStr = line.replace("Confidence:", "").trim();
          confidence = parseInt(confStr.replace('%', '') || "50");
        }
      }

      currentAnalysisId = data.id;

      const card = document.getElementById('resultCard');
      card.style.display = 'block';
      card.scrollIntoView({ behavior: 'smooth' });

      // Reset themes
      card.classList.remove('theme-true', 'theme-false', 'theme-uncertain');
      
      let themeClass = 'theme-uncertain';
      let title = "Verdict is uncertain";
      let signals = ["? Mixed or missing context", "⚖️ Requires human review"];
      
      const lblLower = label.toLowerCase();
      if (lblLower.includes("false")) {
        themeClass = 'theme-false';
        title = "This claim appears false";
        signals = ["⚠️ High emotional language", "❌ Matches misinformation markers"];
      } else if (lblLower.includes("true")) {
        themeClass = 'theme-true';
        title = "This claim appears credible";
        signals = ["✓ Factual syntax detected", "📝 Rational sentiment"];
      }

      card.classList.add(themeClass);

      // Animate gauge
      const gaugeFill = document.getElementById('gaugeFill');
      const offset = 300 - (data.score / 100) * 300;
      // Timeout to ensure CSS animation triggers
      setTimeout(() => { gaugeFill.style.strokeDashoffset = offset; }, 50);

      document.getElementById('gaugeNumber').textContent = Math.round(data.score);
      document.getElementById('verdictLabel').textContent = label.toUpperCase();
      document.getElementById('verdictTitle').textContent = title;
      document.getElementById('verdictDesc').textContent = desc;
      document.getElementById('confValue').textContent = confidence + "%";
      
      setTimeout(() => { document.getElementById('confBar').style.width = confidence + "%"; }, 50);

      document.getElementById('reasonTags').innerHTML = signals.map(s => `<div class="reason-tag">${s}</div>`).join('');
    }

    function checkAnother() {
      document.getElementById('resultCard').style.display = 'none';
      document.getElementById('claim-input').value = '';
      document.getElementById('claim-input').focus();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // --- SHARING ---
    function openShareModal() {
      if (!currentAnalysisId) {
        alert("Cannot share: Analysis ID not found.");
        return;
      }
      const shareUrl = `${API_BASE}/api/share/${currentAnalysisId}`;
      document.getElementById('shareLinkInput').value = shareUrl;
      document.getElementById('shareStatus').textContent = "";
      document.getElementById('copyShareBtn').textContent = "Copy";
      
      document.getElementById('shareModal').style.display = 'block';
      document.getElementById('modalOverlay').style.display = 'block';
    }

    function closeShareModal() {
      document.getElementById('shareModal').style.display = 'none';
      document.getElementById('modalOverlay').style.display = 'none';
    }

    function copyShareLink() {
      const input = document.getElementById('shareLinkInput');
      input.select();
      document.execCommand("copy");
      document.getElementById('copyShareBtn').textContent = "Copied!";
      document.getElementById('shareStatus').textContent = "Link copied to clipboard!";
    }

    // --- RECENT CHECKS ---
    async function openRecentChecks(e) {
      if(e) e.preventDefault();
      
      const userToFetch = currentUser || "GuestUser";
      const modal = document.getElementById('recentChecksModal');
      const overlay = document.getElementById('modalOverlay');
      const listContainer = document.getElementById('recentChecksList');

      modal.style.display = 'block';
      overlay.style.display = 'block';

      listContainer.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 2rem;"><div class="spinner" style="display:inline-block;"></div> Loading...</td></tr>`;

      try {
        const res = await fetch(`${API_BASE}/history/${userToFetch}?limit=10`);
        if (!res.ok) throw new Error("Failed to fetch");
        
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          listContainer.innerHTML = `<tr><td colspan='4' style='text-align:center; color:var(--text-muted); padding: 2rem;'>No history found for ${userToFetch}.</td></tr>`;
          return;
        }

        listContainer.innerHTML = data.items.map(check => {
          const date = new Date(check.created_at).toLocaleDateString();
          const text = check.text.length > 50 ? check.text.substring(0, 50) + '...' : check.text;
          const score = Math.round(check.score);
          const lbl = check.label.toUpperCase();
          
          let color = "var(--yellow)";
          if (lbl.includes("TRUE")) color = "var(--green)";
          if (lbl.includes("FALSE")) color = "var(--red)";

          return `
            <tr>
              <td style="color:var(--text-muted); font-size:0.85rem;">${date}</td>
              <td>${text}</td>
              <td style="font-family:'JetBrains Mono', monospace; font-weight:bold;">${score}</td>
              <td><span style="color:${color}; font-size:0.8rem; font-weight:bold; border:1px solid ${color}; padding: 4px 8px; border-radius:4px;">${lbl}</span></td>
            </tr>
          `;
        }).join('');
      } catch(err) {
        listContainer.innerHTML = `<tr><td colspan='4' style='text-align:center; color:var(--red); padding: 2rem;'>Error loading history.</td></tr>`;
      }
    }

    function closeRecentChecks() {
      document.getElementById('recentChecksModal').style.display = 'none';
      document.getElementById('modalOverlay').style.display = 'none';
    }

    // --- EVENTS ---
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeAllModals();
    });

    document.getElementById('claim-input').addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') checkClaim();
    });

    // Run init
    init();
  