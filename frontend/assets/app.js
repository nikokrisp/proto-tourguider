const main = document.querySelector('#main');
const live = document.querySelector('#announcement');
const state = {screen: 'home', consultation: null, selected: [], unknown: false, tab: 'rules', project: null, busy: false, returnTo: 'home'};
const arrow = '<span aria-hidden="true">↗</span>';
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = n => new Intl.NumberFormat('id-ID').format(n);

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);
  try {
    const res = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers: {'Content-Type':'application/json'}, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal});
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Jawaban belum dapat diproses. Periksa pilihanmu dan coba lagi.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Proses membutuhkan waktu lebih lama. Coba lagi sebentar.');
    if (error instanceof TypeError) throw new Error('Aplikasi belum terhubung. Pastikan server lokal masih berjalan, lalu coba lagi.');
    throw error;
  } finally { clearTimeout(timeout); }
}

function focusMain() { main.focus({preventScroll:true}); window.scrollTo({top:0,behavior:'instant'}); }
function announce(text) { live.textContent = text; }
function home() {
  state.screen='home';
  state.pendingEdit=null;
  announce('Beranda Tourguider.');
  main.innerHTML = `<section class="home wrap fade-in" aria-labelledby="hero-title">
    <div class="eyebrow">Proyek Sistem Berbasis Pengetahuan</div>
    <h1 id="hero-title" class="hero-title">Rekomendasi destinasi wisata<br>berdasarkan preferensimu.</h1>
    <p class="hero-copy">Tourguider menggunakan forward chaining dan CBR untuk merekomendasikan destinasi dari data Stravl. Isi preferensi perjalananmu untuk melihat hasil dan dasar rekomendasinya.</p>
    <div class="hero-actions"><button class="button" data-action="start">Mulai konsultasi ${arrow}</button><button class="nav-link" data-action="about">Tentang proyek <span aria-hidden="true">↗</span></button></div>
    <p class="quiet-note">Tanpa akun <span>·</span> Pertanyaan mengikuti jawabanmu <span>·</span> Gratis</p>
    <div class="home-steps"><div class="home-step"><span class="step-number">01</span><div><h2>Isi preferensi perjalanan</h2><p>Jawab pertanyaan tentang preferensi perjalananmu.</p></div></div>
    <div class="home-step"><span class="step-number">02</span><div><h2>Lihat rekomendasi destinasi</h2><p>Bandingkan hasil berbasis aturan dan pengguna serupa.</p></div></div>
    <div class="home-step"><span class="step-number">03</span><div><h2>Periksa dasar rekomendasi</h2><p>Lihat aturan yang digunakan dan respons pengguna pendukung.</p></div></div></div>
  </section>`;
}

function loading(label='Memuat konsultasi…') {
  main.setAttribute('aria-busy','true');
  main.innerHTML=`<div class="loading" role="status"><div class="spinner" aria-hidden="true"></div><p>${esc(label)}</p></div>`;
  announce(label);
}

function showError(error, retry) {
  state.screen='error';
  main.removeAttribute('aria-busy');
  main.innerHTML=`<section class="error-box" role="alert"><div class="eyebrow">Sebentar, ada kendala</div><h1>Konsultasi belum dapat diproses.</h1><p>${esc(error.message)}</p><button class="button" data-action="${retry}">Coba lagi ${arrow}</button> <button class="button ghost" data-action="home">Ke beranda</button></section>`;
  focusMain();
}

async function start() {
  if(state.busy) return;
  state.pendingEdit=null;
  state.tab='rules';
  state.busy=true; loading();
  try { state.consultation=await api('/api/consultations/start',{}); state.selected=[];state.unknown=false; renderConsultation();focusMain(); }
  catch(e){showError(e,'start');} finally{state.busy=false;main.removeAttribute('aria-busy');}
}

function chips(summary) {
  return summary.map(a=>`<button class="chip" data-action="edit" data-field="${esc(a.field)}" aria-label="Ubah ${esc(a.label)}: ${esc(a.text)}">${esc(a.text)} <span class="edit-icon" aria-hidden="true">↗</span></button>`).join('');
}

function renderConsultation() {
  const c=state.consultation;
  if(c.complete) {renderResults();return;}
  state.screen='consultation';
  const q=c.question;
  main.innerHTML=`<section class="consult wrap fade-in" aria-labelledby="question-title"><div class="section-top"><span class="eyebrow">Preferensi perjalanan</span><span class="step-caption">Sesuai alur jawabanmu</span></div>
  <form id="question-form" class="question-card" novalidate><div class="card-meta"><span>Pertanyaan ke-${c.question_number} · ${esc(q.label)}</span><span class="ordinal">${String(c.question_number).padStart(2,'0')}</span></div>
    <h1 id="question-title">${esc(q.title)}</h1><p class="question-hint" id="question-hint">${esc(q.hint)}</p>
    <fieldset class="option-grid" aria-describedby="question-hint field-error"><legend class="sr-only">${esc(q.title)}</legend>${q.options.map(o=>`<label class="option"><input type="${q.multiple?'checkbox':'radio'}" name="answer" value="${esc(o.value)}" ${state.selected.includes(o.value)?'checked':''}><span>${esc(o.label)}</span></label>`).join('')}</fieldset>
    <label class="unknown"><input id="unknown-answer" type="checkbox" ${state.unknown?'checked':''}><span>Belum tahu / belum menentukan</span></label>
    <p id="field-error" class="field-error" role="alert" hidden>Pilih jawaban atau tandai “Belum tahu” untuk melanjutkan.</p>
    <div class="form-actions"><button type="button" class="button ghost" data-action="back"><span aria-hidden="true">←</span> Kembali</button><button type="submit" class="button">Lanjutkan ${arrow}</button></div>
  </form>${c.summary.length?`<div class="answer-strip"><p class="answer-strip-title">Jawabanmu sejauh ini · pilih untuk mengubah</p><div class="chips">${chips(c.summary)}</div></div>`:''}
  <p class="consult-note">Pertanyaan menyesuaikan jawabanmu. Pilih jawaban sebelumnya untuk mengubahnya.</p></section>`;
  main.querySelector('#question-form').addEventListener('submit', submitAnswer);
  announce(`Pertanyaan ${c.question_number}: ${q.title}`);
}

async function submitAnswer(event) {
  event.preventDefault();
  if(state.busy)return;
  const form=event.currentTarget;
  const chosen=[...form.querySelectorAll('[name="answer"]:checked')].map(i=>i.value);
  const unknown=form.querySelector('#unknown-answer').checked;
  if(!chosen.length&&!unknown){form.querySelector('#field-error').hidden=false;form.querySelector('[name="answer"]').focus();return;}
  state.selected=chosen;state.unknown=unknown;
  const answers={...state.consultation.answers,[state.consultation.question.field]:unknown?[]:chosen};
  await sendAnswers(answers);
}

async function sendAnswers(answers, label='Memproses jawaban…') {
  if(state.busy)return false;
  state.busy=true;loading(label);
  try{
    state.consultation=await api('/api/consultations/answer',{answers});state.selected=[];state.unknown=false;
    if(state.pendingEdit && state.consultation.question?.field===state.pendingEdit.field){state.selected=state.pendingEdit.values;state.unknown=!state.selected.length;}
    state.pendingEdit=null;renderConsultation();focusMain();return true;
  }
  catch(e){state.retryAnswers=answers;showError(e,'retry-answer');return false;}finally{state.busy=false;main.removeAttribute('aria-busy');}
}

async function edit(field) {
  const c=state.consultation;
  const original=c.answers[field]||[];
  const before={};
  for(const a of c.summary){if(a.field===field)break;before[a.field]=c.answers[a.field];}
  state.pendingEdit={field,values:[...original]};
  await sendAnswers(before);
}

function traceBlock(trace, personalized=true) {
  return `<details class="reasoning"><summary>Lihat proses penalaran</summary><p class="reasoning-intro">${personalized?'Forward chaining: fakta jawaban memicu aturan. Kesimpulan suatu aturan menjadi premis aturan berikutnya sampai kelompok rekomendasi terbentuk.':'Alur berikut menelusuri penanda jawaban kosong. Karena belum ada preferensi yang ditentukan, kelompok akhir ini tidak dipakai untuk personalisasi; daftar hasil menggunakan popularitas data pelatihan.'}</p><ol class="trace-list">${trace.map((t,i)=>`<li class="trace"><span class="trace-label">LANGKAH ${i+1} · ${esc(t.rule_id)}</span><p>Jika <code>${esc(t.premise)}</code> dan ${esc(t.condition.toLowerCase())}, maka <code>${esc(t.conclusion)}</code>.</p></li>`).join('')}</ol></details>`;
}

function renderResults(preserveScroll=false) {
  state.screen='results';
  const c=state.consultation, r=c.results, items=r[state.tab];
  const isRules=state.tab==='rules', personalized=r.personalized!==false;
  main.innerHTML=`<section class="results wrap fade-in"><div class="eyebrow">Hasil konsultasi</div><div class="results-heading"><h1>Rekomendasi destinasi wisata</h1><p>${personalized?'Hasil berdasarkan jawabanmu. Bandingkan rekomendasi berbasis aturan dan pengguna serupa.':'Destinasi populer dari data pelatihan untuk pengguna yang belum menentukan preferensi.'}</p></div>
    <div class="results-summary"><span>Jawaban konsultasi</span>${chips(c.summary)}</div>${r.notice?`<p class="result-notice" role="status">${esc(r.notice)}</p>`:''}
    <div class="results-layout"><div><div class="tabs" role="tablist" aria-label="Metode rekomendasi"><button id="tab-rules" role="tab" class="tab" aria-selected="${isRules}" aria-controls="recommendation-panel" tabindex="${isRules?0:-1}" data-action="tab" data-tab="rules">Berdasarkan aturan</button><button id="tab-cbr" role="tab" class="tab" aria-selected="${!isRules}" aria-controls="recommendation-panel" tabindex="${!isRules?0:-1}" data-action="tab" data-tab="cbr">Pengguna serupa</button></div>
    <div id="recommendation-panel" role="tabpanel" aria-labelledby="tab-${state.tab}" tabindex="0"><p class="tab-description">${!personalized?'Daftar menggunakan popularitas karena preferensi belum ditentukan.':isRules?'Dipilih dari kelompok preferensi yang sesuai, dengan bobot yang sama untuk setiap pengguna.':'Dipilih dari respons pengguna serupa, dengan minimal satu respons Ya untuk setiap kecocokan.'}</p><ol class="destination-list">${items.map((d,i)=>{
      const parts=d.name.split(', '), country=parts.pop(), place=parts.join(', ')||country;
      return `<li class="destination-card"><span class="destination-rank" aria-label="Urutan ${i+1}">${String(i+1).padStart(2,'0')}</span><div><h2 class="destination-title">${esc(place)}</h2><p class="destination-country">${esc(parts.length?country:'')}</p><p class="destination-reason">${esc(d.reason)}</p>${d.fallback?'<span class="support-tag">Alternatif populer</span>':''}</div><span class="destination-icon" aria-hidden="true">↗</span></li>`;
    }).join('')}</ol></div>${traceBlock(c.trace,personalized)}</div>
    <aside class="insight-card" aria-label="Dasar rekomendasi"><span class="spark" aria-hidden="true">✳</span><h2>${!personalized?'Preferensi belum diisi':isRules?'Dasar rekomendasi':'Kasus pembanding'}</h2><p>${!personalized?'Isi preferensi untuk mendapatkan rekomendasi berdasarkan jawabanmu.':isRules?'Forward chaining menentukan kelompok preferensi dari jawabanmu. Destinasi diurutkan dengan bobot yang sama untuk setiap pengguna dalam kelompok tersebut.':'CBR menggunakan hingga 20 pengguna dengan preferensi serupa. Respons Ya, Mungkin, dan Tidak dari pengguna tersebut menentukan urutan rekomendasi.'}</p><hr class="insight-divider"><div class="insight-stat">${number(!personalized?0:isRules?r.segment_users:r.neighbor_count)}</div><div class="insight-label">${!personalized?'preferensi yang sudah ditentukan':isRules?'pengguna dalam kelompok preferensimu':'pengguna serupa menjadi pembanding'}</div>${!isRules?r.similar_cases.map(n=>`<div class="case"><strong>${esc(n.case_id)} · kemiripan ${Math.round(n.similarity*100)}%</strong><p>${esc(n.shared_preferences.join(' · '))}.</p></div>`).join(''):'<p>Angka pendukung menunjukkan respons dalam dataset, bukan jaminan kecocokan atau kepuasan perjalanan.</p>'}</aside></div>
    <div class="results-actions"><button class="button outline" data-action="edit-first">Ubah jawaban <span aria-hidden="true">↗</span></button><button class="button ghost" data-action="start">Mulai ulang <span aria-hidden="true">↻</span></button></div>
    <p class="disclaimer">Rekomendasi ini berdasarkan ketertarikan pengguna Stravl. Preferensi anggaran dan keamanan tidak memverifikasi biaya atau kondisi destinasi saat ini. Ketersediaan penilaian berbeda untuk setiap tempat.</p>
  </section>`;
  if(!preserveScroll)announce('Rekomendasi siap. Jelajahi hasil berdasarkan aturan atau pengguna serupa.');
}

async function about() {
  if(state.busy)return;
  state.returnTo=state.screen==='about'?state.returnTo:state.screen;
  state.busy=true;loading('Memuat informasi proyek…');
  try{state.project=await api('/api/project');renderAbout();focusMain();}
  catch(e){showError(e,'about');}finally{state.busy=false;main.removeAttribute('aria-busy');}
}

function renderAbout() {
  state.screen='about';
  const {audit:a,evaluation:e}=state.project;
  const names={forward_chaining:'Forward chaining',cbr:'Kasus serupa (CBR)',popularity:'Popularitas (pembanding)'};
  const metrics=[['precision_at_5','Ketepatan','Precision'],['recall_at_5','Cakupan','Recall'],['ndcg_at_5','Kualitas urutan','NDCG']];
  main.innerHTML=`<section class="about wrap fade-in"><button class="button ghost small" data-action="return"><span aria-hidden="true">←</span> Kembali</button><h1>Tentang Tourguider</h1><p class="about-intro"><strong>Tourguider</strong> merupakan proyek mata kuliah <strong>Sistem Berbasis Pengetahuan</strong> yang menerapkan forward chaining dan case-based reasoning (CBR) untuk merekomendasikan destinasi wisata berdasarkan preferensi pengguna. Dataset Stravl digunakan untuk membentuk basis pengetahuan, menelusuri aturan, dan membandingkan hasil rekomendasi.</p>
    <div class="stats"><div class="stat-card"><strong>${number(a.raw_users)}</strong><span>profil pengguna pada dataset awal</span></div><div class="stat-card"><strong>${number(a.destinations)}</strong><span>destinasi wisata dalam katalog</span></div><div class="stat-card"><strong>${number(a.rule_count)}</strong><span>aturan dalam basis pengetahuan</span></div></div>
    <section class="about-card recommendation-methods"><h2>Metode rekomendasi</h2><p class="methods-intro">Tourguider membandingkan dua pendekatan untuk mengolah preferensi wisata.</p><div class="method-overview">
      <article class="method-tile"><div class="method-tile-top"><span class="method-index" aria-hidden="true">01</span><span class="method-kind">Berbasis aturan</span></div><h3>Forward Chaining</h3><p>Jawaban pengguna memicu aturan secara berantai hingga terbentuk kelompok rekomendasi.</p><div class="method-flow" aria-label="Alur forward chaining"><span>Jawaban</span><span aria-hidden="true">→</span><span>Aturan berantai</span><span aria-hidden="true">→</span><span>Rekomendasi</span></div></article>
      <article class="method-tile"><div class="method-tile-top"><span class="method-index" aria-hidden="true">02</span><span class="method-kind">Berbasis kasus</span></div><h3>Case-Based Reasoning (CBR)</h3><p>Mencari hingga 20 pengguna dengan preferensi serupa, lalu mengurutkan destinasi dari respons mereka.</p><div class="method-flow" aria-label="Alur case-based reasoning"><span>Preferensi</span><span aria-hidden="true">→</span><span>Kasus serupa</span><span aria-hidden="true">→</span><span>Rekomendasi</span></div></article>
    </div></section>
    <section class="about-card"><h2>Validasi hasil rekomendasi</h2>${e?`<p>Validasi dilakukan pada ${number(e.evaluated_users)} dari ${number(e.test_users)} pengguna dalam data uji yang memenuhi kriteria evaluasi. Data dibagi berdasarkan pengguna: 80% untuk membangun model dan basis kasus, serta 20% untuk pengujian.</p><p class="validation-lead">Tabel berikut membandingkan lima rekomendasi teratas dari setiap metode. Nilai yang lebih tinggi menunjukkan hasil yang lebih baik pada masing-masing ukuran.</p><p class="table-hint">Geser tabel ke samping untuk melihat seluruh hasil.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Tabel validasi rekomendasi, dapat digeser ke samping"><table class="validation-table"><caption class="sr-only">Perbandingan ketepatan, cakupan, dan kualitas urutan lima rekomendasi teratas</caption><thead><tr><th scope="col">Metode</th>${metrics.map(([,label,term])=>`<th scope="col">${label}<span class="metric-term">${term}</span></th>`).join('')}</tr></thead><tbody>${Object.entries(e.metrics).map(([key,m])=>`<tr><th scope="row">${names[key]}</th>${metrics.map(([metric])=>`<td class="${m[metric]===Math.max(...Object.values(e.metrics).map(v=>v[metric]))?'best':''}">${(m[metric]*100).toLocaleString('id-ID',{minimumFractionDigits:2,maximumFractionDigits:2})}%</td>`).join('')}</tr>`).join('')}</tbody></table></div><dl class="metric-definitions"><div><dt>Ketepatan · Precision</dt><dd>Proporsi dari lima rekomendasi yang memang diberi respons “Ya” oleh pengguna uji.</dd></div><div><dt>Cakupan · Recall</dt><dd>Proporsi seluruh destinasi yang disukai pengguna uji yang berhasil muncul dalam lima rekomendasi.</dd></div><div><dt>Kualitas urutan · NDCG</dt><dd>Menilai penempatan destinasi yang disukai pada lima posisi teratas. Rekomendasi yang relevan di posisi awal mendapat bobot lebih besar.</dd></div></dl><p class="validation-note">Setiap pengguna diuji pada destinasi yang sudah dinilai “Ya” atau “Tidak”, dengan minimal lima kandidat dan satu respons “Ya”. Respons “Mungkin” dan destinasi tanpa penilaian dikeluarkan dari kandidat evaluasi. CBR memakai preferensi yang telah diisi dan mengeluarkan destinasi yang hanya ditolak kasus serupa, sesuai proses konsultasi.</p><p class="validation-note">Hasil ini menggambarkan kemampuan mengurutkan destinasi yang telah dinilai dalam dataset. Pengujian belum mengukur kepuasan perjalanan nyata atau kualitas rekomendasi untuk seluruh katalog.</p>`:'<p>Validasi untuk versi proses ini belum tersedia. Jalankan ulang audit sebelum menggunakan angka evaluasi.</p>'}</section>
    <section class="about-card"><h2>Pembersihan data dan batasan</h2><ul><li>${number(a.duplicate_records_removed)} rekaman identik digabungkan sebelum pembagian pengguna.</li><li>${number(a.repeated_swipes_removed_after_record_dedup)} pengulangan swipe dihapus dan ${number(a.conflicting_pairs_removed_after_record_dedup)} pasangan berlabel bertentangan dikeluarkan setelah penggabungan rekaman.</li><li>${number(a.empty_records_excluded)} rekaman tanpa interaksi bersih tidak dipakai sebagai kasus.</li><li>Kolom tanpa penjelasan, rating lama, dan rekomendasi algoritma asal tidak digunakan sebagai fitur.</li><li>Aturan terbukti setara dengan pohon sumber pada ${number(a.rule_equivalence_records)} profil bersih. Aturan merupakan pola data, bukan pengetahuan pakar pariwisata.</li><li>Data merekam ketertarikan, bukan kunjungan atau kepuasan nyata. Biaya dan keamanan aktual tidak tersedia.</li></ul><div class="source-links"><a href="https://github.com/Stravl/Stravl-Data" target="_blank" rel="noopener">Dataset Stravl ↗</a><a href="https://link.springer.com/article/10.1186/s44147-023-00315-4" target="_blank" rel="noopener">Artikel acuan metode ↗</a><a href="https://styles.refero.design/style/15d10d6c-1844-46c6-ae69-c99a56e6ad41" target="_blank" rel="noopener">Referensi visual ↗</a></div></section>
    <button class="button" data-action="start">Mulai konsultasi ${arrow}</button>
  </section>`;
}

document.addEventListener('change', event=>{
  if(event.target.id==='unknown-answer' && event.target.checked)main.querySelectorAll('[name="answer"]').forEach(i=>i.checked=false);
  if(event.target.name==='answer' && event.target.checked)main.querySelector('#unknown-answer').checked=false;
  if(event.target.name==='answer'||event.target.id==='unknown-answer'){
    state.selected=[...main.querySelectorAll('[name="answer"]:checked')].map(i=>i.value);
    state.unknown=main.querySelector('#unknown-answer').checked;
  }
  const error=main.querySelector('#field-error');if(error)error.hidden=true;
});
document.addEventListener('click', async event=>{
  const el=event.target.closest('[data-action]');if(!el||state.busy)return;
  if(window.location?.protocol==='file:'){window.location.href='http://127.0.0.1:8765/';return;}
  const action=el.dataset.action;
  if(action==='home'){home();focusMain();}
  if(action==='start')await start();
  if(action==='about')await about();
  if(action==='back'){const last=state.consultation.summary.at(-1);if(last)await edit(last.field);else{home();focusMain();}}
  if(action==='edit')await edit(el.dataset.field);
  if(action==='edit-first')await edit(state.consultation.summary[0].field);
  if(action==='retry-answer')await sendAnswers(state.retryAnswers);
  if(action==='tab'){state.tab=el.dataset.tab;renderResults(true);main.querySelector(`#tab-${state.tab}`).focus({preventScroll:true});}
  if(action==='return'){if(state.returnTo==='results'){renderResults();focusMain();}else if(state.returnTo==='consultation'){renderConsultation();focusMain();}else{home();focusMain();}}
});
document.addEventListener('keydown', event=>{
  if(event.target.getAttribute('role')==='tab' && ['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
    event.preventDefault();state.tab=event.key==='Home'?'rules':event.key==='End'?'cbr':state.tab==='rules'?'cbr':'rules';renderResults(true);main.querySelector(`#tab-${state.tab}`).focus({preventScroll:true});
  }
});
if(window.location?.protocol==='file:'){
  state.screen='local-file';
  main.innerHTML='<section class="error-box"><h1>Buka Tourguider melalui server lokal.</h1><p>Jalankan run.command di folder proyek, lalu buka alamat di bawah agar konsultasi terhubung dengan mesin rekomendasi.</p><a class="button" href="http://127.0.0.1:8765/">Buka Tourguider ↗</a></section>';
}else{home();}
