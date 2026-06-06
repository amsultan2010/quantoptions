/* ============================================================
   QuantOptionsPy — script.js
   Canvas animation · Slider sync · API calls · Chart rendering
   ============================================================ */

/* ── Canvas: Monte Carlo paths + drifting Greek symbols ────── */
(function () {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx    = canvas.getContext('2d');

  const PURPLE_RGB = '139,92,246';
  const PALE_RGB   = '196,181,253';
  const GREEKS     = ['Δ', 'Γ', 'Θ', 'ν', 'ρ', 'σ'];
  const N_PATHS    = 18;
  const N_GLYPHS   = 11;
  const STEPS      = 220;

  let W, H, paths = [], glyphs = [];

  function makePath() {
    const ys  = new Float32Array(STEPS);
    let   y   = Math.random() * H;
    const amp = H * 0.012;
    for (let i = 0; i < STEPS; i++) {
      y       += (Math.random() - 0.5) * amp * 2.8;
      ys[i]   = y;
    }
    return {
      ys,
      vy:    (Math.random() - 0.5) * 0.14,
      alpha: 0.028 + Math.random() * 0.062,
      pale:  Math.random() > 0.58,
      lw:    0.45 + Math.random() * 0.75,
    };
  }

  function makeGlyph() {
    return {
      sym:   GREEKS[Math.floor(Math.random() * GREEKS.length)],
      x:     Math.random() * W,
      y:     Math.random() * H,
      vx:    (Math.random() - 0.5) * 0.22,
      vy:    (Math.random() - 0.5) * 0.22,
      size:  15 + Math.random() * 20,
      alpha: 0.032 + Math.random() * 0.052,
    };
  }

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    paths  = Array.from({ length: N_PATHS  }, makePath);
    glyphs = Array.from({ length: N_GLYPHS }, makeGlyph);
  }

  function tick() {
    ctx.clearRect(0, 0, W, H);
    const xStep = W / (STEPS - 1);

    /* MC paths drifting vertically */
    for (const p of paths) {
      for (let i = 0; i < STEPS; i++) p.ys[i] += p.vy;

      /* wrap when midpoint wanders off screen */
      const mid = p.ys[STEPS >> 1];
      if (mid < -H * 0.25 || mid > H * 1.25) {
        const np = makePath();
        p.ys    = np.ys;
        p.vy    = np.vy;
        p.alpha = np.alpha;
        p.pale  = np.pale;
        p.lw    = np.lw;
      }

      ctx.beginPath();
      ctx.moveTo(0, p.ys[0]);
      for (let i = 1; i < STEPS; i++) ctx.lineTo(i * xStep, p.ys[i]);
      ctx.strokeStyle = `rgba(${p.pale ? PALE_RGB : PURPLE_RGB},${p.alpha})`;
      ctx.lineWidth   = p.lw;
      ctx.stroke();
    }

    /* Greek symbols floating */
    for (const g of glyphs) {
      g.x += g.vx;
      g.y += g.vy;
      if (g.x < -55) g.x = W + 35;
      else if (g.x > W + 55) g.x = -35;
      if (g.y < -55) g.y = H + 35;
      else if (g.y > H + 55) g.y = -35;

      ctx.font      = `300 italic ${g.size}px 'Space Grotesk', Georgia, serif`;
      ctx.fillStyle = `rgba(167,139,250,${g.alpha})`;
      ctx.fillText(g.sym, g.x, g.y);
    }

    requestAnimationFrame(tick);
  }

  resize();
  window.addEventListener('resize', resize);
  tick();
})();

/* ── Scroll-reveal ─────────────────────────────────────────── */
const observer = new IntersectionObserver(
  entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('is-visible'); }),
  { threshold: 0.12 }
);
document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));

/* ── Slider ────────────────────────────────────────────────── */
const simSlider  = document.getElementById('inp-sims');
const simDisplay = document.getElementById('sim-display');

function updateSlider() {
  const val = parseInt(simSlider.value);
  simDisplay.textContent = val.toLocaleString();
}
simSlider.addEventListener('input', updateSlider);
updateSlider();

/* ── Option type toggle ────────────────────────────────────── */
let optType = 'call';
function setType(t) {
  optType = t;
  document.getElementById('btn-call').classList.toggle('active', t === 'call');
  document.getElementById('btn-put').classList.toggle('active', t === 'put');
}

/* ── Helpers ───────────────────────────────────────────────── */
function params() {
  return {
    S:               parseFloat(document.getElementById('inp-S').value),
    K:               parseFloat(document.getElementById('inp-K').value),
    T:               parseFloat(document.getElementById('inp-T').value),
    r:               parseFloat(document.getElementById('inp-r').value),
    sigma:           parseFloat(document.getElementById('inp-sigma').value),
    barrier:         parseFloat(document.getElementById('inp-barrier').value),
    num_simulations: parseInt(simSlider.value),
    option_type:     optType,
  };
}

function showError(msg) {
  document.getElementById('error-message').textContent = msg;
  document.getElementById('error-banner').classList.remove('hidden');
}
function clearError() {
  document.getElementById('error-banner').classList.add('hidden');
}

function showLoading(text, sub) {
  document.getElementById('loading-text').textContent = text || 'Running pricing engine…';
  document.getElementById('loading-sub').textContent  = sub  || '';
  document.getElementById('loading-overlay').classList.remove('hidden');
}
function hideLoading() {
  document.getElementById('loading-overlay').classList.add('hidden');
}

function fmtPrice(v) { return '$' + v.toFixed(2); }
function fmtGreek(v) { return v.toFixed(4); }

const PLOTLY_CFG = { responsive: true, displayModeBar: false };

/* ── Badge builder ─────────────────────────────────────────── */
function buildBadges(p) {
  const container = document.getElementById('param-badges');
  const items = [
    `S=$${p.S}`, `K=$${p.K}`, `T=${p.T}yr`,
    `σ=${(p.sigma * 100).toFixed(0)}%`, `r=${(p.r * 100).toFixed(1)}%`,
    `n=${p.num_simulations.toLocaleString()}`, p.option_type.toUpperCase()
  ];
  container.innerHTML = items.map(t =>
    `<span class="param-badge">${t}</span>`
  ).join('');
}

/* ── Main pricing ──────────────────────────────────────────── */
async function runPricing() {
  clearError();
  const p = params();
  if ([p.S, p.K, p.T, p.r, p.sigma, p.barrier, p.num_simulations].some(v => isNaN(v))) {
    showError('Please fill in all fields with valid numbers.'); return;
  }

  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.innerHTML = `
    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:spin 0.7s linear infinite">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
    </svg>
    Pricing…`;
  showLoading(
    'Running pricing engine…',
    `Black-Scholes + Monte Carlo (${p.num_simulations.toLocaleString()} paths)`
  );

  try {
    const res  = await fetch('/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(p),
    });
    const data = await res.json();

    if (!res.ok) { showError(data.error || 'Calculation failed.'); return; }

    /* Show results */
    document.getElementById('empty-state').classList.add('hidden');
    const rc = document.getElementById('results-content');
    rc.classList.remove('hidden');
    void rc.offsetWidth; // reflow for scroll-reveal

    /* Re-observe newly visible fade-up elements */
    rc.querySelectorAll('.fade-up').forEach(el => observer.observe(el));

    /* Update subtitle + badges */
    document.getElementById('results-title').textContent = 'Pricing Results';
    document.getElementById('results-subtitle').textContent =
      `${p.option_type === 'call' ? 'Call' : 'Put'} option · S=$${p.S} · K=$${p.K} · T=${p.T}yr · σ=${(p.sigma*100).toFixed(0)}%`;
    buildBadges(p);

    /* Prices */
    function setPriceShimmer(id, text) {
      const el = document.getElementById(id);
      el.textContent = text;
      el.classList.remove('price-shimmer');
      void el.offsetWidth; // force reflow to restart animation
      el.classList.add('price-shimmer');
      el.addEventListener('animationend', () => el.classList.remove('price-shimmer'), { once: true });
    }
    setPriceShimmer('bs-price', fmtPrice(data.bs_price));
    setPriceShimmer('mc-price', fmtPrice(data.mc_price));

    /* Greeks */
    function setGreek(id, val) {
      const el = document.getElementById(id);
      el.textContent = fmtGreek(val);
      el.classList.toggle('neg', val < 0);
    }
    const g = data.greeks;
    setGreek('g-delta', g.delta);
    setGreek('g-gamma', g.gamma);
    setGreek('g-theta', g.theta);
    setGreek('g-vega',  g.vega);
    setGreek('g-rho',   g.rho);

    /* Exotics */
    const e = data.exotics;
    document.getElementById('ex-vanbs').textContent   = fmtPrice(e.vanilla_bs);
    document.getElementById('ex-vanmc').textContent   = fmtPrice(e.vanilla_mc);
    document.getElementById('ex-asian').textContent   = fmtPrice(e.asian);
    document.getElementById('ex-barrier').textContent = fmtPrice(e.barrier);
    document.getElementById('ex-lookback').textContent = fmtPrice(e.lookback);

    /* Charts */
    Plotly.newPlot('chart-paths',   data.charts.paths.data,   data.charts.paths.layout,   PLOTLY_CFG);
    Plotly.newPlot('chart-vega',    data.charts.vega.data,    data.charts.vega.layout,    PLOTLY_CFG);
    Plotly.newPlot('chart-heatmap', data.charts.heatmap.data, data.charts.heatmap.layout, PLOTLY_CFG);

    /* Reset convergence area */
    document.getElementById('conv-placeholder').classList.remove('hidden');
    document.getElementById('chart-conv').classList.add('hidden');

    document.getElementById('conv-btn').disabled = false;

  } catch (err) {
    showError('Network error — is the server running?');
    console.error(err);
  } finally {
    hideLoading();
    btn.disabled = false;
    btn.innerHTML = `
      <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polygon points="5 3 19 12 5 21 5 3"></polygon>
      </svg>
      Price Options`;
  }
}

/* ── Convergence ───────────────────────────────────────────── */
async function runConvergence() {
  clearError();
  const p = params();

  const btn = document.getElementById('conv-btn');
  btn.disabled = true;
  btn.innerHTML = `
    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 0.7s linear infinite">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
    </svg>
    Computing…`;
  showLoading(
    'Running convergence analysis…',
    'Simulating across increasing path counts'
  );

  try {
    const res  = await fetch('/api/convergence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(p),
    });
    const data = await res.json();

    if (!res.ok) { showError(data.error || 'Convergence analysis failed.'); return; }

    document.getElementById('conv-placeholder').classList.add('hidden');
    const chartEl = document.getElementById('chart-conv');
    chartEl.classList.remove('hidden');
    Plotly.newPlot('chart-conv', data.chart.data, data.chart.layout, PLOTLY_CFG);

  } catch (err) {
    showError('Network error during convergence analysis.');
    console.error(err);
  } finally {
    hideLoading();
    btn.disabled = false;
    btn.innerHTML = `
      <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="1 4 1 10 7 10"></polyline>
        <path d="M3.51 15a9 9 0 1 0 .49-4.5"></path>
      </svg>
      Run Convergence Analysis`;
  }
}

/* ── Enter key submits ─────────────────────────────────────── */
document.querySelectorAll('input[type="number"]').forEach(el => {
  el.addEventListener('keydown', e => { if (e.key === 'Enter') runPricing(); });
});

/* ── Inline spin keyframe for loading buttons ──────────────── */
const style = document.createElement('style');
style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
document.head.appendChild(style);
