/**
 * DSA Grader — Results Page Logic V3
 * Hien thi ket qua cham diem voi rubric dong tu ngan hang bai tap.
 */

// ═══════════════════════════════════════════
//  State
// ═══════════════════════════════════════════
let allResults = [];
let statusFilter = "all";
let searchKeyword = "";

// ═══════════════════════════════════════════
//  Init
// ═══════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
  const raw = sessionStorage.getItem("gradingResults");
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      allResults = parsed.results || [];
      renderSummary(parsed.summary || {});
    } catch (e) {
      console.error("Parse error:", e);
    }
  }
  renderResults();
  bindFilters();
});

// ═══════════════════════════════════════════
//  Summary Dashboard
// ═══════════════════════════════════════════
function renderSummary(summary) {
  const section = document.getElementById("summary-section");
  if (!section || !summary.total_files) return;

  section.innerHTML = `
    <div class="dev-stat-item">
      <div class="dev-stat-label">Tong so bai</div>
      <div class="dev-stat-value">${summary.total_files || 0}</div>
    </div>
    <div class="dev-stat-item">
      <div class="dev-stat-label">Diem trung binh</div>
      <div class="dev-stat-value">${summary.avg_score != null ? summary.avg_score : "—"}</div>
    </div>
    <div class="dev-stat-item">
      <div class="dev-stat-label">Thoi gian xu ly</div>
      <div class="dev-stat-value">${summary.total_time || "—"}</div>
    </div>
    <div class="dev-stat-item">
      <div class="dev-stat-label">Da luu</div>
      <div class="dev-stat-value">${summary.saved_to_db || 0} bai</div>
    </div>
  `;
}

// ═══════════════════════════════════════════
//  Render Result Cards
// ═══════════════════════════════════════════
function renderResults() {
  const container = document.getElementById("results-container");
  if (!container) return;

  let filtered = allResults;

  if (statusFilter !== "all") {
    filtered = filtered.filter(
      (r) => (r.status || "").toUpperCase() === statusFilter.toUpperCase()
    );
  }

  if (searchKeyword) {
    const kw = searchKeyword.toLowerCase();
    filtered = filtered.filter(
      (r) =>
        (r.filename || "").toLowerCase().includes(kw) ||
        (r.algorithms || "").toLowerCase().includes(kw)
    );
  }

  if (!filtered.length) {
    container.innerHTML = `
      <div style="text-align:center; padding:3rem; color:var(--text-muted);">
        <i class="fa-solid fa-inbox" style="font-size:2rem; margin-bottom:1rem; display:block;"></i>
        <p>Chua co ket qua nao.</p>
      </div>`;
    return;
  }

  container.innerHTML = filtered.map((r, i) => buildCard(r, i)).join("");
}

// ═══════════════════════════════════════════
//  Card Builder
// ═══════════════════════════════════════════
function buildCard(r, index = 0) {
  const card = document.createElement("div");
  card.className = "pipeline-card";
  card.style.animation = `fadeInUp 0.4s ease forwards`;
  card.style.animationDelay = `${index * 0.08}s`;
  card.style.opacity = "0";

  const hasRubric = r.has_rubric === true;
  const totalScore = r.total_score;
  const hasScore = totalScore != null && hasRubric;

  // Status
  const st = getStatusInfo(r.status, hasScore);

  // Score display
  const scoreColor = hasScore
    ? totalScore >= 80 ? "var(--brand-success)" : totalScore >= 50 ? "var(--brand-warning)" : "var(--brand-danger)"
    : "var(--text-muted)";

  const scoreDisplay = hasScore ? totalScore : "—";

  // Filename & student
  const filename = (r.filename || "unknown").split(" | ").pop() || r.filename;
  const student = (r.filename || "").includes(" | ")
    ? r.filename.split(" | ")[0]
    : "Khong ro";

  // Grading label
  const gradingLabel = hasRubric
    ? '<span style="color:var(--brand-success); font-size:0.75rem; margin-left:6px;"><i class="fa-solid fa-circle-check"></i> Co tieu chi</span>'
    : '<span style="color:var(--brand-warning); font-size:0.75rem; margin-left:6px;"><i class="fa-solid fa-triangle-exclamation"></i> Chua cap nhat tieu chi</span>';

  // Reasoning & improvement
  const reasoning = r.reasoning || "Khong co nhan xet.";
  const improvement = r.improvement || "Khong co goi y.";
  const strengths = r.strengths || "";
  const weaknesses = r.weaknesses || "";
  const complexityAnalysis = r.complexity_analysis || "";

  card.innerHTML = `
    <div class="pipeline-header" onclick="this.parentElement.classList.toggle('expanded')">
      <div style="display:flex; align-items:center; gap:1rem; flex:1; min-width:0;">
        <span class="pipeline-status ${st.cls}">
          <i class="fa-solid ${st.icon}"></i>${st.text}
        </span>
        <div style="display:flex; flex-direction:column; min-width:0;">
          <span style="font-weight:600; color:var(--text-bright); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
            ${filename}
          </span>
          <span style="font-size:0.8rem; color:var(--text-muted);">
            <i class="fa-regular fa-user" style="margin-right:4px;"></i>${student}
          </span>
        </div>
      </div>
      <div style="display:flex; align-items:center; gap:2rem; margin-left:auto;">
        <div style="text-align:right;" class="algo-info">
          <div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:2px;">Thuat toan</div>
          <div style="font-size:0.9rem; font-weight:500; color:var(--brand-primary);">
            <i class="fa-solid fa-puzzle-piece" style="margin-right:6px;"></i>${r.algorithms || "N/A"}
          </div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:0.8rem; color:var(--text-muted); margin-bottom:2px;">Diem so</div>
          <div style="font-family:var(--font-code); font-size:1.1rem; font-weight:700; color:${scoreColor};">
            ${scoreDisplay}<span style="font-size:0.7rem; color:var(--text-muted);">${hasScore ? '/100' : ''}</span>
            ${gradingLabel}
          </div>
        </div>
        <i class="fa-solid fa-chevron-down pipeline-toggle-icon"></i>
      </div>
    </div>

    <div class="pipeline-body">
      <!-- Score Sidebar -->
      <div>
        <div class="score-display">
          <div class="score-box-dev" style="border-color:${scoreColor};">
            <div class="val" style="color:${scoreColor};">${scoreDisplay}</div>
            <div class="max">${hasScore ? '/ 100 diem' : 'Chua co diem'}</div>
          </div>

          ${hasScore ? `
            <div style="display:grid; gap:6px;">
              ${buildScoreRow("Logic", r.breakdown?.logic_score, 40)}
              ${buildScoreRow("Thuat toan", r.breakdown?.algorithm_score, 40)}
              ${buildScoreRow("Code Style", r.breakdown?.style_score, 10)}
              ${buildScoreRow("Toi uu", r.breakdown?.optimization_score, 10)}
            </div>
          ` : `
            <div style="background:var(--bg-input); padding:0.75rem; border-radius:6px; border:1px dashed var(--brand-warning); margin-top:0.5rem;">
              <p style="font-size:0.8rem; color:var(--brand-warning); margin:0; text-align:center;">
                <i class="fa-solid fa-triangle-exclamation" style="margin-right:4px;"></i>
                He thong chua cap nhat tieu chi.<br>
                He thong chi phan tich, chua cho diem.
              </p>
            </div>
          `}

          <div style="margin-top:0.75rem; display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-muted);">
            <span>Complexity:</span>
            <span style="font-family:var(--font-code); color:var(--text-bright);">${r.complexity || 0}</span>
          </div>
        </div>
      </div>

      <!-- Feedback Content -->
      <div style="flex:1; min-width:0;">

        ${strengths || weaknesses ? `
        <!-- Diem manh / Diem yeu -->
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; margin-bottom:1.25rem;">
          ${strengths ? `
          <div style="background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.2); padding:0.75rem; border-radius:6px;">
            <h5 style="font-size:0.8rem; color:var(--brand-success); margin-bottom:0.4rem;">
              <i class="fa-solid fa-thumbs-up" style="margin-right:4px;"></i>Diem manh
            </h5>
            <p style="font-size:0.82rem; color:var(--text-main); margin:0; line-height:1.5;">${strengths}</p>
          </div>
          ` : ''}
          ${weaknesses ? `
          <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.2); padding:0.75rem; border-radius:6px;">
            <h5 style="font-size:0.8rem; color:var(--brand-danger); margin-bottom:0.4rem;">
              <i class="fa-solid fa-thumbs-down" style="margin-right:4px;"></i>Can cai thien
            </h5>
            <p style="font-size:0.82rem; color:var(--text-main); margin:0; line-height:1.5;">${weaknesses}</p>
          </div>
          ` : ''}
        </div>
        ` : ''}

        <!-- Nhan xet chi tiet -->
        <div style="margin-bottom:1.25rem;">
          <h4 style="font-size:0.95rem; font-weight:600; color:var(--text-bright); margin-bottom:0.75rem; display:flex; align-items:center;">
            <i class="fa-solid fa-pen-to-square" style="margin-right:8px; color:${scoreColor}"></i>
            Đánh giá của Giảng viên
          </h4>
          <div class="feedback-log" style="border-left:3px solid ${scoreColor};">
            <p style="white-space:pre-line; margin:0;">${reasoning}</p>
          </div>
        </div>

        ${complexityAnalysis ? `
        <!-- Phan tich do phuc tap -->
        <div style="margin-bottom:1.25rem;">
          <h4 style="font-size:0.95rem; font-weight:600; color:var(--text-bright); margin-bottom:0.75rem; display:flex; align-items:center;">
            <i class="fa-solid fa-gauge-high" style="margin-right:8px; color:var(--brand-info);"></i>
            Phân tích độ phức tạp
          </h4>
          <div class="feedback-log">
            <p style="margin:0; white-space:pre-line;">${complexityAnalysis}</p>
          </div>
        </div>
        ` : ''}

        <!-- Goi y cai thien -->
        <div>
          <h4 style="font-size:0.95rem; font-weight:600; color:var(--text-bright); margin-bottom:0.75rem; display:flex; align-items:center;">
            <i class="fa-solid fa-lightbulb" style="margin-right:8px; color:var(--brand-primary)"></i>
            Gợi ý cải thiện
          </h4>
          <div class="feedback-log" style="background:rgba(13, 148, 136, 0.05); border:1px dashed var(--brand-primary);">
            <p style="margin:0; white-space:pre-line;">${improvement}</p>
          </div>
        </div>

      </div>
    </div>
  `;

  return card.outerHTML;
}

// ═══════════════════════════════════════════
//  Helpers
// ═══════════════════════════════════════════
function getStatusInfo(status, hasScore) {
  if (!hasScore) {
    return { cls: "status-pending", icon: "fa-clock", text: "Chua cap nhat" };
  }
  switch ((status || "").toUpperCase()) {
    case "PASS": return { cls: "status-ac", icon: "fa-circle-check", text: "Dat" };
    case "FAIL": return { cls: "status-wa", icon: "fa-circle-xmark", text: "Chua dat" };
    case "FLAG": return { cls: "status-fl", icon: "fa-flag", text: "Nghi van" };
    default: return { cls: "status-pending", icon: "fa-clock", text: "Cho xu ly" };
  }
}

function buildScoreRow(label, value, max) {
  if (value == null) return '';

  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  const color =
    pct >= 80 ? "var(--brand-success)" :
      pct >= 50 ? "var(--brand-warning)" :
        "var(--brand-danger)";

  return `
    <div style="background:var(--bg-input); padding:0.5rem 0.6rem; border-radius:6px; border:1px solid var(--border-pro);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
        <span style="font-size:0.7rem; color:var(--text-muted);">${label}</span>
        <span style="font-size:0.8rem; font-weight:700; color:${color};">${value}/${max}</span>
      </div>
      <div style="height:3px; background:var(--border-active); border-radius:99px; overflow:hidden;">
        <div style="height:100%; width:${pct}%; background:${color}; border-radius:99px;"></div>
      </div>
    </div>
  `;
}

function bindFilters() {
  document.getElementById("status-filter").addEventListener("change", (e) => {
    statusFilter = e.target.value;
    renderResults();
  });
  document.getElementById("search-filter").addEventListener("input", (e) => {
    searchKeyword = e.target.value.trim();
    renderResults();
  });
}
