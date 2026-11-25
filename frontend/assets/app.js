const main = document.querySelector("#main");
const resultKey = "tourguider-mendeley-result-v4";
let state;
let history;
let pending = false;
const number = new Intl.NumberFormat("id-ID");
let draft = {};
const baseFields = ["region", "mode", "category"];
const escapeText = (value) => String(value).replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);

function recentResults() {
  if (!history) {
    try {
      const stored = JSON.parse(sessionStorage.getItem(resultKey));
      history = Array.isArray(stored) ? stored : [];
    } catch {
      history = [];
    }
  }
  return history;
}

function savedResult() {
  return recentResults()[0];
}

function saveResult(value) {
  if (!value) return;
  const key = JSON.stringify(value.answers);
  const rest = recentResults().filter((item) => JSON.stringify(item.answers) !== key);
  history = [value, ...rest].slice(0, 5);
  try {
    sessionStorage.setItem(resultKey, JSON.stringify(history));
  } catch {
    // Consultation still works when browser storage is disabled.
  }
}

const presets = [
  {
    title: "Air Terjun di Malang",
    meta: "Malang · Teman · Air terjun",
    answers: { region: ["malang"], mode: ["friends"], category: ["waterfall"] },
  },
  {
    title: "Wisata Gunung di Yogyakarta",
    meta: "Yogyakarta · Keluarga · Gunung & vulkanologi",
    answers: { region: ["yogyakarta"], mode: ["family"], category: ["volcano"] },
  },
  {
    title: "Rekreasi di Bali",
    meta: "Bali · Pasangan · Rekreasi",
    answers: { region: ["bali"], mode: ["couples"], category: ["recreation"] },
  },
];

function home() {
  const recent = recentResults();
  main.innerHTML = `<section class="home wrap">
    <h1 class="hero-title">Rekomendasi tempat wisata <em>di Indonesia</em></h1>
    <p class="hero-copy">Pilih wilayah, minat, dan tipe rombongan. Tourguider mencocokkan pilihanmu dengan riwayat kunjungan di Bali, Yogyakarta, dan Malang.</p>
    <div class="hero-actions"><button class="button" data-action="start">Mulai konsultasi ↗</button><a class="nav-link" href="/alur-cbr">Lihat alur CBR</a></div>
    <div class="home-steps">
      <div class="home-step"><span class="step-number">01</span><div><h2>Isi preferensi</h2><p>Pilih wilayah, tipe rombongan, dan jenis wisata.</p></div></div>
      <div class="home-step"><span class="step-number">02</span><div><h2>Cari kasus serupa</h2><p>Bandingkan rating dari kunjungan dengan tipe rombongan serupa.</p></div></div>
      <div class="home-step"><span class="step-number">03</span><div><h2>Lihat satu tempat</h2><p>Telusuri alasan tempat itu terpilih.</p></div></div>
    </div>
    <section class="home-panel" aria-labelledby="preset-title">
      <div class="panel-head">
        <div><h2 id="preset-title">Skenario contoh cepat</h2><p>Langsung uji rekomendasi dengan kombinasi populer dari panduan demo.</p></div>
        <a class="nav-link" href="/basis-kasus">Jelajahi 27 destinasi ↗</a>
      </div>
      <div class="preset-grid">
        ${presets.map((preset, index) => `<button class="preset-card" type="button" data-action="preset" data-index="${index}">
          <strong>${escapeText(preset.title)}</strong>
          <span>${escapeText(preset.meta)}</span>
          <small>Jalankan konsultasi ↗</small>
        </button>`).join("")}
      </div>
    </section>
    ${recent.length ? `<section class="home-panel" aria-labelledby="history-title">
      <div class="panel-head">
        <div><h2 id="history-title">Riwayat konsultasi sesi ini</h2><p>Buka kembali hasil sebelumnya untuk membandingkan rekomendasi.</p></div>
      </div>
      <div class="history-list">
        ${recent.map((entry, index) => `<button class="history-item" type="button" data-action="open-history" data-index="${index}">
          <div><strong>${escapeText(entry.recommendation?.name ?? "Belum ada rekomendasi")}</strong>
            <span>${escapeText(entry.summary.map((item) => item.value).join(" · "))}</span></div>
          <span class="history-score">${entry.trace?.score == null ? "Bukti kurang" : `${cbrDecimal.format(entry.trace.score)}/5`} ↗</span>
        </button>`).join("")}
      </div>
    </section>` : ""}
  </section>`;
}

async function request(path, answers) {
  if (pending) return;
  pending = true;
  const form = main.querySelector("form");
  const error = main.querySelector("#request-error");
  if (error) error.textContent = "";
  if (form) {
    form.setAttribute("aria-busy", "true");
    for (const button of form.querySelectorAll("button")) button.disabled = true;
  } else {
    main.innerHTML = '<p class="loading" role="status">Memuat konsultasi…</p>';
  }
  try {
    const response = await fetch(`/api/consultations/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: answers ? JSON.stringify({ answers }) : undefined,
    });
    if (!response.ok) throw new Error("Permintaan gagal");
    state = await response.json();
    if (state.status === "question") {
      renderQuestion();
    } else {
      saveResult(state);
      renderResult();
    }
    main.focus();
  } catch {
    const message = "Konsultasi belum bisa dimuat. Coba lagi.";
    if (error) error.textContent = message;
    else main.innerHTML = `<section class="wrap error-box"><p role="alert">${message}</p><button class="button" data-action="retry">Coba lagi</button></section>`;
    retryRequest = () => request(path, answers);
  } finally {
    pending = false;
    if (form) {
      form.removeAttribute("aria-busy");
      for (const button of form.querySelectorAll("button")) {
        button.disabled = button.type === "submit" && !form.querySelector('input[name="choice"]:checked');
      }
    }
  }
}

let retryRequest;


function renderQuestion() {
  const q = state.question;
  const unavailable = new Set(q.unavailable);
  const previous = draft[q.id]?.[0];
  const selected = previous && !unavailable.has(previous)
    ? previous
    : null;
  main.innerHTML = `<section class="wrap"><div class="consult">
    <form class="question-card">
      <div class="card-meta"><span>${escapeText(q.label)}</span><span>Langkah ${state.question_number}</span></div>
      <h1 id="question-title">${escapeText(q.prompt)}</h1>
      <p class="question-hint">Pilih satu jawaban untuk melanjutkan.</p>
      <fieldset class="option-grid" aria-labelledby="question-title">
      ${Object.entries(q.options).map(([id, label]) => {
        const disabled = unavailable.has(id);
        return `<label class="option">
          <input type="radio" name="choice" value="${escapeText(id)}" ${selected === id ? "checked" : ""} ${disabled ? "disabled" : "required"}>
          <span>${escapeText(label)}${disabled ? '<small class="option-note">Belum ada tempat yang cocok</small>' : ""}</span>
        </label>`;
      }).join("")}
      </fieldset>
      ${unavailable.size ? '<p class="availability-note">Pilihan yang tidak aktif belum punya tempat yang memenuhi jawabanmu. Ubah jawaban sebelumnya untuk membuka pilihan lain.</p>' : ""}
      <p id="request-error" class="field-error" role="alert"></p>
      <div class="form-actions">
        ${state.question_number > 1 ? '<button class="button ghost" type="button" data-action="back">Kembali</button>' : ""}
        <button class="button" type="submit" ${selected ? "" : "disabled"}>${q.id === "category" ? "Lihat rekomendasi" : "Lanjutkan"} ↗</button>
      </div>
    </form>
    <div class="answer-strip chips">${summary(state.summary)}</div>
  </div></section>`;
}

function summary(items) {
  return items.map(({ label, value }) => `<span class="chip">${escapeText(label)} · ${escapeText(value)}</span>`).join("");
}

function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return [hours && `${hours} jam`, remainder && `${remainder} menit`].filter(Boolean).join(" ");
}

const noResultReason = {
  no_places: "Katalog belum punya tempat yang cocok dengan wilayah dan minat ini.",
  no_matching_cases: "Tempat dalam pencarian ini belum memiliki catatan dengan tipe rombongan yang sama.",
  below_support: "Ada kunjungan yang cocok, tetapi jumlah pengulas per tempat belum mencapai ambang.",
};

function renderResult() {
  const item = state.recommendation;
  const match = item ? [
    item.region,
    item.activity ?? (state.answers.category?.[0] !== "all" ? item.category : ""),
    state.answers.duration?.[0] !== "any" && item.minutes ? `Hingga ${formatDuration(item.minutes)}` : "",
  ].filter(Boolean) : [];
  const facts = item ? [
    ["Durasi kegiatan", item.minutes ? `Hingga ${formatDuration(item.minutes)}` : null],
    ["Jalur", item.route],
    ["Fasilitas", item.facilities?.join(", ")],
    ["Lokasi dalam dataset", item.recorded_location],
    ["Akses dan kunjungan", item.access],
    ["Tarif tercantum", item.price],
  ].filter(([, value]) => value) : [];
  const checked = item?.checked ? new Intl.DateTimeFormat("id-ID", {
    dateStyle: "long", timeZone: "UTC",
  }).format(new Date(item.checked)) : "";
  main.innerHTML = `<section class="wrap"><div class="consult result-shell"><article class="question-card result-card">
    <header class="result-hero">
      <div class="result-kicker"><span>${item ? "Rekomendasi wisata" : "Belum ada rekomendasi"}</span>
        ${item ? `<span class="result-category">${escapeText(item.category)}</span>` : ""}</div>
      <h1>${escapeText(item?.name ?? "Coba sesuaikan pilihanmu")}</h1>
      ${item ? `<p class="result-location">${escapeText(item.region)}</p>` : ""}
    </header>
    <div class="result-body">
      ${item ? `<section class="result-match" aria-labelledby="result-match-title">
        <h2 id="result-match-title">Kenapa tempat ini cocok?</h2>
        <ul class="result-match-tags" aria-label="Kecocokan dengan pilihanmu">
          ${match.map((value) => `<li>${escapeText(value)}</li>`).join("")}
        </ul>
        <p>${escapeText(item.reason)}</p>

      </section>
      ${facts.length ? `<section class="result-facts" aria-labelledby="result-facts-title"><h2 id="result-facts-title">Info kunjungan</h2>
        <dl>${facts.map(([label, value]) => `<div><dt>${escapeText(label)}</dt><dd>${escapeText(value)}</dd></div>`).join("")}</dl></section>` : ""}
      <div class="visit-links"><a class="button" href="${escapeText(item.map_url)}" target="_blank" rel="noopener noreferrer">Buka peta ↗</a><a class="button outline" href="${escapeText(item.operator_url ?? item.source)}" target="_blank" rel="noopener noreferrer">${item.operator_url ? "Cek info pengelola" : "Lihat sumber kasus"} ↗</a></div>
      ${checked ? `<p class="result-note">Sumber diperiksa ${escapeText(checked)}.</p>` : ""}`
    : `<p>${noResultReason[state.trace.reason] ?? "Belum ada tempat yang memenuhi semua pilihanmu."}</p>
      <div class="visit-links">${state.alternatives.map((option, index) => `<button class="button outline" data-action="alternative" data-index="${index}">${escapeText(option.label)}</button>`).join("")}</div>`}
      <details class="result-preferences"><summary>Preferensi konsultasi</summary><div class="answer-strip chips">${summary(state.summary)}</div></details>
      <div class="form-actions cbr-actions"><button class="button ghost" data-action="revise">Ubah preferensi</button><a class="nav-link" href="/alur-cbr">Lihat alur CBR ↗</a></div>
    </div>
  </article></div></section>`;
}

function revise(step) {
  draft = { ...draft, ...state.answers };
  const fields = [...baseFields];
  const prefix = Object.fromEntries(fields.slice(0, step).map((key) => [key, draft[key]]).filter(([, value]) => value));
  request("answer", prefix);
}

const cbrDecimal = new Intl.NumberFormat("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
const cbrDate = new Intl.DateTimeFormat("id-ID", { month: "long", year: "numeric", timeZone: "UTC" });

function comparison(recent) {
  const previous = recentResults()[1];
  if (!previous || !recent || ["policy_version", "min_reviewers", "prior_weight"]
    .some((key) => previous.trace[key] !== recent.trace[key])) return "";
  const render = (result, label) => {
    const trace = result.trace;
    const place = result.recommendation?.name || "Belum ada rekomendasi";
    return `<div class="cbr-compare-item"><strong>${label} · ${escapeText(place)}</strong>
      <p>${escapeText(result.summary.map((answer) => answer.value).join(" · "))}</p>
      <p>${trace.matched_visit_count == null ? "" : `${number.format(trace.matched_visit_count)} kunjungan cocok · `}
        ${number.format(trace.eligible_places)} kandidat lolos · ${trace.score == null ? "Skor belum tersedia" : `skor ${cbrDecimal.format(trace.score)}/5`}</p></div>`;
  };
  const before = previous.trace.ranking ?? [];
  const after = recent.trace.ranking ?? [];
  const removed = before.filter((item) => !after.some((other) => other.name === item.name));
  const added = after.filter((item) => !before.some((other) => other.name === item.name));
  const changes = [
    added.length ? `Kandidat masuk: ${added.map((item) => item.name).join(", ")}` : "",
    removed.length ? `Kandidat keluar: ${removed.map((item) => item.name).join(", ")}` : "",
  ].filter(Boolean);
  return `<section class="cbr-explanation"><h2>Setelah preferensi diubah</h2>
    <div class="cbr-comparison">${render(previous, "Sebelum")}${render(recent, "Sesudah")}</div>
    ${changes.length ? `<details><summary>Lihat perubahan kandidat</summary>${changes.map((line) => `<p>${escapeText(line)}</p>`).join("")}</details>` : ""}
  </section>`;
}

function flow() {
  const recent = savedResult();
  const trace = recent?.trace;
  const item = recent?.recommendation;
  const individual = trace?.evidence_type === "individual";
  main.innerHTML = `<section class="wrap cbr-page cbr-guide">
    <article class="question-card result-card">
      <header class="result-hero">
        <div class="result-kicker">Case-Based Reasoning</div>
        <h1>Alur CBR</h1>
        <p class="result-location">${item ? escapeText(item.name) : "Rekomendasi dari kunjungan terdahulu"}</p>
      </header>
      <div class="result-body">
        ${trace ? `<section class="cbr-explanation">
          <h2>${item ? `Mengapa ${escapeText(item.name)}?` : "Kenapa belum ada hasil?"}</h2>
          <div class="answer-strip chips">${summary(recent.summary)}</div>
          <p>${trace.eligible_places} dari ${trace.matching_places} tempat memenuhi ambang ${trace.min_reviewers} pengulas berbeda dengan tipe rombongan yang sama.</p>
          ${individual ? `<p>Dari ${number.format(trace.visit_count)} kunjungan dalam wilayah dan minat ini, ${number.format(trace.matched_visit_count)} cocok dengan tipe rombongan (${number.format(trace.matched_unique_reviewers)} pengulas unik). Kecocokan bernilai 1 untuk rombongan sama dan 0 untuk yang berbeda.</p>`
            : "<p>Basis data aktif memakai ringkasan historis. Rincian kontribusi per kunjungan tersedia pada basis kasus individual.</p>"}
          ${item ? `<div class="cbr-evidence">
            <h2>Contoh kunjungan serupa</h2>
            <p>${individual ? `${number.format(trace.winner_visit_count)} kunjungan dari ${number.format(trace.reviewer_count)} pengulas dipakai untuk menghitung skor. Berikut ${trace.examples.length} contoh.`
              : "Contoh kunjungan dari ringkasan historis."}</p>
            <ol>${trace.examples.map((visit) => `<li>${visit.label ? `<strong>${escapeText(visit.label)}</strong> · ` : ""}${escapeText(cbrDate.format(new Date(Date.UTC(visit.year, visit.month - 1))))} · ${escapeText(visit.mode)} · <strong>${visit.rating}/5</strong>
              ${visit.reviewer_visit_count > 1 ? `<p>Pengulas ini punya ${visit.reviewer_visit_count} kunjungan serupa. Rerata ${cbrDecimal.format(visit.reviewer_mean)}/5 masuk perhitungan sebagai satu nilai.</p>` : ""}</li>`).join("")}</ol>
            <h2>Cara skor dihitung</h2>
            <p>Rata-rata kasus serupa ${cbrDecimal.format(trace.similar_mean)}/5 diberi bobot ${trace.reviewer_count}. Rata-rata historis tempat ${cbrDecimal.format(trace.historical_mean)}/5 diberi bobot ${trace.prior_weight}. Jumlah keduanya setelah dibobot dibagi total bobot.</p>
            <p><strong>Skor akhir ${cbrDecimal.format(trace.score)}/5.</strong> ${trace.eligible_places === 1
              ? "Hanya tempat ini yang memenuhi ambang dukungan."
              : "Skor tertinggi dipilih. Jika seri, tempat dengan lebih banyak pengulas serupa didahulukan, lalu ID tempat terkecil."}</p>
            ${individual ? `<details><summary>Lihat angka perhitungan</summary><p class="cbr-formula">(${trace.reviewer_count} × ${escapeText(String(trace.similar_mean))} + ${trace.prior_weight} × ${escapeText(String(trace.historical_mean))}) / (${trace.reviewer_count} + ${trace.prior_weight}) = ${escapeText(String(trace.score))}</p></details>` : ""}
          </div>` : `<p>${noResultReason[trace.reason] ?? "Ubah preferensi untuk mencari kasus lain."}</p>
            ${recent.alternatives.length ? `<ul>${recent.alternatives.map((option) => `<li>${escapeText(option.label)}</li>`).join("")}</ul>` : ""}`}
          ${(individual ? trace.candidates.length : trace.eligible_places > 1) ? `<details><summary>Lihat kandidat</summary><ol>
            ${(individual ? [...trace.ranking, ...trace.candidates.filter((candidate) => candidate.status !== "eligible")] : trace.ranking)
              .map((place) => `<li>${escapeText(place.name)} · ${number.format(place.count)} pengulas · ${place.score == null
                ? place.status === "no_matching_cases" ? "Belum ada kasus cocok" : "Di bawah ambang"
                : `${cbrDecimal.format(place.score)}/5`}</li>`).join("")}
          </ol></details>` : ""}
        </section>` : ""}
        ${comparison(recent)}
        <section class="cbr-diagram">
          <h2>Cara rekomendasi dibuat</h2>
          <ol class="cbr-flow" aria-label="Diagram alur CBR">
            <li><strong>01 · Isi preferensi</strong><p>Pilih wilayah, tipe rombongan, dan minat.</p></li>
            <li><strong>02 · Retrieve dan kecocokan</strong><p>Saring tempat, lalu ambil kunjungan dengan rombongan yang sama.</p><p class="cbr-branch">Bukti kurang → ubah preferensi.</p></li>
            <li><strong>03 · Reuse</strong><p>Gabungkan rating kasus serupa dengan rata-rata historis tempat.</p></li>
            <li><strong>04 · Tinjau hasil</strong><p>Lihat satu rekomendasi dan alasan pemilihannya, lalu ubah preferensi bila perlu.</p></li>
          </ol>
          <p class="result-note"><strong>Tahap lanjutan.</strong> Revise menilai hasil setelah kunjungan. Retain menyimpan pengalaman yang telah divalidasi.</p>
        </section>
        <div class="form-actions cbr-actions"><a class="button" href="${trace ? "/?ubah=1" : "/?mulai=1"}">${trace ? "Ubah preferensi" : "Mulai konsultasi"} ↗</a></div>
      </div>
    </article>
  </section>`;
}

let catalogData = null;
const catalogFilter = { region: "all", category: "all", query: "" };

function renderCatalogList() {
  const list = main.querySelector("#catalog-list");
  const countEl = main.querySelector("#catalog-count");
  if (!list || !catalogData) return;
  const q = catalogFilter.query.trim().toLowerCase();
  const filtered = catalogData.places.filter((place) => {
    if (catalogFilter.region !== "all" && place.region !== catalogFilter.region) return false;
    if (catalogFilter.category !== "all" && place.category !== catalogFilter.category) return false;
    if (q && !place.name.toLowerCase().includes(q) && !(place.address || "").toLowerCase().includes(q)) return false;
    return true;
  });
  if (countEl) countEl.textContent = `Menampilkan ${filtered.length} dari ${catalogData.places.length} destinasi aktif`;
  if (!filtered.length) {
    list.innerHTML = '<p class="catalog-empty">Tidak ada destinasi yang cocok dengan filter tersebut.</p>';
    return;
  }
  const minRev = catalogData.min_reviewers;
  list.innerHTML = filtered.map((place) => `<article class="catalog-card">
    <div class="catalog-card-top">
      <div class="catalog-badges">
        <span class="chip">${escapeText(place.region_label)}</span>
        <span class="chip chip-soft">${escapeText(place.category_label)}</span>
      </div>
      <strong class="catalog-rating">${cbrDecimal.format(place.historical_mean)}/5</strong>
    </div>
    <h3>${escapeText(place.name)}</h3>
    ${place.address ? `<p class="catalog-address">${escapeText(place.address)}</p>` : ""}
    <div class="catalog-modes" aria-label="Jumlah pengulas unik per tipe rombongan">
      ${Object.entries(catalogData.modes).map(([code, label]) => {
        const count = place.mode_counts[code] ?? 0;
        const ok = count >= minRev;
        return `<span class="mode-pill ${ok ? "is-eligible" : "is-low"}" title="${ok ? "Memenuhi ambang minimal" : "Di bawah ambang minimal"}">${escapeText(label)}: <strong>${number.format(count)}</strong></span>`;
      }).join("")}
    </div>
    <div class="catalog-card-footer">
      <a class="nav-link" href="${escapeText(place.map_url)}" target="_blank" rel="noopener noreferrer">Buka peta ↗</a>
    </div>
  </article>`).join("");
}

async function catalogView() {
  main.innerHTML = '<p class="loading" role="status">Memuat basis kasus destinasi…</p>';
  try {
    const response = await fetch("/api/catalog");
    if (!response.ok) throw new Error("Gagal memuat katalog");
    catalogData = await response.json();
    main.innerHTML = `<section class="wrap page-shell">
      <header class="page-hero">
        <div class="result-kicker">Basis Pengetahuan</div>
        <h1>Basis kasus destinasi</h1>
        <p class="page-subtitle">Daftar lengkap ${catalogData.places.length} objek wisata aktif beserta rata-rata historis dan jumlah pengulas unik per tipe rombongan. Badge hijau menandakan jumlah pengulas memenuhi ambang minimal (${catalogData.min_reviewers} pengulas).</p>
      </header>
      <div class="catalog-toolbar">
        <div class="filter-pills" role="group" aria-label="Filter wilayah">
          <button type="button" class="filter-pill is-active" data-action="filter-region" data-region="all">Semua wilayah</button>
          ${Object.entries(catalogData.regions).map(([code, label]) => `<button type="button" class="filter-pill" data-action="filter-region" data-region="${escapeText(code)}">${escapeText(label)}</button>`).join("")}
        </div>
        <div class="filter-inputs">
          <select id="catalog-category" aria-label="Filter kategori">
            <option value="all">Semua kategori</option>
            ${Object.entries(catalogData.categories).map(([code, label]) => `<option value="${escapeText(code)}">${escapeText(label)}</option>`).join("")}
          </select>
          <input id="catalog-search" type="search" placeholder="Cari nama tempat atau alamat…" aria-label="Cari destinasi">
        </div>
      </div>
      <p id="catalog-count" class="catalog-count"></p>
      <div id="catalog-list" class="catalog-grid"></div>
    </section>`;
    renderCatalogList();
  } catch {
    main.innerHTML = '<section class="wrap error-box"><p role="alert">Basis kasus belum bisa dimuat. Coba muat ulang halaman.</p></section>';
  }
}

async function evaluationView() {
  main.innerHTML = '<p class="loading" role="status">Memuat ringkasan data dan evaluasi…</p>';
  try {
    const response = await fetch("/api/overview");
    if (!response.ok) throw new Error("Gagal memuat evaluasi");
    const data = await response.json();
    const ev = data.evaluation;
    const c = data.counts;
    const regionLabels = { bali: "Bali", yogyakarta: "Yogyakarta", malang: "Malang", all: "Semua wilayah" };
    const covRows = ["bali", "yogyakarta", "malang", "all"].filter((k) => ev.coverage_before?.[k] && ev.coverage_after?.[k]);
    main.innerHTML = `<section class="wrap page-shell">
      <header class="page-hero">
        <div class="result-kicker">Transparansi Data & Uji Model</div>
        <h1>Data & evaluasi CBR</h1>
        <p class="page-subtitle">Ringkasan pembersihan Tourism Dataset Mendeley v1, ketimpangan sebaran wilayah, serta hasil pengujian akurasi rating dan cakupan rekomendasi.</p>
      </header>

      <div class="kpi-grid">
        <div class="kpi-card"><span>Destinasi aktif</span><strong>${number.format(c.active_places)}</strong><small>${c.excluded_places} tempat ditahan oleh kebijakan</small></div>
        <div class="kpi-card"><span>Kunjungan aktif</span><strong>${number.format(c.active_visits)}</strong><small>Dari ${number.format(c.raw_visits)} transaksi mentah</small></div>
        <div class="kpi-card"><span>Pengulas unik</span><strong>${number.format(c.active_reviewers)}</strong><small>1 pengulas dihitung 1 suara</small></div>
        <div class="kpi-card"><span>MAE prediksi CBR</span><strong>${ev.cbr_mae == null ? "-" : cbrDecimal.format(ev.cbr_mae)}</strong><small>Pada ${number.format(ev.cases)} kasus uji holdout</small></div>
      </div>

      <article class="question-card eval-card">
        <h2>Distribusi & ketimpangan data wilayah</h2>
        <p class="eval-lead">Secara jumlah tempat terlihat cukup berimbang, tetapi kepadatan ulasan sangat terkonsentrasi di Bali. Kondisi ini memengaruhi ketersediaan kandidat di Malang.</p>
        <div class="bar-list">
          ${data.regions.map((reg) => `<div class="bar-row">
            <div class="bar-meta"><strong>${escapeText(reg.label)} (${reg.places} tempat)</strong><span>${number.format(reg.visits)} kunjungan (${reg.share.toFixed(1)}%)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:${Math.max(reg.share, 1.5).toFixed(1)}%"></div></div>
          </div>`).join("")}
        </div>
      </article>

      <div class="eval-two-col">
        <article class="question-card eval-card">
          <h2>Pembersihan dataset</h2>
          <dl class="eval-dl">
            <div><dt>Transaksi mentah Mendeley v1</dt><dd>${number.format(c.raw_visits)}</dd></div>
            <div><dt>Duplikat dibuang</dt><dd>- ${number.format(c.duplicates_removed)}</dd></div>
            <div><dt>Baris rating konflik dibuang</dt><dd>- ${number.format(c.conflicting_rows_removed)}</dd></div>
            ${c.excluded_visits ? `<div><dt>Kunjungan 3 tempat nonaktif</dt><dd>- ${number.format(c.excluded_visits)}</dd></div>` : ""}
            <div class="eval-dl-total"><dt>Total kunjungan aktif</dt><dd>${number.format(c.active_visits)}</dd></div>
          </dl>
        </article>

        <article class="question-card eval-card">
          <h2>Rumus & parameter aktif</h2>
          <p class="cbr-formula">(n × rata-rata serupa + k × rata-rata historis) / (n + k)</p>
          <dl class="eval-dl">
            <div><dt>Mode basis data aktif</dt><dd>${data.evidence_type === "individual" ? "Kasus individual (v4)" : "Ringkasan agregat (bawaan)"}</dd></div>
            <div><dt>Ambang minimal pengulas (n)</dt><dd>${data.min_reviewers} pengulas unik</dd></div>
            <div><dt>Bobot penyeimbang (k)</dt><dd>${data.prior_weight}</dd></div>
            <div><dt>Baseline MAE (historis)</dt><dd>${ev.baseline_mae == null ? "-" : cbrDecimal.format(ev.baseline_mae)}</dd></div>
          </dl>
        </article>
      </div>

      ${covRows.length ? `<article class="question-card eval-card">
        <h2>Cakupan rekomendasi sebelum & sesudah optimasi</h2>
        <p class="eval-lead">Menurunkan batas dukungan dari 10 menjadi 5 pengulas pada v4 menaikkan cakupan total dari ${ev.coverage_before_total}/120 menjadi ${ev.coverage_after_total}/120 kombinasi tanpa menurunkan akurasi MAE.</p>
        <div class="table-wrap">
          <table class="eval-table">
            <thead><tr><th>Wilayah input</th><th>Sebelum (ambang 10)</th><th>Sesudah (ambang 5)</th><th>Pemenang unik</th></tr></thead>
            <tbody>
              ${covRows.map((key) => `<tr>
                <td>${escapeText(regionLabels[key] ?? key)}</td>
                <td>${ev.coverage_before[key].supported}/30</td>
                <td><strong>${ev.coverage_after[key].supported}/30</strong></td>
                <td>${ev.coverage_before[key].unique_winners} → ${ev.coverage_after[key].unique_winners}</td>
              </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </article>` : ""}

      <div class="form-actions cbr-actions">
        <a class="button" href="/?mulai=1">Mulai konsultasi ↗</a>
        <a class="button outline" href="${escapeText(data.source)}" target="_blank" rel="noopener noreferrer">Sumber Mendeley ↗</a>
      </div>
    </section>`;
  } catch {
    main.innerHTML = '<section class="wrap error-box"><p role="alert">Data evaluasi belum bisa dimuat. Coba muat ulang halaman.</p></section>';
  }
}

document.addEventListener("change", (event) => {
  const form = main.querySelector("form");
  if (form && event.target.form === form && event.target.name === "choice" && !pending) {
    form.querySelector('button[type="submit"]').disabled = !event.target.checked;
  }
  if (event.target.id === "catalog-category") {
    catalogFilter.category = event.target.value;
    renderCatalogList();
  }
});

document.addEventListener("input", (event) => {
  if (event.target.id === "catalog-search") {
    catalogFilter.query = event.target.value;
    renderCatalogList();
  }
});

document.addEventListener("submit", (event) => {
  if (event.target !== main.querySelector("form")) return;
  event.preventDefault();
  const choice = new FormData(event.target).get("choice");
  if (choice) {
    draft[state.question.id] = [choice];
    request("answer", { ...state.answers, [state.question.id]: [choice] });
  }
});

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-action]");
  const action = trigger?.dataset.action;
  if (pending) return;
  if (action === "home") location.assign("/");
  if (action === "start") { draft = {}; request("start"); }
  if (action === "retry") retryRequest?.();
  if (action === "back") revise(state.question_number - 2);
  if (action === "revise") revise(0);
  if (action === "alternative") {
    draft = { ...state.alternatives[Number(trigger.dataset.index)].answers };
    request("answer", draft);
  }
  if (action === "preset") {
    const preset = presets[Number(trigger.dataset.index)];
    if (preset) {
      draft = { ...preset.answers };
      request("answer", draft);
    }
  }
  if (action === "open-history") {
    const entry = recentResults()[Number(trigger.dataset.index)];
    if (entry) {
      state = entry;
      draft = { ...entry.answers };
      renderResult();
      main.focus();
    }
  }
  if (action === "filter-region") {
    catalogFilter.region = trigger.dataset.region;
    for (const pill of main.querySelectorAll('[data-action="filter-region"]')) {
      pill.classList.toggle("is-active", pill === trigger);
    }
    renderCatalogList();
  }
});

for (const link of document.querySelectorAll(".site-header nav a.nav-link")) {
  if (link.getAttribute("href") === location.pathname) link.classList.add("is-active");
}

const params = new URLSearchParams(location.search);
if (location.pathname === "/alur-cbr") flow();
else if (location.pathname === "/basis-kasus") catalogView();
else if (location.pathname === "/evaluasi") evaluationView();
else if (params.has("ubah") && (state = savedResult())) revise(0);
else if (params.has("mulai") || params.has("ubah")) { draft = {}; request("start"); }
else home();
