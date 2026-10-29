/* ---------- Elemen, state, dan pembantu umum ---------- */

const main = document.querySelector("#main");
const live = document.querySelector("#announcement");

const state = {
  screen: "home",
  consultation: null,
  selected: [],
  unknown: false,
  tab: "rules",
  project: null,
  busy: false,
  returnTo: "home",
  pendingEdit: null,
  retryAnswers: null,
};

const LOCAL_SERVER_URL = "http://127.0.0.1:8765/";
const arrow = '<span aria-hidden="true">↗</span>';

const HTML_ESCAPES = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (character) => HTML_ESCAPES[character]);

const idNumberFormat = new Intl.NumberFormat("id-ID");
const number = (n) => idNumberFormat.format(n);

/* ---------- Akses API ---------- */

const REQUEST_TIMEOUT_MS = 45000;

function friendlyError(error) {
  if (error.name === "AbortError") {
    return new Error("Proses membutuhkan waktu lebih lama. Coba lagi sebentar.");
  }
  if (error instanceof TypeError) {
    return new Error(
      "Aplikasi belum terhubung. Pastikan server lokal masih berjalan, lalu coba lagi.",
    );
  }
  return error;
}

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Jawaban belum dapat diproses. Periksa pilihanmu dan coba lagi.",
      );
    }
    return data;
  } catch (error) {
    throw friendlyError(error);
  } finally {
    clearTimeout(timeout);
  }
}

/* ---------- Kerangka layar ---------- */

function focusMain() {
  main.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "instant" });
}

function announce(text) {
  live.textContent = text;
}

function loading(label = "Memuat konsultasi…") {
  main.setAttribute("aria-busy", "true");
  main.innerHTML = `<div class="loading" role="status">
    <div class="spinner" aria-hidden="true"></div>
    <p>${esc(label)}</p>
  </div>`;
  announce(label);
}

/* Menjalankan satu permintaan API sambil menahan klik ganda dan menampilkan status memuat. */
async function withLoadingScreen(task, label) {
  state.busy = true;
  loading(label);
  try {
    return await task();
  } finally {
    state.busy = false;
    main.removeAttribute("aria-busy");
  }
}

function showError(error, retryAction) {
  state.screen = "error";
  main.removeAttribute("aria-busy");
  main.innerHTML = `<section class="error-box" role="alert">
    <div class="eyebrow">Sebentar, ada kendala</div>
    <h1>Konsultasi belum dapat diproses.</h1>
    <p>${esc(error.message)}</p>
    <button class="button" data-action="${retryAction}">Coba lagi ${arrow}</button>
    <button class="button ghost" data-action="home">Ke beranda</button>
  </section>`;
  focusMain();
}

/* ---------- Layar beranda ---------- */

const HOME_STEPS = [
  [
    "01",
    "Isi preferensi perjalanan",
    "Jawab pertanyaan tentang preferensi perjalananmu.",
  ],
  [
    "02",
    "Lihat rekomendasi destinasi",
    "Bandingkan hasil berbasis aturan dan pengguna serupa.",
  ],
  [
    "03",
    "Periksa dasar rekomendasi",
    "Lihat aturan yang digunakan dan respons pengguna pendukung.",
  ],
];

function homeStep([stepNumber, title, copy]) {
  return `<div class="home-step"><span class="step-number">${stepNumber}</span><div><h2>${title}</h2><p>${copy}</p></div></div>`;
}

function home() {
  state.screen = "home";
  state.pendingEdit = null;
  announce("Beranda Tourguider.");
  main.innerHTML = `<section class="home wrap fade-in" aria-labelledby="hero-title">
    <div class="eyebrow">Proyek Sistem Berbasis Pengetahuan</div>
    <h1 id="hero-title" class="hero-title">Rekomendasi destinasi wisata<br>berdasarkan preferensimu.</h1>
    <p class="hero-copy">Tourguider menggunakan forward chaining dan CBR untuk merekomendasikan destinasi dari data Stravl. Isi preferensi perjalananmu untuk melihat hasil dan dasar rekomendasinya.</p>
    <div class="hero-actions">
      <button class="button" data-action="start">Mulai konsultasi ${arrow}</button>
      <button class="nav-link" data-action="about">Tentang proyek <span aria-hidden="true">↗</span></button>
    </div>
    <p class="quiet-note">Tanpa akun <span>·</span> Pertanyaan mengikuti jawabanmu <span>·</span> Gratis</p>
    <div class="home-steps">${HOME_STEPS.map(homeStep).join("")}</div>
  </section>`;
}

/* ---------- Alur konsultasi ---------- */

function resetSelection() {
  state.selected = [];
  state.unknown = false;
}

async function start() {
  if (state.busy) return;
  state.pendingEdit = null;
  state.tab = "rules";
  await withLoadingScreen(async () => {
    try {
      state.consultation = await api("/api/consultations/start", {});
      resetSelection();
      renderConsultation();
      focusMain();
    } catch (e) {
      showError(e, "start");
    }
  });
}

function answerChips(summary) {
  return summary
    .map((answer) => {
      const text = esc(answer.text);
      return `<button class="chip" data-action="edit" data-field="${esc(answer.field)}" aria-label="Ubah ${esc(answer.label)}: ${text}">${text} <span class="edit-icon" aria-hidden="true">↗</span></button>`;
    })
    .join("");
}

function answerOption(option, question) {
  const inputType = question.multiple ? "checkbox" : "radio";
  const checked = state.selected.includes(option.value) ? "checked" : "";
  return `<label class="option"><input type="${inputType}" name="answer" value="${esc(option.value)}" ${checked}><span>${esc(option.label)}</span></label>`;
}

function summaryStrip(summary) {
  if (!summary.length) return "";
  return `<div class="answer-strip">
    <p class="answer-strip-title">Jawabanmu sejauh ini · pilih untuk mengubah</p>
    <div class="chips">${answerChips(summary)}</div>
  </div>`;
}

function renderConsultation() {
  const consultation = state.consultation;
  if (consultation.complete) {
    renderResults();
    return;
  }

  state.screen = "consultation";
  const question = consultation.question;
  const questionNumber = consultation.question_number;

  main.innerHTML = `<section class="consult wrap fade-in" aria-labelledby="question-title">
    <div class="section-top">
      <span class="eyebrow">Preferensi perjalanan</span>
      <span class="step-caption">Sesuai alur jawabanmu</span>
    </div>
    <form id="question-form" class="question-card" novalidate>
      <div class="card-meta">
        <span>Pertanyaan ke-${questionNumber} · ${esc(question.label)}</span>
        <span class="ordinal">${String(questionNumber).padStart(2, "0")}</span>
      </div>
      <h1 id="question-title">${esc(question.title)}</h1>
      <p class="question-hint" id="question-hint">${esc(question.hint)}</p>
      <fieldset class="option-grid" aria-describedby="question-hint field-error">
        <legend class="sr-only">${esc(question.title)}</legend>
        ${question.options.map((option) => answerOption(option, question)).join("")}
      </fieldset>
      <label class="unknown"><input id="unknown-answer" type="checkbox" ${state.unknown ? "checked" : ""}><span>Belum tahu / belum menentukan</span></label>
      <p id="field-error" class="field-error" role="alert" hidden>Pilih jawaban atau tandai “Belum tahu” untuk melanjutkan.</p>
      <div class="form-actions">
        <button type="button" class="button ghost" data-action="back"><span aria-hidden="true">←</span> Kembali</button>
        <button type="submit" class="button">Lanjutkan ${arrow}</button>
      </div>
    </form>
    ${summaryStrip(consultation.summary)}
    <p class="consult-note">Pertanyaan menyesuaikan jawabanmu. Pilih jawaban sebelumnya untuk mengubahnya.</p>
  </section>`;

  main.querySelector("#question-form").addEventListener("submit", submitAnswer);
  announce(`Pertanyaan ${questionNumber}: ${question.title}`);
}

async function submitAnswer(event) {
  event.preventDefault();
  if (state.busy) return;

  const form = event.currentTarget;
  const chosen = [...form.querySelectorAll('[name="answer"]:checked')].map(
    (input) => input.value,
  );
  const unknown = form.querySelector("#unknown-answer").checked;

  if (!chosen.length && !unknown) {
    form.querySelector("#field-error").hidden = false;
    form.querySelector('[name="answer"]').focus();
    return;
  }

  state.selected = chosen;
  state.unknown = unknown;

  const answers = {
    ...state.consultation.answers,
    [state.consultation.question.field]: unknown ? [] : chosen,
  };
  await sendAnswers(answers);
}

async function sendAnswers(answers, label = "Memproses jawaban…") {
  if (state.busy) return false;
  return withLoadingScreen(async () => {
    try {
      state.consultation = await api("/api/consultations/answer", { answers });
      resetSelection();
      if (
        state.pendingEdit &&
        state.consultation.question?.field === state.pendingEdit.field
      ) {
        state.selected = state.pendingEdit.values;
        state.unknown = !state.selected.length;
      }
      state.pendingEdit = null;
      renderConsultation();
      focusMain();
      return true;
    } catch (e) {
      state.retryAnswers = answers;
      showError(e, "retry-answer");
      return false;
    }
  }, label);
}

/* Mengirim ulang jawaban sebelum `field` agar pertanyaan tersebut tampil kembali dengan pilihan lama. */
async function edit(field) {
  const consultation = state.consultation;
  const answersBeforeField = {};
  for (const answer of consultation.summary) {
    if (answer.field === field) break;
    answersBeforeField[answer.field] = consultation.answers[answer.field];
  }

  state.pendingEdit = {
    field,
    values: [...(consultation.answers[field] || [])],
  };
  await sendAnswers(answersBeforeField);
}

const TRACE_INTRO = {
  personalized:
    "Forward chaining: fakta jawaban memicu aturan. Kesimpulan suatu aturan menjadi premis aturan berikutnya sampai kelompok rekomendasi terbentuk.",
  popularity:
    "Alur berikut menelusuri penanda jawaban kosong. Karena belum ada preferensi yang ditentukan, kelompok akhir ini tidak dipakai untuk personalisasi; daftar hasil menggunakan popularitas data pelatihan.",
};

function traceStep(step, index) {
  return `<li class="trace"><span class="trace-label">LANGKAH ${index + 1} · ${esc(step.rule_id)}</span><p>Jika <code>${esc(step.premise)}</code> dan ${esc(step.condition.toLowerCase())}, maka <code>${esc(step.conclusion)}</code>.</p></li>`;
}

function traceBlock(trace, personalized = true) {
  const intro = personalized ? TRACE_INTRO.personalized : TRACE_INTRO.popularity;
  return `<details class="reasoning">
    <summary>Lihat proses penalaran</summary>
    <p class="reasoning-intro">${intro}</p>
    <ol class="trace-list">${trace.map(traceStep).join("")}</ol>
  </details>`;
}

/* ---------- Layar hasil ---------- */

const RESULT_TABS = [
  { id: "rules", label: "Berdasarkan aturan" },
  { id: "cbr", label: "Pengguna serupa" },
];

function tabButton(tab, activeTab) {
  const isActive = tab.id === activeTab;
  return `<button id="tab-${tab.id}" role="tab" class="tab" aria-selected="${isActive}" aria-controls="recommendation-panel" tabindex="${isActive ? 0 : -1}" data-action="tab" data-tab="${tab.id}">${tab.label}</button>`;
}

function destinationCard(destination, index) {
  const parts = destination.name.split(", ");
  const country = parts.pop();
  const place = parts.join(", ") || country;
  const fallbackTag = destination.fallback
    ? '<span class="support-tag">Alternatif populer</span>'
    : "";

  return `<li class="destination-card">
      <span class="destination-rank" aria-label="Urutan ${index + 1}">${String(index + 1).padStart(2, "0")}</span>
      <div>
        <h2 class="destination-title">${esc(place)}</h2>
        <p class="destination-country">${esc(parts.length ? country : "")}</p>
        <p class="destination-reason">${esc(destination.reason)}</p>${fallbackTag}
      </div>
      <span class="destination-icon" aria-hidden="true">↗</span>
    </li>`;
}

function caseList(cases) {
  return cases
    .map(
      (item) =>
        `<div class="case"><strong>${esc(item.case_id)} · kemiripan ${Math.round(item.similarity * 100)}%</strong><p>${esc(item.shared_preferences.join(" · "))}.</p></div>`,
    )
    .join("");
}

function resultsHeadingCopy(personalized) {
  return personalized
    ? "Hasil berdasarkan jawabanmu. Bandingkan rekomendasi berbasis aturan dan pengguna serupa."
    : "Destinasi populer dari data pelatihan untuk pengguna yang belum menentukan preferensi.";
}

function panelCopy(personalized, isRules) {
  if (!personalized) {
    return "Daftar menggunakan popularitas karena preferensi belum ditentukan.";
  }
  return isRules
    ? "Dipilih dari kelompok preferensi yang sesuai, dengan bobot yang sama untuk setiap pengguna."
    : "Dipilih dari respons pengguna serupa, dengan minimal satu respons Ya untuk setiap kecocokan.";
}

function insightCopy(results, personalized, isRules) {
  if (!personalized) {
    return {
      title: "Preferensi belum diisi",
      body: "Isi preferensi untuk mendapatkan rekomendasi berdasarkan jawabanmu.",
      stat: 0,
      label: "preferensi yang sudah ditentukan",
    };
  }
  if (isRules) {
    return {
      title: "Dasar rekomendasi",
      body: "Forward chaining menentukan kelompok preferensi dari jawabanmu. Destinasi diurutkan dengan bobot yang sama untuk setiap pengguna dalam kelompok tersebut.",
      stat: results.segment_users,
      label: "pengguna dalam kelompok preferensimu",
    };
  }
  return {
    title: "Kasus pembanding",
    body: "CBR menggunakan hingga 20 pengguna dengan preferensi serupa. Respons Ya, Mungkin, dan Tidak dari pengguna tersebut menentukan urutan rekomendasi.",
    stat: results.neighbor_count,
    label: "pengguna serupa menjadi pembanding",
  };
}

function renderResults(preserveScroll = false) {
  state.screen = "results";
  const consultation = state.consultation;
  const results = consultation.results;
  const isRules = state.tab === "rules";
  const personalized = results.personalized !== false;
  const items = results[state.tab];
  const insight = insightCopy(results, personalized, isRules);
  const notice = results.notice
    ? `<p class="result-notice" role="status">${esc(results.notice)}</p>`
    : "";
  const insightDetail = isRules
    ? "<p>Angka pendukung menunjukkan respons dalam dataset, bukan jaminan kecocokan atau kepuasan perjalanan.</p>"
    : caseList(results.similar_cases);

  main.innerHTML = `<section class="results wrap fade-in">
    <div class="eyebrow">Hasil konsultasi</div>
    <div class="results-heading">
      <h1>Rekomendasi destinasi wisata</h1>
      <p>${resultsHeadingCopy(personalized)}</p>
    </div>
    <div class="results-summary"><span>Jawaban konsultasi</span>${answerChips(consultation.summary)}</div>${notice}
    <div class="results-layout">
      <div>
        <div class="tabs" role="tablist" aria-label="Metode rekomendasi">${RESULT_TABS.map((tab) => tabButton(tab, state.tab)).join("")}</div>
        <div id="recommendation-panel" role="tabpanel" aria-labelledby="tab-${state.tab}" tabindex="0">
          <p class="tab-description">${panelCopy(personalized, isRules)}</p>
          <ol class="destination-list">${items.map(destinationCard).join("")}</ol>
        </div>
        ${traceBlock(consultation.trace, personalized)}
      </div>
      <aside class="insight-card" aria-label="Dasar rekomendasi">
        <span class="spark" aria-hidden="true">✳</span>
        <h2>${insight.title}</h2>
        <p>${insight.body}</p>
        <hr class="insight-divider">
        <div class="insight-stat">${number(insight.stat)}</div>
        <div class="insight-label">${insight.label}</div>
        ${insightDetail}
      </aside>
    </div>
    <div class="results-actions">
      <button class="button outline" data-action="edit-first">Ubah jawaban <span aria-hidden="true">↗</span></button>
      <button class="button ghost" data-action="start">Mulai ulang <span aria-hidden="true">↻</span></button>
    </div>
    <p class="disclaimer">Rekomendasi ini berdasarkan ketertarikan pengguna Stravl. Preferensi anggaran dan keamanan tidak memverifikasi biaya atau kondisi destinasi saat ini. Ketersediaan penilaian berbeda untuk setiap tempat.</p>
  </section>`;
  if (!preserveScroll) {
    announce(
      "Rekomendasi siap. Jelajahi hasil berdasarkan aturan atau pengguna serupa.",
    );
  }
}

/* ---------- Layar tentang proyek ---------- */

async function about() {
  if (state.busy) return;
  state.returnTo = state.screen === "about" ? state.returnTo : state.screen;
  await withLoadingScreen(async () => {
    try {
      state.project = await api("/api/project");
      renderAbout();
      focusMain();
    } catch (e) {
      showError(e, "about");
    }
  }, "Memuat informasi proyek…");
}

const METHOD_NAMES = {
  forward_chaining: "Forward chaining",
  cbr: "Kasus serupa (CBR)",
  popularity: "Popularitas (pembanding)",
};

const VALIDATION_METRICS = [
  ["precision_at_5", "Ketepatan", "Precision"],
  ["recall_at_5", "Cakupan", "Recall"],
  ["ndcg_at_5", "Kualitas urutan", "NDCG"],
];

const METRIC_DEFINITIONS = [
  [
    "Ketepatan · Precision",
    "Proporsi dari lima rekomendasi yang memang diberi respons “Ya” oleh pengguna uji.",
  ],
  [
    "Cakupan · Recall",
    "Proporsi seluruh destinasi yang disukai pengguna uji yang berhasil muncul dalam lima rekomendasi.",
  ],
  [
    "Kualitas urutan · NDCG",
    "Menilai penempatan destinasi yang disukai pada lima posisi teratas. Rekomendasi yang relevan di posisi awal mendapat bobot lebih besar.",
  ],
];

const ABOUT_INTRO =
  "<strong>Tourguider</strong> merupakan proyek mata kuliah <strong>Sistem Berbasis Pengetahuan</strong> yang menerapkan forward chaining dan case-based reasoning (CBR) untuk merekomendasikan destinasi wisata berdasarkan preferensi pengguna. Dataset Stravl digunakan untuk membentuk basis pengetahuan, menelusuri aturan, dan membandingkan hasil rekomendasi.";

const METHOD_TILES = [
  {
    index: "01",
    kind: "Berbasis aturan",
    title: "Forward Chaining",
    copy: "Jawaban pengguna memicu aturan secara berantai hingga terbentuk kelompok rekomendasi.",
    flowLabel: "Alur forward chaining",
    steps: ["Jawaban", "Aturan berantai", "Rekomendasi"],
  },
  {
    index: "02",
    kind: "Berbasis kasus",
    title: "Case-Based Reasoning (CBR)",
    copy: "Mencari hingga 20 pengguna dengan preferensi serupa, lalu mengurutkan destinasi dari respons mereka.",
    flowLabel: "Alur case-based reasoning",
    steps: ["Preferensi", "Kasus serupa", "Rekomendasi"],
  },
];

function statCards(audit) {
  const stats = [
    [number(audit.raw_users), "profil pengguna pada dataset awal"],
    [number(audit.destinations), "destinasi wisata dalam katalog"],
    [number(audit.rule_count), "aturan dalam basis pengetahuan"],
  ];
  const cards = stats
    .map(
      ([value, label]) =>
        `<div class="stat-card"><strong>${value}</strong><span>${label}</span></div>`,
    )
    .join("");

  return `<div class="stats">${cards}</div>`;
}

function methodTile({ index, kind, title, copy, flowLabel, steps }) {
  const flow = steps
    .map((step) => `<span>${step}</span>`)
    .join('<span aria-hidden="true">→</span>');

  return `<article class="method-tile">
      <div class="method-tile-top"><span class="method-index" aria-hidden="true">${index}</span><span class="method-kind">${kind}</span></div>
      <h3>${title}</h3>
      <p>${copy}</p>
      <div class="method-flow" aria-label="${flowLabel}">${flow}</div>
    </article>`;
}

function methodsSection() {
  return `<section class="about-card recommendation-methods">
    <h2>Metode rekomendasi</h2>
    <p class="methods-intro">Tourguider membandingkan dua pendekatan untuk mengolah preferensi wisata.</p>
    <div class="method-overview">${METHOD_TILES.map(methodTile).join("")}</div>
  </section>`;
}

function percent(value) {
  return `${(value * 100).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

function validationTable(evaluation) {
  const bestScores = {};
  for (const [metric] of VALIDATION_METRICS) {
    bestScores[metric] = Math.max(
      ...Object.values(evaluation.metrics).map((scores) => scores[metric]),
    );
  }

  const headerCells = VALIDATION_METRICS.map(
    ([, label, term]) =>
      `<th scope="col">${label}<span class="metric-term">${term}</span></th>`,
  ).join("");

  const rows = Object.entries(evaluation.metrics)
    .map(([method, scores]) => {
      const cells = VALIDATION_METRICS.map(([metric]) => {
        const isBest = scores[metric] === bestScores[metric] ? "best" : "";
        return `<td class="${isBest}">${percent(scores[metric])}</td>`;
      }).join("");
      return `<tr><th scope="row">${METHOD_NAMES[method]}</th>${cells}</tr>`;
    })
    .join("");

  return `<table class="validation-table"><caption class="sr-only">Perbandingan ketepatan, cakupan, dan kualitas urutan lima rekomendasi teratas</caption><thead><tr><th scope="col">Metode</th>${headerCells}</tr></thead><tbody>${rows}</tbody></table>`;
}

function validationFacts(evaluation) {
  if (!evaluation) {
    return "<p>Validasi untuk versi proses ini belum tersedia. Jalankan ulang audit sebelum menggunakan angka evaluasi.</p>";
  }

  const definitions = METRIC_DEFINITIONS.map(
    ([term, description]) =>
      `<div><dt>${term}</dt><dd>${description}</dd></div>`,
  ).join("");

  return `<p>Validasi dilakukan pada ${number(evaluation.evaluated_users)} dari ${number(evaluation.test_users)} pengguna dalam data uji yang memenuhi kriteria evaluasi. Data dibagi berdasarkan pengguna: 80% untuk membangun model dan basis kasus, serta 20% untuk pengujian.</p>
    <p class="validation-lead">Tabel berikut membandingkan lima rekomendasi teratas dari setiap metode. Nilai yang lebih tinggi menunjukkan hasil yang lebih baik pada masing-masing ukuran.</p>
    <p class="table-hint">Geser tabel ke samping untuk melihat seluruh hasil.</p>
    <div class="table-wrap" tabindex="0" role="region" aria-label="Tabel validasi rekomendasi, dapat digeser ke samping">${validationTable(evaluation)}</div>
    <dl class="metric-definitions">${definitions}</dl>
    <p class="validation-note">Setiap pengguna diuji pada destinasi yang sudah dinilai “Ya” atau “Tidak”, dengan minimal lima kandidat dan satu respons “Ya”. Respons “Mungkin” dan destinasi tanpa penilaian dikeluarkan dari kandidat evaluasi. CBR memakai preferensi yang telah diisi dan mengeluarkan destinasi yang hanya ditolak kasus serupa, sesuai proses konsultasi.</p>
    <p class="validation-note">Hasil ini menggambarkan kemampuan mengurutkan destinasi yang telah dinilai dalam dataset. Pengujian belum mengukur kepuasan perjalanan nyata atau kualitas rekomendasi untuk seluruh katalog.</p>`;
}

function validationSection(evaluation) {
  return `<section class="about-card"><h2>Validasi hasil rekomendasi</h2>${validationFacts(evaluation)}</section>`;
}

function dataCleaningSection(audit) {
  const notes = [
    `${number(audit.duplicate_records_removed)} rekaman identik digabungkan sebelum pembagian pengguna.`,
    `${number(audit.repeated_swipes_removed_after_record_dedup)} pengulangan swipe dihapus dan ${number(audit.conflicting_pairs_removed_after_record_dedup)} pasangan berlabel bertentangan dikeluarkan setelah penggabungan rekaman.`,
    `${number(audit.empty_records_excluded)} rekaman tanpa interaksi bersih tidak dipakai sebagai kasus.`,
    "Kolom tanpa penjelasan, rating lama, dan rekomendasi algoritma asal tidak digunakan sebagai fitur.",
    `Aturan terbukti setara dengan pohon sumber pada ${number(audit.rule_equivalence_records)} profil bersih. Aturan merupakan pola data, bukan pengetahuan pakar pariwisata.`,
    "Data merekam ketertarikan, bukan kunjungan atau kepuasan nyata. Biaya dan keamanan aktual tidak tersedia.",
  ];
  const sources = [
    ["https://github.com/Stravl/Stravl-Data", "Dataset Stravl"],
    [
      "https://link.springer.com/article/10.1186/s44147-023-00315-4",
      "Artikel acuan metode",
    ],
    [
      "https://styles.refero.design/style/15d10d6c-1844-46c6-ae69-c99a56e6ad41",
      "Referensi visual",
    ],
  ];

  const bullets = notes.map((note) => `<li>${note}</li>`).join("");
  const links = sources
    .map(
      ([href, label]) =>
        `<a href="${href}" target="_blank" rel="noopener">${label} ↗</a>`,
    )
    .join("");

  return `<section class="about-card">
    <h2>Pembersihan data dan batasan</h2>
    <ul>${bullets}</ul>
    <div class="source-links">${links}</div>
  </section>`;
}

function renderAbout() {
  state.screen = "about";
  const { audit, evaluation } = state.project;

  main.innerHTML = `<section class="about wrap fade-in">
    <button class="button ghost small" data-action="return"><span aria-hidden="true">←</span> Kembali</button>
    <h1>Tentang Tourguider</h1>
    <p class="about-intro">${ABOUT_INTRO}</p>
    ${statCards(audit)}
    ${methodsSection()}
    ${validationSection(evaluation)}
    ${dataCleaningSection(audit)}
    <button class="button" data-action="start">Mulai konsultasi ${arrow}</button>
  </section>`;
}

/* ---------- Penanganan peristiwa ---------- */

document.addEventListener("change", (event) => {
  const target = event.target;
  const isUnknownAnswer = target.id === "unknown-answer";
  const isChoice = target.name === "answer";

  if (isUnknownAnswer && target.checked) {
    main
      .querySelectorAll('[name="answer"]')
      .forEach((input) => (input.checked = false));
  }
  if (isChoice && target.checked) {
    main.querySelector("#unknown-answer").checked = false;
  }
  if (isChoice || isUnknownAnswer) {
    state.selected = [...main.querySelectorAll('[name="answer"]:checked')].map(
      (input) => input.value,
    );
    state.unknown = main.querySelector("#unknown-answer").checked;
  }

  const fieldError = main.querySelector("#field-error");
  if (fieldError) fieldError.hidden = true;
});

/* Kembali ke layar tempat tombol "Tentang proyek" dibuka. */
function returnToPreviousScreen() {
  if (state.returnTo === "results") renderResults();
  else if (state.returnTo === "consultation") renderConsultation();
  else home();
  focusMain();
}

document.addEventListener("click", async (event) => {
  const trigger = event.target.closest("[data-action]");
  if (!trigger || state.busy) return;

  if (window.location?.protocol === "file:") {
    window.location.href = LOCAL_SERVER_URL;
    return;
  }

  switch (trigger.dataset.action) {
    case "home":
      home();
      focusMain();
      break;
    case "start":
      await start();
      break;
    case "about":
      await about();
      break;
    case "back": {
      const lastAnswer = state.consultation.summary.at(-1);
      if (lastAnswer) await edit(lastAnswer.field);
      else {
        home();
        focusMain();
      }
      break;
    }
    case "edit":
      await edit(trigger.dataset.field);
      break;
    case "edit-first":
      await edit(state.consultation.summary[0].field);
      break;
    case "retry-answer":
      await sendAnswers(state.retryAnswers);
      break;
    case "tab":
      state.tab = trigger.dataset.tab;
      renderResults(true);
      main.querySelector(`#tab-${state.tab}`).focus({ preventScroll: true });
      break;
    case "return":
      returnToPreviousScreen();
      break;
  }
});

const TAB_NAVIGATION_KEYS = ["ArrowLeft", "ArrowRight", "Home", "End"];

document.addEventListener("keydown", (event) => {
  if (
    event.target.getAttribute("role") !== "tab" ||
    !TAB_NAVIGATION_KEYS.includes(event.key)
  ) {
    return;
  }

  event.preventDefault();
  if (event.key === "Home") state.tab = "rules";
  else if (event.key === "End") state.tab = "cbr";
  else state.tab = state.tab === "rules" ? "cbr" : "rules";

  renderResults(true);
  main.querySelector(`#tab-${state.tab}`).focus({ preventScroll: true });
});

/* ---------- Titik masuk ---------- */

if (window.location?.protocol === "file:") {
  state.screen = "local-file";
  main.innerHTML = `<section class="error-box">
    <h1>Buka Tourguider melalui server lokal.</h1>
    <p>Jalankan run.command di folder proyek, lalu buka alamat di bawah agar konsultasi terhubung dengan mesin rekomendasi.</p>
    <a class="button" href="${LOCAL_SERVER_URL}">Buka Tourguider ↗</a>
  </section>`;
} else {
  home();
}
