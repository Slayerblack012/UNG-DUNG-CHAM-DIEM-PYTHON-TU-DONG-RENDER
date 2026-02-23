/**
 * DSA Grader — Toast Notification Service.
 * Hiển thị thông báo chuyên nghiệp thay vì alert().
 */

// Đảm bảo DOM ready trước khi thao tác
document.addEventListener("DOMContentLoaded", () => {
    if (!document.getElementById("toast-container")) {
        const container = document.createElement("div");
        container.id = "toast-container";
        document.body.appendChild(container);
    }
});

const Toast = {
    // Icon mapping theo loại thông báo
    icons: {
        success: "fa-check-circle",
        error: "fa-xmark-circle",
        info: "fa-circle-info",
        warning: "fa-triangle-exclamation",
    },

    /**
     * Hiển thị thông báo toast.
     * @param {string} type     - 'success' | 'error' | 'info' | 'warning'
     * @param {string} title    - Tiêu đề
     * @param {string} message  - Nội dung chi tiết
     * @param {number} duration - Thời gian hiển thị (ms), mặc định 4000
     */
    show(type, title, message, duration = 4000) {
        const container = document.getElementById("toast-container");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = `toast-item toast-${type}`;

        const iconClass = this.icons[type] || this.icons.info;

        toast.innerHTML = `
      <div class="toast-icon">
        <i class="fa-solid ${iconClass}"></i>
      </div>
      <div class="toast-content">
        <div class="toast-title">${title}</div>
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close" aria-label="Đóng">
        <i class="fa-solid fa-xmark"></i>
      </button>
      <div class="toast-progress">
        <div class="toast-progress-bar" style="background-color: var(--toast-color-${type})"></div>
      </div>
    `;

        // Close button handler
        toast.querySelector(".toast-close").addEventListener("click", () => {
            dismissToast(toast, container);
        });

        container.appendChild(toast);

        // Trigger slide-in animation
        requestAnimationFrame(() => toast.classList.add("show"));

        // Auto dismiss
        if (duration > 0) {
            setTimeout(() => dismissToast(toast, container), duration);
        }
    },

    // ── Shortcut methods ──
    success(title, message) { this.show("success", title, message); },
    error(title, message) { this.show("error", title, message, 6000); },
    info(title, message) { this.show("info", title, message); },
    warning(title, message) { this.show("warning", title, message, 5000); },
};

/**
 * Dismiss animation rồi xóa khỏi DOM.
 * @param {HTMLElement} toast
 * @param {HTMLElement} container
 */
function dismissToast(toast, container) {
    if (!toast || toast.classList.contains("hide")) return;

    toast.classList.remove("show");
    toast.classList.add("hide");

    setTimeout(() => {
        if (container && container.contains(toast)) {
            toast.remove();
        }
    }, 400);
}

// Expose globally
window.Toast = Toast;
