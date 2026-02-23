/**
 * DSA Grader — Main Page Logic.
 * Xử lý: File upload (drag & drop), form submit, polling job status.
 */

document.addEventListener("DOMContentLoaded", () => {
  // ═══════════════════════════════════════════
  //  DOM Elements
  // ═══════════════════════════════════════════
  const gradeForm = document.getElementById("grade-form");
  const uploadZone = document.getElementById("upload-zone");
  const fileInput = document.getElementById("files");
  const fileListContainer = document.getElementById("file-list-container");
  const fileList = document.getElementById("file-list");
  const fileCount = document.getElementById("file-count");
  const submitBtn = document.getElementById("submit-btn");
  const studentIdInput = document.getElementById("student-id");
  const studentNameInput = document.getElementById("student-name");
  const topicSelect = document.getElementById("topic-select");

  // Loading overlay
  const loadingOverlay = document.getElementById("loading-overlay");
  const progressBar = document.getElementById("loading-progress-bar");
  const loadingMessage = document.getElementById("loading-message");
  const progVal = document.getElementById("prog-val");

  // Confirm modal
  const confirmModal = document.getElementById("custom-confirm");
  const confirmMsg = document.getElementById("confirm-msg");
  const btnConfirmYes = document.getElementById("confirm-yes");
  const btnConfirmCancel = document.getElementById("confirm-cancel");
  let confirmCallback = null;

  // ═══════════════════════════════════════════
  //  Submit Button State
  // ═══════════════════════════════════════════

  function updateSubmitButton() {
    const hasFiles = fileInput.files.length > 0;
    submitBtn.disabled = !hasFiles;
    submitBtn.innerHTML = hasFiles
      ? '<i class="fa-solid fa-paper-plane"></i><span>Nộp bài & Chấm điểm</span>'
      : '<i class="fa-solid fa-cloud-arrow-up"></i><span>Chọn file để nộp</span>';
  }

  // ═══════════════════════════════════════════
  //  File Upload — Drag & Drop
  // ═══════════════════════════════════════════

  uploadZone.addEventListener("click", () => fileInput.click());

  // Prevent default browser drag behaviors
  ["dragenter", "dragover", "dragleave", "drop"].forEach((event) => {
    uploadZone.addEventListener(event, (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
  });

  // Drag visual feedback
  uploadZone.addEventListener("dragenter", () => uploadZone.classList.add("dragover"));
  uploadZone.addEventListener("dragover", () => uploadZone.classList.add("dragover"));
  uploadZone.addEventListener("dragleave", (e) => {
    if (!uploadZone.contains(e.relatedTarget)) {
      uploadZone.classList.remove("dragover");
    }
  });

  // Drop handler
  uploadZone.addEventListener("drop", (e) => {
    uploadZone.classList.remove("dragover");
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      fileInput.files = files;
      renderStagedFiles(files);
      Toast.info("File đã nhận", `Đã nhận ${files.length} file.`);
    }
  });

  fileInput.addEventListener("change", () => renderStagedFiles(fileInput.files));

  // ═══════════════════════════════════════════
  //  File List Rendering
  // ═══════════════════════════════════════════

  const ALLOWED_EXTENSIONS = [".py", ".zip", ".rar"];

  function renderStagedFiles(files) {
    const validFiles = Array.from(files).filter((f) => {
      const name = f.name.toLowerCase();
      return ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
    });

    if (validFiles.length === 0 && files.length > 0) {
      Toast.warning("Sai định dạng", "Chỉ hỗ trợ file .py, .zip, .rar");
      return;
    }

    fileList.innerHTML = "";
    fileCount.textContent = validFiles.length;
    fileListContainer.style.display = validFiles.length > 0 ? "block" : "none";
    updateSubmitButton();

    validFiles.forEach((file, index) => {
      const div = document.createElement("div");
      div.className = "dev-file-item";
      div.style.animationDelay = `${index * 0.05}s`;

      const ext = file.name.split(".").pop().toLowerCase();
      const isPython = ext === "py";

      div.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.75rem; min-width:0;">
          <i class="fa-${isPython ? "brands fa-python" : "solid fa-file-zipper"}"
             style="color:${isPython ? "#3776AB" : "#f0db4f"}; font-size:1.1rem;"></i>
          <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${file.name}</span>
          <span style="font-size:0.7rem; color:var(--text-muted); flex-shrink:0;">${formatFileSize(file.size)}</span>
        </div>
        <button type="button" class="remove-btn" aria-label="Xóa file ${file.name}"
                style="background:none; border:none; color:var(--text-muted); cursor:pointer; padding:0.25rem;">
          <i class="fa-solid fa-xmark"></i>
        </button>
      `;

      // Remove individual file
      div.querySelector(".remove-btn").addEventListener("click", (ev) => {
        ev.stopPropagation();
        showConfirm(`Bạn có chắc muốn xóa file "${file.name}"?`, () => {
          const dt = new DataTransfer();
          Array.from(fileInput.files)
            .filter((f) => f.name !== file.name)
            .forEach((f) => dt.items.add(f));
          fileInput.files = dt.files;
          renderStagedFiles(fileInput.files);
          Toast.success("Đã xóa", `File "${file.name}" đã được gỡ bỏ.`);
        });
      });

      fileList.appendChild(div);
    });
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  // Clear all files
  document.getElementById("clear-files-btn").addEventListener("click", () => {
    if (fileInput.files.length === 0) return;
    showConfirm("Xóa tất cả file?", () => {
      fileInput.value = "";
      renderStagedFiles([]);
      Toast.success("Đã dọn sạch", "Danh sách file đã được làm mới.");
    });
  });

  // ═══════════════════════════════════════════
  //  Form Submit — Grading Pipeline
  // ═══════════════════════════════════════════

  const LOADING_MESSAGES = [
    "Đang khởi tạo hệ thống...",
    "Kiểm tra tính toàn vẹn bài nộp...",
    "Đang phân tích bài làm...",
    "Đang đánh giá thuật toán...",
    "Tổng hợp báo cáo kết quả...",
    "Hoàn tất đánh giá...",
  ];

  gradeForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Build student info
    const studentId = studentIdInput.value.trim();
    const studentName = studentNameInput.value.trim();
    const fullStudentInfo =
      studentId && studentName
        ? `${studentId} - ${studentName}`
        : studentId || studentName || "Ẩn danh";

    // Show loading overlay
    showLoading();

    // Build form data
    const formData = new FormData();
    Array.from(fileInput.files).forEach((f) => formData.append("files", f));
    formData.append("topic", topicSelect.value);
    formData.append("student_name", fullStudentInfo);

    // Fake progress animation
    let currentProg = 0;
    let msgIndex = 0;

    const progressInterval = setInterval(() => {
      if (currentProg < 90) {
        currentProg += (95 - currentProg) / 25;
        setProgress(currentProg);

        const newMsgIndex = Math.floor(currentProg / 18);
        if (newMsgIndex !== msgIndex && newMsgIndex < LOADING_MESSAGES.length) {
          msgIndex = newMsgIndex;
          loadingMessage.textContent = LOADING_MESSAGES[msgIndex];
        }
      }
    }, 500);

    try {
      // POST /grade → get job_id
      const res = await fetch("/grade", { method: "POST", body: formData });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Server error");
      }

      const { job_id } = await res.json();

      // Poll for completion
      await pollJobStatus(job_id, progressInterval);

    } catch (err) {
      clearInterval(progressInterval);
      hideLoading();
      Toast.error("Lỗi nộp bài", err.message);
    }
  });

  /**
   * Poll job status cho đến khi completed hoặc failed.
   */
  async function pollJobStatus(jobId, progressInterval) {
    try {
      const res = await fetch(`/api/job/${jobId}`);
      if (!res.ok) throw new Error("Không thể theo dõi job.");
      const data = await res.json();

      if (data.status === "completed") {
        clearInterval(progressInterval);
        setProgress(100);
        loadingMessage.textContent = "Hoàn tất! Đang chuyển hướng...";

        setTimeout(() => {
          sessionStorage.setItem("gradingResults", JSON.stringify(data));
          window.location.href = "/results";
        }, 800);

      } else if (data.status === "failed") {
        throw new Error(data.error || "Quá trình chấm điểm gặp lỗi.");

      } else {
        // Đang xử lý → poll lại sau 2s
        if (data.status === "processing") {
          loadingMessage.textContent = "Đang đánh giá bài làm của bạn...";
        }
        setTimeout(() => pollJobStatus(jobId, progressInterval), 2000);
      }

    } catch (err) {
      clearInterval(progressInterval);
      hideLoading();
      Toast.error("Lỗi xử lý", err.message);
    }
  }

  // ═══════════════════════════════════════════
  //  Loading Overlay Helpers
  // ═══════════════════════════════════════════

  function showLoading() {
    loadingOverlay.style.display = "flex";
    loadingOverlay.style.opacity = "0";
    setProgress(0);
    setTimeout(() => (loadingOverlay.style.opacity = "1"), 10);
  }

  function hideLoading() {
    loadingOverlay.style.display = "none";
  }

  function setProgress(value) {
    progressBar.style.width = value + "%";
    progVal.textContent = Math.floor(value) + "%";
  }

  // ═══════════════════════════════════════════
  //  Confirm Modal
  // ═══════════════════════════════════════════

  function showConfirm(msg, callback) {
    confirmMsg.textContent = msg;
    confirmCallback = callback;
    confirmModal.style.display = "flex";
  }

  btnConfirmCancel.addEventListener("click", () => {
    confirmModal.style.display = "none";
    confirmCallback = null;
  });

  btnConfirmYes.addEventListener("click", () => {
    if (confirmCallback) confirmCallback();
    confirmModal.style.display = "none";
    confirmCallback = null;
  });

  confirmModal.addEventListener("click", (e) => {
    if (e.target === confirmModal) {
      confirmModal.style.display = "none";
      confirmCallback = null;
    }
  });

  // ═══════════════════════════════════════════
  //  Rules Modal
  // ═══════════════════════════════════════════

  const rulesBtn = document.getElementById("rules-btn");
  const rulesModal = document.getElementById("rules-modal");

  if (rulesBtn && rulesModal) {
    rulesBtn.addEventListener("click", (e) => {
      e.preventDefault();
      rulesModal.style.display = "flex";
    });

    const closeRules = () => (rulesModal.style.display = "none");

    document.getElementById("rules-close")?.addEventListener("click", closeRules);
    document.getElementById("rules-done")?.addEventListener("click", closeRules);

    rulesModal.addEventListener("click", (e) => {
      if (e.target === rulesModal) closeRules();
    });
  }
});
