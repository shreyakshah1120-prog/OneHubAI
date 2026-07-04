(function () {
  const root = document.getElementById('healthApp');
  if (!root) return;

  const urls = {
    language: root.dataset.urlLanguage,
    profile: root.dataset.urlProfile,
    part: root.dataset.urlPart,
    start: root.dataset.urlStart,
    message: root.dataset.urlMessage,
    report: root.dataset.urlReportTemplate,
    del: root.dataset.urlDeleteTemplate,
    pdf: root.dataset.urlPdfTemplate,
  };

  const i18n = {
    en: {
      kicker: 'Medical AI Assistant',
      title: 'Health',
      subtitle: 'Explore your body, describe symptoms naturally, and get careful triage guidance. This is not a diagnosis.',
      language: 'Language',
      greeting: 'Greeting',
      bmi: 'BMI',
      previousReports: 'Previous Reports',
      selectedBodyPart: 'Selected Body Part',
      healthScore: 'Health Score',
      profileTitle: 'Health Profile',
      profileSubtitle: 'Personal metrics help make triage context-aware.',
      age: 'Age',
      gender: 'Gender',
      female: 'Female',
      male: 'Male',
      other: 'Other',
      height: 'Height (cm)',
      weight: 'Weight (kg)',
      conditions: 'Medical Conditions (optional)',
      allergies: 'Allergies (optional)',
      healthyWeight: 'Healthy Weight',
      water: 'Daily Water',
      calories: 'Daily Calories',
      anatomyTitle: 'Human Anatomy',
      anatomySubtitle: "Tap a label and let Dr. AI tell what's the problem.",
      external: 'External',
      internal: 'Internal',
      selected: 'Selected',
      reportProblem: 'Report a problem with this',
      selectBodyPrompt: 'Choose a body part to see concise organ information.',
      consultTitle: 'Doctor Consultation',
      consultSubtitle: 'One question at a time, based on your answers.',
      consultEmpty: 'Select a body part and start a consultation.',
      uploadReport: 'Upload report',
      send: 'Send',
      finish: 'Generate report',
      aiReport: 'AI Report',
      reportSubtitle: 'Structured triage summary rendered as cards.',
      history: 'History',
      historySubtitle: 'Open, delete, or download previous consultations.',
      open: 'Open',
      downloadPdf: 'Download PDF',
      delete: 'Delete',
      emptyHistory: 'Your health reports will appear here.',
      chooseLanguage: 'Choose Language',
      chooseLanguageSub: 'This will translate the Health module and AI responses.',
      noPart: 'No body part selected',
      describe: 'Describe your problem...',
      loading: 'Thinking carefully...',
      saved: 'Saved',
      deleted: 'Deleted',
      uploadAttached: 'Report attached',
    },
    hi: {
      kicker: 'मेडिकल AI असिस्टेंट',
      title: 'स्वास्थ्य',
      subtitle: 'शरीर को समझें, लक्षण स्वाभाविक रूप से बताएं, और सावधानीपूर्वक ट्रायाज मार्गदर्शन पाएं। यह निदान नहीं है।',
      language: 'भाषा',
      greeting: 'अभिवादन',
      bmi: 'BMI',
      previousReports: 'पिछली रिपोर्ट',
      selectedBodyPart: 'चुना हुआ अंग',
      healthScore: 'हेल्थ स्कोर',
      profileTitle: 'स्वास्थ्य प्रोफाइल',
      profileSubtitle: 'व्यक्तिगत जानकारी ट्रायाज को संदर्भ देती है।',
      age: 'उम्र',
      gender: 'लिंग',
      female: 'महिला',
      male: 'पुरुष',
      other: 'अन्य',
      height: 'ऊंचाई (सेमी)',
      weight: 'वजन (किग्रा)',
      conditions: 'मेडिकल कंडीशन (वैकल्पिक)',
      allergies: 'एलर्जी (वैकल्पिक)',
      healthyWeight: 'स्वस्थ वजन',
      water: 'दैनिक पानी',
      calories: 'दैनिक कैलोरी',
      anatomyTitle: 'मानव शरीर रचना',
      anatomySubtitle: 'व्यू बदलें, फिर शरीर का भाग चुनें।',
      external: 'बाहरी',
      internal: 'आंतरिक',
      selected: 'चयनित',
      reportProblem: 'इसमें समस्या बताएं',
      selectBodyPrompt: 'संक्षिप्त जानकारी के लिए शरीर का भाग चुनें।',
      consultTitle: 'डॉक्टर परामर्श',
      consultSubtitle: 'आपके जवाबों के आधार पर एक-एक सवाल।',
      consultEmpty: 'शरीर का भाग चुनें और परामर्श शुरू करें।',
      uploadReport: 'रिपोर्ट अपलोड करें',
      send: 'भेजें',
      finish: 'रिपोर्ट बनाएं',
      aiReport: 'AI रिपोर्ट',
      reportSubtitle: 'कार्ड के रूप में संरचित ट्रायाज सारांश।',
      history: 'इतिहास',
      historySubtitle: 'पुराने परामर्श खोलें, हटाएं या PDF डाउनलोड करें।',
      open: 'खोलें',
      downloadPdf: 'PDF डाउनलोड',
      delete: 'हटाएं',
      emptyHistory: 'आपकी स्वास्थ्य रिपोर्ट यहां दिखेगी।',
      chooseLanguage: 'भाषा चुनें',
      chooseLanguageSub: 'यह Health मॉड्यूल और AI जवाबों का अनुवाद करेगा।',
      noPart: 'कोई अंग चयनित नहीं',
      describe: 'अपनी समस्या बताएं...',
      loading: 'ध्यान से सोच रहा है...',
      saved: 'सेव हो गया',
      deleted: 'हटा दिया गया',
      uploadAttached: 'रिपोर्ट जुड़ गई',
    },
    gu: {
      kicker: 'મેડિકલ AI સહાયક',
      title: 'આરોગ્ય',
      subtitle: 'શરીર સમજો, લક્ષણો સહજ રીતે લખો, અને સાવચેત ટ્રાયાજ માર્ગદર્શન મેળવો. આ નિદાન નથી.',
      language: 'ભાષા',
      greeting: 'અભિવાદન',
      bmi: 'BMI',
      previousReports: 'જૂની રિપોર્ટ્સ',
      selectedBodyPart: 'પસંદ કરેલો ભાગ',
      healthScore: 'હેલ્થ સ્કોર',
      profileTitle: 'આરોગ્ય પ્રોફાઇલ',
      profileSubtitle: 'વ્યક્તિગત માહિતી ટ્રાયાજને સંદર્ભ આપે છે.',
      age: 'ઉંમર',
      gender: 'લિંગ',
      female: 'સ્ત્રી',
      male: 'પુરુષ',
      other: 'અન્ય',
      height: 'ઊંચાઈ (સેમી)',
      weight: 'વજન (કિગ્રા)',
      conditions: 'મેડિકલ કન્ડિશન (વૈકલ્પિક)',
      allergies: 'એલર્જી (વૈકલ્પિક)',
      healthyWeight: 'સ્વસ્થ વજન',
      water: 'દૈનિક પાણી',
      calories: 'દૈનિક કેલરી',
      anatomyTitle: 'માનવ શરીર રચના',
      anatomySubtitle: 'વ્યુ બદલો, પછી શરીરનો ભાગ પસંદ કરો.',
      external: 'બાહ્ય',
      internal: 'આંતરિક',
      selected: 'પસંદ કરેલું',
      reportProblem: 'આમાં સમસ્યા જણાવો',
      selectBodyPrompt: 'સંક્ષિપ્ત માહિતી માટે શરીરનો ભાગ પસંદ કરો.',
      consultTitle: 'ડોક્ટર કન્સલ્ટેશન',
      consultSubtitle: 'તમારા જવાબો પ્રમાણે એક સમયે એક પ્રશ્ન.',
      consultEmpty: 'શરીરનો ભાગ પસંદ કરો અને કન્સલ્ટેશન શરૂ કરો.',
      uploadReport: 'રિપોર્ટ અપલોડ',
      send: 'મોકલો',
      finish: 'રિપોર્ટ બનાવો',
      aiReport: 'AI રિપોર્ટ',
      reportSubtitle: 'કાર્ડ તરીકે ગોઠવાયેલ ટ્રાયાજ સારાંશ.',
      history: 'ઇતિહાસ',
      historySubtitle: 'જૂના કન્સલ્ટેશન ખોલો, કાઢી નાખો અથવા PDF ડાઉનલોડ કરો.',
      open: 'ખોલો',
      downloadPdf: 'PDF ડાઉનલોડ',
      delete: 'કાઢી નાખો',
      emptyHistory: 'તમારી આરોગ્ય રિપોર્ટ અહીં દેખાશે.',
      chooseLanguage: 'ભાષા પસંદ કરો',
      chooseLanguageSub: 'આ Health મોડ્યુલ અને AI જવાબોને અનુવાદિત કરશે.',
      noPart: 'કોઈ ભાગ પસંદ નથી',
      describe: 'તમારી સમસ્યા લખો...',
      loading: 'ધ્યાનથી વિચારી રહ્યું છે...',
      saved: 'સાચવાયું',
      deleted: 'કાઢી નાખ્યું',
      uploadAttached: 'રિપોર્ટ જોડાયો',
    },
  };

  // bx,by = label box position (%)   ax,ay = point on the body it refers to (%)   side = which way the box hangs off its point
  // bx,by = box center position (%)   w,h = box size (px)   side = kept for reference, no longer used for lines
const hotspots = {
  external: [
    ['Forehead',  75, 9,   110, 23, 'right'],
    ['Eye',       75, 14,   46, 20, 'right'],
    ['Mouth',     75, 20,  75, 22, 'right'],
    ['Chin',      75, 25,  58, 22, 'right'],
    ['Chest',     75, 32,  70, 22, 'right'],
    ['Abdomen',   75, 43,  100, 22, 'right'],
    ['Fingers',   75, 56,  80, 22, 'right'],
    ['Heel',      74, 90,  57, 22, 'right'],
    ['Head',      25, 11,   60, 22, 'left'],
    ['Neck',      25, 19,  60, 22, 'left'],
    ['Shoulder',  25, 25,  120, 34, 'left'],
    ['Upper Arm', 25, 31,  120, 30, 'left'],
    ['Elbow',     24, 38,  80, 25, 'left'],
    ['Forearm',   24, 45,  100, 28, 'left'],
    ['Wrist',     89, 49,  80, 24, 'left'],
    ['Hand',      24, 52,  61, 23, 'left'],
    ['Thigh',     25, 63,  70, 22, 'left'],
    ['Knee',      24, 70,  60, 22, 'left'],
    ['Tiny Leg',  24, 77,  90, 22, 'left'],
    ['Ankle',     24, 83,  70, 22, 'left'],
    ['Foot',      24, 89,  60, 22, 'left'],
    ['Toes',      25, 94,  59, 18, 'left'],
  ],
  internal: [
    ['Brain',           26, 4.5,  68,  26, 'left'],
    ['Oesophagus',      25, 16, 116, 26, 'left'],
    ['Lymph Nodes',     25, 29, 129, 26, 'left'],
    ['Liver',           26, 35, 60,  26, 'left'],
    ['Kidneys',         26, 40, 80,  26, 'left'],
    ['Large Intestine', 26, 46, 140, 26, 'left'],
    ['Muscle',          26, 57, 72,  25, 'left'],
    ['Lungs',           75, 24, 60,  26, 'right'],
    ['Blood Vessels',   75, 31, 126, 26, 'right'],
    ['Stomach',         75, 36, 83,  26, 'right'],
    ['Small Intestine', 75, 45, 138, 26, 'right'],
    ['Bone',            74, 60, 60,  26, 'right'],
    ['Joint',           75, 71, 58,  26, 'right'],
  ],
};

  let lang = root.dataset.language || 'en';
  let view = 'external';
  let selectedPart = '';
  let consultationId = '';

  const $ = (id) => document.getElementById(id);
  const t = (key) => (i18n[lang] && i18n[lang][key]) || i18n.en[key] || key;
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

  function apiUrl(template, id) {
    return template.replace(/0(?=\/?$|\/)/, String(id));
  }

  function translateUI() {
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.dataset.i18n;
      if (t(key)) el.textContent = t(key);
    });
    $('consultAnswer').placeholder = t('describe');
    if (!selectedPart) $('selectedPartTitle').textContent = t('noPart');
  }

  async function saveLanguage(code) {
    const res = await postJson(urls.language, { language: code });
    if (!res.ok) throw new Error(res.error || 'Could not save language');
    lang = code;
    $('languageLabel').textContent = res.label;
    root.dataset.language = code;
    $('languageModal').hidden = true;
    translateUI();
    showToast(t('saved'), 'success');
  }

  function renderHotspots() {
  const wrap = $('anatomyHotspots');
  wrap.innerHTML = '';
  hotspots[view].forEach(([part, bx, by, w, h, side]) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'hotspot' + (part === selectedPart ? ' active' : '');
    btn.title = part;
    btn.setAttribute('aria-label', part);
    if (part === 'Wrist') btn.textContent = part.toUpperCase();   // <-- add this line
    btn.dataset.part = part;
    btn.style.setProperty('--x', `${bx}%`);
    btn.style.setProperty('--y', `${by}%`);
    btn.style.setProperty('--w', `${w}px`);
    btn.style.setProperty('--h', `${h}px`);
    btn.style.setProperty('--tx', side === 'right' ? '0%' : '-100%');
    btn.addEventListener('click', () => selectPart(part));
    wrap.appendChild(btn);
  });
  document.querySelectorAll('#quickParts button').forEach((btn) => {
    btn.hidden = btn.dataset.view !== view;
    btn.classList.toggle('active', btn.dataset.part === selectedPart);
  });
}

  function drawAnatomyLines() {
    const stage = $('anatomyStage');
    const svg = $('anatomyLines');
    if (!stage || !svg) return;
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svg.innerHTML = '';

    document.querySelectorAll('#anatomyHotspots .hotspot').forEach((btn) => {
      const ax = (parseFloat(btn.dataset.ax) / 100) * w;
      const ay = (parseFloat(btn.dataset.ay) / 100) * h;
      const rect = btn.getBoundingClientRect();
      const stageRect = stage.getBoundingClientRect();
      const isActive = btn.classList.contains('active');
      const fromRight = btn.style.getPropertyValue('--tx') === '0%';
      const lx = rect.left - stageRect.left + (fromRight ? 0 : rect.width);
      const ly = rect.top - stageRect.top + rect.height / 2;

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', lx);
      line.setAttribute('y1', ly);
      line.setAttribute('x2', ax);
      line.setAttribute('y2', ay);
      line.setAttribute('class', 'anatomy-leader-line' + (isActive ? ' active' : ''));
      svg.appendChild(line);

      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', ax);
      dot.setAttribute('cy', ay);
      dot.setAttribute('r', isActive ? 5 : 3.5);
      dot.setAttribute('class', 'anatomy-anchor-dot' + (isActive ? ' active' : ''));
      svg.appendChild(dot);
    });
  }

  // NEW
function selectPart(part) {
  selectedPart = part;
  consultationId = '';
  $('dashPart').textContent = part;
  $('selectedPartTitle').textContent = part;
  $('startConsultBtn').disabled = false;
  $('chatLog').innerHTML = `<div class="assistant-msg">${escapeHtml(t('consultEmpty'))}</div>`;
  $('consultAnswer').disabled = true;
  $('consultForm').querySelector('button[type="submit"]').disabled = true;
  $('finishNowBtn').disabled = true;
  renderHotspots();
  showToast(`Selected: ${part}`, 'success');
}

  function profilePayload() {
    return {
      age: $('hpAge').value,
      gender: $('hpGender').value,
      height: $('hpHeight').value,
      weight: $('hpWeight').value,
      conditions: $('hpConditions').value,
      allergies: $('hpAllergies').value,
    };
  }

  async function updateMetrics() {
    try {
      const res = await postJson(urls.profile, profilePayload());
      if (!res.ok) return;
      const m = res.metrics;
      $('dashBmi').textContent = m.bmi;
      $('metricWeight').textContent = m.healthy_weight;
      $('metricWater').textContent = m.water;
      $('metricCalories').textContent = m.calories;
      $('healthScore').textContent = m.bmi === '--' ? '--' : (m.category === 'Healthy range' ? 'Good' : 'Review');
    } catch (_) {}
  }

  async function startConsultation() {
    if (!selectedPart) return;
    const res = await postJson(urls.start, { organ: selectedPart, profile: profilePayload() });
    if (!res.ok) {
      showToast(res.error || 'Could not start consultation', 'error');
      return;
    }
    consultationId = res.consultation_id;
    $('chatLog').innerHTML = '';
    addMessage(res.question, 'assistant');
    $('consultAnswer').disabled = false;
    $('consultForm').querySelector('button[type="submit"]').disabled = false;
    $('finishNowBtn').disabled = false;
    $('consultAnswer').focus();
  }

  async function sendConsultMessage(forceReport) {
    if (!consultationId) return;
    const answer = $('consultAnswer').value.trim();
    const file = $('reportUpload').files[0];
    if (!answer && !file) return;
    if (answer) addMessage(answer, 'user');
    if (file) addMessage(`${t('uploadAttached')}: ${file.name}`, 'user');
    $('consultAnswer').value = '';
    addMessage(t('loading'), 'assistant', true);

    const fd = new FormData();
    fd.append('csrf_token', csrf());
    fd.append('consultation_id', consultationId);
    fd.append('answer', answer);
    fd.append('force_report', forceReport ? '1' : '0');
    if (file) fd.append('report', file);

    try {
      const res = await fetch(urls.message, { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: fd });
      const data = await res.json();
      removePending();
      $('reportUpload').value = '';
      if (!data.ok) {
        addMessage(data.error || 'Something went wrong.', 'assistant');
        return;
      }
      renderEmergency(data.emergency);
      if (data.done) {
        renderReport(data.report, data.report_id);
        addMessage(data.report.overview || 'Report generated.', 'assistant');
        consultationId = '';
        $('consultAnswer').disabled = true;
        $('consultForm').querySelector('button[type="submit"]').disabled = true;
        $('finishNowBtn').disabled = true;
      } else {
        addMessage(data.question, 'assistant');
      }
    } catch (err) {
      removePending();
      addMessage(err.message, 'assistant');
    }
  }

  function renderEmergency(emergency) {
    const banner = $('emergencyBanner');
    if (emergency && emergency.is_emergency) {
      banner.hidden = false;
      banner.textContent = emergency.message;
    } else {
      banner.hidden = true;
      banner.textContent = '';
    }
  }

  function addMessage(text, who, pending) {
    const el = document.createElement('div');
    el.className = who === 'user' ? 'user-msg' : 'assistant-msg';
    if (pending) el.dataset.pending = '1';
    el.textContent = text;
    $('chatLog').appendChild(el);
    $('chatLog').scrollTop = $('chatLog').scrollHeight;
  }

  function removePending() {
    document.querySelectorAll('[data-pending="1"]').forEach((el) => el.remove());
  }

  function renderReport(report, id) {
    const panel = $('reportPanel');
    panel.hidden = false;
    const cards = [
      ['Overview', report.overview],
      ['Possible Causes', report.possible_causes],
      ['Home Remedies', report.home_remedies],
      ['Lifestyle Advice', report.lifestyle_advice],
      ['When to See Doctor', report.when_to_see_doctor],
      ['Emergency Warning Signs', report.emergency_warning_signs],
      ['Report Cross-check', report.uploaded_report_cross_check],
      ['Urgency', report.urgency],
      ['Confidence', report.confidence],
      ['Disclaimer', report.disclaimer],
    ];
    $('reportCards').innerHTML = cards.map(([title, value]) => cardHtml(title, value, 'report-card')).join('') +
      (id ? `<a class="health-primary" href="${apiUrl(urls.pdf, id)}">${escapeHtml(t('downloadPdf'))}</a>` : '');
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function cardHtml(title, value, className) {
    const body = Array.isArray(value)
      ? `<ul>${value.map((v) => `<li>${escapeHtml(String(v))}</li>`).join('')}</ul>`
      : `<p>${escapeHtml(String(value || 'Not available'))}</p>`;
    return `<article class="${className}"><h3>${escapeHtml(title)}</h3>${body}</article>`;
  }

  async function openReport(id) {
    const res = await fetch(apiUrl(urls.report, id));
    const data = await res.json();
    if (!data.ok) return;
    renderReport(data.report, id);
  }

  async function deleteReport(id) {
    const res = await fetch(apiUrl(urls.del, id), { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
    const data = await res.json();
    if (!data.ok) return;
    document.querySelector(`[data-report-id="${id}"]`)?.remove();
    showToast(t('deleted'), 'success');
  }

  function bindEvents() {
    $('changeLanguageBtn').addEventListener('click', () => { $('languageModal').hidden = false; });
    document.querySelectorAll('.language-options button').forEach((btn) => {
      btn.addEventListener('click', () => saveLanguage(btn.dataset.language).catch((err) => showToast(err.message, 'error')));
    });
    document.querySelectorAll('.segmented button').forEach((btn) => {
      btn.addEventListener('click', () => {
        view = btn.dataset.view;
        document.querySelectorAll('.segmented button').forEach((b) => b.classList.toggle('active', b === btn));
        $('anatomyBgExternal').hidden = view !== 'external';
        $('anatomyBgInternal').hidden = view !== 'internal';
        renderHotspots();
      });
    });
    window.addEventListener('resize', drawAnatomyLines);
    document.querySelectorAll('#quickParts button').forEach((btn) => btn.addEventListener('click', () => selectPart(btn.dataset.part)));
    ['hpAge', 'hpGender', 'hpHeight', 'hpWeight', 'hpConditions', 'hpAllergies'].forEach((id) => $(id).addEventListener('input', updateMetrics));
    $('startConsultBtn').addEventListener('click', startConsultation);
    $('consultForm').addEventListener('submit', (ev) => {
      ev.preventDefault();
      sendConsultMessage(false);
    });
    $('finishNowBtn').addEventListener('click', () => sendConsultMessage(true));
    $('historyList').addEventListener('click', (ev) => {
      const actionEl = ev.target.closest('[data-action]');
      if (!actionEl) return;
      const id = actionEl.dataset.id;
      if (actionEl.dataset.action === 'open') openReport(id);
      if (actionEl.dataset.action === 'delete') deleteReport(id);
    });
  }

  translateUI();
  bindEvents();
  renderHotspots();
  updateMetrics();
  if (root.dataset.languageMissing === '1') $('languageModal').hidden = false;
})();
