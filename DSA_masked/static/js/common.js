/**
 * DSA Grader — Common Utilities.
 * Theme switching & global cleanup.
 */

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
});

/**
 * Khởi tạo theme từ localStorage và gắn toggle handler.
 */
function initTheme() {
    const savedTheme = localStorage.getItem("dsa-theme") || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);

    const toggleBtn = document.getElementById("theme-toggle");
    if (!toggleBtn) return;

    updateToggleIcon(toggleBtn, savedTheme);

    toggleBtn.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme");
        const next = current === "light" ? "dark" : "light";

        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("dsa-theme", next);
        updateToggleIcon(toggleBtn, next);
    });
}

/**
 * Cập nhật icon theme toggle.
 * Dark mode → hiển thị Sun icon (chuyển sang light).
 * Light mode → hiển thị Moon icon (chuyển sang dark).
 */
function updateToggleIcon(btn, theme) {
    const icon = btn.querySelector("i");
    if (!icon) return;
    icon.className = theme === "light" ? "fa-solid fa-moon" : "fa-solid fa-sun";
}
