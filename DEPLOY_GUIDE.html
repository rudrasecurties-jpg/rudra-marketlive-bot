<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bot Deploy Guide</title>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0f1e;
    --card: #111827;
    --border: #1e2d45;
    --accent: #00d4aa;
    --accent2: #3b82f6;
    --warn: #f59e0b;
    --danger: #ef4444;
    --text: #e2e8f0;
    --muted: #64748b;
    --done: #10b981;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Sora', sans-serif;
    min-height: 100vh;
    padding: 0 0 80px;
  }

  /* ── Header ── */
  .hero {
    background: linear-gradient(135deg, #0a0f1e 0%, #0d1f3c 50%, #0a1628 100%);
    border-bottom: 1px solid var(--border);
    padding: 48px 24px 40px;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(0,212,170,0.08) 0%, transparent 70%);
  }
  .hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(0,212,170,0.1);
    border: 1px solid rgba(0,212,170,0.3);
    border-radius: 100px;
    padding: 4px 14px;
    font-size: 12px;
    color: var(--accent);
    letter-spacing: 1px;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 20px;
  }
  .hero h1 {
    font-size: clamp(28px, 5vw, 48px);
    font-weight: 800;
    line-height: 1.15;
    margin-bottom: 12px;
    background: linear-gradient(135deg, #fff 30%, var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .hero p {
    color: var(--muted);
    font-size: 16px;
    max-width: 480px;
    margin: 0 auto;
    line-height: 1.6;
  }
  .time-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 24px;
    background: rgba(59,130,246,0.1);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    color: var(--accent2);
  }

  /* ── Container ── */
  .container { max-width: 760px; margin: 0 auto; padding: 0 20px; }

  /* ── Progress bar ── */
  .progress-wrap {
    position: sticky;
    top: 0;
    z-index: 100;
    background: rgba(10,15,30,0.95);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 14px 24px;
  }
  .progress-inner { max-width: 760px; margin: 0 auto; }
  .progress-label {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 8px;
  }
  .progress-bar {
    height: 4px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 4px;
    transition: width 0.4s ease;
    width: 0%;
  }

  /* ── Step cards ── */
  .section-title {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin: 48px 0 20px;
  }

  .step-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    margin-bottom: 16px;
    overflow: hidden;
    transition: border-color 0.3s, transform 0.2s;
    cursor: pointer;
  }
  .step-card:hover { border-color: rgba(0,212,170,0.3); }
  .step-card.done {
    border-color: rgba(16,185,129,0.4);
    background: #0d1f1a;
  }
  .step-card.active { border-color: var(--accent); }

  .step-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 24px;
  }
  .step-num {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 16px;
    flex-shrink: 0;
    background: var(--border);
    color: var(--muted);
    transition: all 0.3s;
  }
  .step-card.done .step-num {
    background: var(--done);
    color: #fff;
    font-size: 18px;
  }
  .step-card.active .step-num {
    background: var(--accent);
    color: #000;
  }
  .step-info { flex: 1; }
  .step-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 2px;
  }
  .step-sub {
    font-size: 13px;
    color: var(--muted);
  }
  .step-arrow {
    color: var(--muted);
    transition: transform 0.3s;
    font-size: 18px;
  }
  .step-card.open .step-arrow { transform: rotate(90deg); }

  .step-body {
    display: none;
    padding: 0 24px 24px;
  }
  .step-card.open .step-body { display: block; }

  /* ── Content elements ── */
  .instruction {
    font-size: 15px;
    line-height: 1.7;
    color: #c7d2e2;
    margin-bottom: 16px;
  }

  .sub-step {
    display: flex;
    gap: 14px;
    margin-bottom: 14px;
    align-items: flex-start;
  }
  .sub-num {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: rgba(59,130,246,0.15);
    border: 1px solid rgba(59,130,246,0.3);
    color: var(--accent2);
    font-size: 12px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
  }
  .sub-text { font-size: 14px; line-height: 1.6; color: #c7d2e2; }
  .sub-text b { color: var(--text); }

  .code-block {
    background: #050a14;
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 10px;
    padding: 16px 18px;
    margin: 12px 0;
    position: relative;
    overflow-x: auto;
  }
  .code-block code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #a8d8c8;
    line-height: 1.8;
    white-space: pre;
    display: block;
  }
  .copy-btn {
    position: absolute;
    top: 10px;
    right: 10px;
    background: rgba(0,212,170,0.1);
    border: 1px solid rgba(0,212,170,0.2);
    color: var(--accent);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    cursor: pointer;
    font-family: 'Sora', sans-serif;
    transition: all 0.2s;
  }
  .copy-btn:hover { background: rgba(0,212,170,0.2); }

  .warn-box {
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.2);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 13px;
    color: #fbbf24;
    margin: 12px 0;
    display: flex;
    gap: 10px;
    align-items: flex-start;
    line-height: 1.6;
  }
  .info-box {
    background: rgba(59,130,246,0.08);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 13px;
    color: #93c5fd;
    margin: 12px 0;
    display: flex;
    gap: 10px;
    align-items: flex-start;
    line-height: 1.6;
  }
  .success-box {
    background: rgba(16,185,129,0.08);
    border: 1px solid rgba(16,185,129,0.2);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 13px;
    color: #6ee7b7;
    margin: 12px 0;
    display: flex;
    gap: 10px;
    align-items: flex-start;
    line-height: 1.6;
  }

  .link-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, rgba(0,212,170,0.15), rgba(59,130,246,0.15));
    border: 1px solid rgba(0,212,170,0.3);
    color: var(--accent);
    padding: 10px 20px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s;
    margin: 8px 8px 0 0;
  }
  .link-btn:hover {
    background: linear-gradient(135deg, rgba(0,212,170,0.25), rgba(59,130,246,0.25));
    transform: translateY(-1px);
  }

  /* ── Done button ── */
  .done-btn {
    width: 100%;
    margin-top: 20px;
    padding: 12px;
    background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(0,212,170,0.15));
    border: 1px solid rgba(16,185,129,0.3);
    border-radius: 10px;
    color: var(--done);
    font-family: 'Sora', sans-serif;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }
  .done-btn:hover { background: rgba(16,185,129,0.2); }
  .step-card.done .done-btn {
    background: rgba(16,185,129,0.2);
    border-color: var(--done);
    cursor: default;
  }

  /* ── Final card ── */
  .final-card {
    background: linear-gradient(135deg, rgba(0,212,170,0.08), rgba(59,130,246,0.08));
    border: 1px solid rgba(0,212,170,0.3);
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    margin-top: 32px;
  }
  .final-card h2 { font-size: 24px; margin-bottom: 8px; }
  .final-card p { color: var(--muted); font-size: 14px; line-height: 1.6; }

  img { max-width: 100%; border-radius: 8px; margin: 8px 0; }

  @media (max-width: 480px) {
    .step-header { padding: 16px; }
    .step-body { padding: 0 16px 20px; }
  }
</style>
</head>
<body>

<!-- Hero -->
<div class="hero">
  <div class="hero-badge">🚀 Deploy Guide</div>
  <h1>Indian Market Bot<br>Railway par Deploy karo</h1>
  <p>Step-by-step guide — bilkul simple, koi technical knowledge zaruri nahi</p>
  <div class="time-badge">⏱ Total time: ~15 minutes</div>
</div>

<!-- Progress -->
<div class="progress-wrap">
  <div class="progress-inner">
    <div class="progress-label">
      <span id="prog-label">0 / 5 complete</span>
      <span id="prog-pct">0%</span>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="prog-fill"></div></div>
  </div>
</div>

<!-- Steps -->
<div class="container">

  <div class="section-title">Setup Steps</div>

  <!-- ═══ STEP 1: BotFather ══════════════════════════════════════════════════ -->
  <div class="step-card" id="step-1">
    <div class="step-header" onclick="toggleStep(1)">
      <div class="step-num" id="num-1">1</div>
      <div class="step-info">
        <div class="step-title">Telegram Bot Token Banao</div>
        <div class="step-sub">BotFather se free token milega — 2 min</div>
      </div>
      <div class="step-arrow">›</div>
    </div>
    <div class="step-body">
      <div class="sub-step">
        <div class="sub-num">1</div>
        <div class="sub-text">Telegram open karo aur search karo <b>@BotFather</b></div>
      </div>
      <div class="sub-step">
        <div class="sub-num">2</div>
        <div class="sub-text">BotFather ko yeh message bhejo:</div>
      </div>
      <div class="code-block">
        <code>/newbot</code>
        <button class="copy-btn" onclick="copyCode(this, '/newbot')">Copy</button>
      </div>
      <div class="sub-step">
        <div class="sub-num">3</div>
        <div class="sub-text">Bot ka naam type karo (kuch bhi, jaise: <b>India Market Signals</b>)</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">4</div>
        <div class="sub-text">Username type karo — ek aisa naam jo unique ho aur <b>_bot</b> se khatam ho.<br>Example: <b>mymarket2024_bot</b></div>
      </div>
      <div class="sub-step">
        <div class="sub-num">5</div>
        <div class="sub-text">BotFather ek <b>Token</b> dega — yeh aisa dikhega:</div>
      </div>
      <div class="code-block">
        <code>1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ-example</code>
      </div>
      <div class="warn-box">⚠️ <span>Is token ko <b>kahin note kar lo</b> — Step 4 mein zarurat padegi. Kisi ke saath share mat karna.</span></div>
      <button class="done-btn" onclick="markDone(1)">✓ Token mil gaya — Step 1 Done!</button>
    </div>
  </div>

  <!-- ═══ STEP 2: GitHub ═════════════════════════════════════════════════════ -->
  <div class="step-card" id="step-2">
    <div class="step-header" onclick="toggleStep(2)">
      <div class="step-num" id="num-2">2</div>
      <div class="step-info">
        <div class="step-title">GitHub par Code Upload karo</div>
        <div class="step-sub">Free account + files upload — 5 min</div>
      </div>
      <div class="step-arrow">›</div>
    </div>
    <div class="step-body">
      <div class="info-box">ℹ️ <span>GitHub ek free website hai jahan code store hota hai. Railway isko padh ke bot chalayega.</span></div>

      <div class="sub-step">
        <div class="sub-num">1</div>
        <div class="sub-text"><b>github.com</b> par jaao aur free account banao (email se)</div>
      </div>
      <a href="https://github.com/signup" target="_blank" class="link-btn">🔗 GitHub Signup</a>

      <div class="sub-step" style="margin-top:16px">
        <div class="sub-num">2</div>
        <div class="sub-text">Login ke baad top-right mein <b>"+"</b> icon → <b>"New repository"</b> click karo</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">3</div>
        <div class="sub-text">Repository name likho: <b>market-bot</b> — baaki sab default rehne do → <b>Create repository</b></div>
      </div>
      <div class="sub-step">
        <div class="sub-num">4</div>
        <div class="sub-text">Ab <b>"uploading an existing file"</b> link par click karo</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">5</div>
        <div class="sub-text">Jo files maine banai hain (bot.py, requirements.txt, Procfile, runtime.txt) — inhe drag & drop karo. <b>.env.example</b> bhi upload karo lekin <b>.env nahi!</b></div>
      </div>
      <div class="sub-step">
        <div class="sub-num">6</div>
        <div class="sub-text">Neeche <b>"Commit changes"</b> button click karo</div>
      </div>
      <div class="success-box">✅ <span>Ab aapka GitHub repository ready hai!</span></div>
      <button class="done-btn" onclick="markDone(2)">✓ Files upload ho gayi — Step 2 Done!</button>
    </div>
  </div>

  <!-- ═══ STEP 3: Railway ════════════════════════════════════════════════════ -->
  <div class="step-card" id="step-3">
    <div class="step-header" onclick="toggleStep(3)">
      <div class="step-num" id="num-3">3</div>
      <div class="step-info">
        <div class="step-title">Railway.app par Deploy karo</div>
        <div class="step-sub">Free hosting — 5 min — Credit card nahi chahiye</div>
      </div>
      <div class="step-arrow">›</div>
    </div>
    <div class="step-body">
      <div class="info-box">ℹ️ <span>Railway ek free server hai jo aapka bot 24/7 chalayega. GitHub se directly connect hota hai.</span></div>

      <div class="sub-step">
        <div class="sub-num">1</div>
        <div class="sub-text"><b>railway.app</b> par jaao → <b>"Start a New Project"</b></div>
      </div>
      <a href="https://railway.app" target="_blank" class="link-btn">🔗 Railway.app</a>

      <div class="sub-step" style="margin-top:16px">
        <div class="sub-num">2</div>
        <div class="sub-text"><b>"Login with GitHub"</b> se login karo — same GitHub account jo abhi banaya</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">3</div>
        <div class="sub-text"><b>"New Project" → "Deploy from GitHub repo"</b> click karo</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">4</div>
        <div class="sub-text">List mein <b>market-bot</b> repository select karo → <b>"Deploy Now"</b></div>
      </div>
      <div class="sub-step">
        <div class="sub-num">5</div>
        <div class="sub-text">Railway deploy shuru karega — abhi <b>fail hoga</b> kyunki BOT_TOKEN set nahi hai. Yeh normal hai, Step 4 mein fix karenge.</div>
      </div>
      <div class="warn-box">⚠️ <span>Deploy fail hona normal hai is step mein. Step 4 mein token set karte hi automatically restart hoga.</span></div>
      <button class="done-btn" onclick="markDone(3)">✓ Railway project ban gaya — Step 3 Done!</button>
    </div>
  </div>

  <!-- ═══ STEP 4: Environment Variables ════════════════════════════════════ -->
  <div class="step-card" id="step-4">
    <div class="step-header" onclick="toggleStep(4)">
      <div class="step-num" id="num-4">4</div>
      <div class="step-info">
        <div class="step-title">Bot Token Railway mein set karo</div>
        <div class="step-sub">Secret settings add karna — 2 min</div>
      </div>
      <div class="step-arrow">›</div>
    </div>
    <div class="step-body">
      <div class="sub-step">
        <div class="sub-num">1</div>
        <div class="sub-text">Railway dashboard mein apna project click karo</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">2</div>
        <div class="sub-text">Upar <b>"Variables"</b> tab click karo</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">3</div>
        <div class="sub-text"><b>"New Variable"</b> click karo aur yeh add karo:</div>
      </div>

      <div class="code-block">
        <code>Variable Name:  BOT_TOKEN
Variable Value: (Step 1 mein jo token mila tha)</code>
      </div>

      <div class="sub-step">
        <div class="sub-num">4</div>
        <div class="sub-text"><b>Save</b> karo — Railway automatically bot restart karega</div>
      </div>

      <div class="sub-step">
        <div class="sub-num">5</div>
        <div class="sub-text"><b>(Optional)</b> Agar channel mein signals bhejne hain to yeh bhi add karo:</div>
      </div>
      <div class="code-block">
        <code>CHANNEL_ID = @apna_channel_username
ADMIN_ID   = apna_telegram_user_id</code>
        <button class="copy-btn" onclick="copyCode(this, 'CHANNEL_ID')">Copy</button>
      </div>
      <div class="info-box">ℹ️ <span>Apna Telegram User ID jaanno ke liye <b>@userinfobot</b> ko Telegram par message karo — woh batayega.</span></div>
      <div class="success-box">✅ <span>Save karne ke baad 1-2 minute wait karo — bot automatically start ho jayega!</span></div>
      <button class="done-btn" onclick="markDone(4)">✓ Token set kar diya — Step 4 Done!</button>
    </div>
  </div>

  <!-- ═══ STEP 5: Test ══════════════════════════════════════════════════════ -->
  <div class="step-card" id="step-5">
    <div class="step-header" onclick="toggleStep(5)">
      <div class="step-num" id="num-5">5</div>
      <div class="step-info">
        <div class="step-title">Bot Test karo</div>
        <div class="step-sub">Verify karo ki sab kaam kar raha hai — 1 min</div>
      </div>
      <div class="step-arrow">›</div>
    </div>
    <div class="step-body">
      <div class="sub-step">
        <div class="sub-num">1</div>
        <div class="sub-text">Railway dashboard mein <b>"Deployments"</b> tab dekho — green ✅ hona chahiye</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">2</div>
        <div class="sub-text">Telegram mein apna bot open karo (Step 1 mein jo username diya tha)</div>
      </div>
      <div class="sub-step">
        <div class="sub-num">3</div>
        <div class="sub-text">Yeh commands bhejo:</div>
      </div>
      <div class="code-block">
        <code>/start
/signal
/status</code>
        <button class="copy-btn" onclick="copyCode(this, '/start\n/signal\n/status')">Copy</button>
      </div>
      <div class="sub-step">
        <div class="sub-num">4</div>
        <div class="sub-text">Bot reply kare to 🎉 sab ready hai!</div>
      </div>

      <div class="warn-box">⚠️ <span><b>Bot reply nahi kar raha?</b><br>Railway → Deployments → Latest deployment → <b>View Logs</b> check karo. Error wahan dikhega.</span></div>

      <div class="success-box">✅ <span><b>Bot chal raha hai!</b> Ab automatic signals milenge — subscribe ke liye /subscribe likho bot mein.</span></div>
      <button class="done-btn" onclick="markDone(5)">🎉 Bot Live Hai! Step 5 Done!</button>
    </div>
  </div>

  <!-- ═══ Final ══════════════════════════════════════════════════════════════ -->
  <div class="final-card" id="final-card" style="display:none">
    <div style="font-size:56px;margin-bottom:16px">🎉</div>
    <h2 style="background:linear-gradient(135deg,#00d4aa,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent">
      Bot Successfully Deploy Ho Gaya!
    </h2>
    <p style="margin-top:12px">
      Aapka Indian Market Signal Bot Railway par live hai.<br>
      Ab yeh 24/7 chalta rahega — bina kisi maintenance ke.
    </p>
    <div style="margin-top:24px;padding:16px;background:rgba(0,0,0,0.3);border-radius:12px;text-align:left">
      <div style="font-size:13px;color:#64748b;margin-bottom:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase">Available Commands</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;line-height:2;color:#a8d8c8">
        /start       — Bot shuru karo<br>
        /signal      — Live market signals<br>
        /subscribe   — Hourly auto signals ON<br>
        /unsubscribe — Auto signals OFF<br>
        /status      — Market status
      </div>
    </div>
  </div>

</div>

<script>
  const TOTAL = 5;
  const done = new Set();

  // Auto-open step 1
  window.addEventListener('load', () => {
    document.getElementById('step-1').classList.add('open');
  });

  function toggleStep(n) {
    const card = document.getElementById(`step-${n}`);
    const isOpen = card.classList.contains('open');
    // Close all
    document.querySelectorAll('.step-card').forEach(c => c.classList.remove('open'));
    if (!isOpen) card.classList.add('open');
  }

  function markDone(n) {
    done.add(n);
    const card = document.getElementById(`step-${n}`);
    const num  = document.getElementById(`num-${n}`);
    card.classList.add('done');
    card.classList.remove('open', 'active');
    num.textContent = '✓';

    updateProgress();

    // Auto open next step
    if (n < TOTAL) {
      setTimeout(() => {
        const next = document.getElementById(`step-${n+1}`);
        next.classList.add('open', 'active');
        next.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 400);
    } else {
      setTimeout(() => {
        document.getElementById('final-card').style.display = 'block';
        document.getElementById('final-card').scrollIntoView({ behavior: 'smooth' });
      }, 400);
    }
  }

  function updateProgress() {
    const pct = Math.round((done.size / TOTAL) * 100);
    document.getElementById('prog-fill').style.width = pct + '%';
    document.getElementById('prog-pct').textContent = pct + '%';
    document.getElementById('prog-label').textContent = `${done.size} / ${TOTAL} complete`;
  }

  function copyCode(btn, text) {
    // Get actual code from code block
    const codeEl = btn.closest('.code-block').querySelector('code');
    const textToCopy = codeEl ? codeEl.textContent.trim() : text;
    navigator.clipboard.writeText(textToCopy).then(() => {
      btn.textContent = 'Copied!';
      setTimeout(() => btn.textContent = 'Copy', 1800);
    });
  }
</script>
</body>
</html>
