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
  const recent = savedResult();
  history = value ? [value, JSON.stringify(recent?.answers) === JSON.stringify(value.answers)
    ? recentResults()[1] : recent].filter(Boolean) : [];
  try {
    sessionStorage.setItem(resultKey, JSON.stringify(history));
  } catch {
    // Consultation still works when browser storage is disabled.
  }
}

function home() {
  main.innerHTML = `<section class="home wrap">
    <h1 class="hero-title">Rekomendasi tempat wisata <em>di Indonesia</em></h1>
    <p class="hero-copy">Pilih wilayah, minat, dan tipe rombongan. Tourguider mencocokkan pilihanmu dengan riwayat kunjungan di Bali, Yogyakarta, dan Malang.</p>
    <div class="hero-actions"><button class="button" data-action="start">Mulai konsultasi ↗</button><a class="nav-link" href="/alur-cbr">Lihat alur CBR</a></div>
    <div class="home-steps">
      <div class="home-step"><span class="step-number">01</span><div><h2>Isi preferensi</h2><p>Pilih wilayah, tipe rombongan, dan jenis wisata.</p></div></div>
      <div class="home-step"><span class="step-number">02</span><div><h2>Cari kasus serupa</h2><p>Bandingkan rating dari kunjungan dengan tipe rombongan serupa.</p></div></div>
      <div class="home-step"><span class="step-number">03</span><div><h2>Lihat satu tempat</h2><p>Telusuri alasan tempat itu terpilih.</p></div></div>
    </div>
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

document.addEventListener("change", (event) => {
  const form = main.querySelector("form");
  if (form && event.target.form === form && event.target.name === "choice" && !pending) {
    form.querySelector('button[type="submit"]').disabled = !event.target.checked;
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
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (pending) return;
  if (action === "home") location.assign("/");
  if (action === "start") { draft = {}; saveResult(null); request("start"); }
  if (action === "retry") retryRequest?.();
  if (action === "back") revise(state.question_number - 2);
  if (action === "revise") revise(0);
  if (action === "alternative") {
    draft = { ...state.alternatives[Number(event.target.closest("[data-index]").dataset.index)].answers };
    request("answer", draft);
  }
});

const params = new URLSearchParams(location.search);
if (location.pathname === "/alur-cbr") flow();
else if (params.has("ubah") && (state = savedResult())) revise(0);
else if (params.has("mulai") || params.has("ubah")) { saveResult(null); request("start"); }
else home();
