/* ===========================
   APCS Practice Platform
   Main JavaScript
   =========================== */

document.addEventListener('DOMContentLoaded', function () {

    // ── Option click highlight (practice) ──────────────────────────────────
    document.querySelectorAll('.option-label').forEach(label => {
        label.addEventListener('click', function () {
            const group = this.closest('.options-group, form');
            if (group) {
                group.querySelectorAll('.option-label').forEach(l => {
                    l.style.fontWeight = 'normal';
                });
            }
            this.style.fontWeight = 'bold';
        });
    });

    // ── Favorite toggle (AJAX) ──────────────────────────────────────────────
    document.querySelectorAll('.toggle-fav').forEach(btn => {
        btn.addEventListener('click', function () {
            const url = this.dataset.url;
            const csrfToken = getCookie('csrftoken');
            fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
            })
            .then(r => r.json())
            .then(data => {
                const icon = this.querySelector('i');
                if (data.status === 'added') {
                    icon.classList.replace('bi-star', 'bi-star-fill');
                    this.classList.add('btn-warning');
                    this.classList.remove('btn-outline-warning');
                } else if (data.status === 'removed') {
                    icon.classList.replace('bi-star-fill', 'bi-star');
                    this.classList.remove('btn-warning');
                    this.classList.add('btn-outline-warning');
                    // Optionally remove card from list
                    const card = this.closest('.col-12');
                    if (card) {
                        card.style.transition = 'opacity 0.3s';
                        card.style.opacity = '0';
                        setTimeout(() => card.remove(), 300);
                    }
                }
            })
            .catch(err => console.error('Favorite toggle error:', err));
        });
    });

    // ── Confirm delete dialogs ──────────────────────────────────────────────
    document.querySelectorAll('[data-confirm]').forEach(el => {
        el.addEventListener('click', function (e) {
            const msg = this.dataset.confirm || '確定要執行此操作嗎？';
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });

    // ── Auto-dismiss flash messages after 4 seconds ─────────────────────────
    document.querySelectorAll('.alert.alert-dismissible').forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 4000);
    });

    // ── Form select: add Bootstrap class if missing ─────────────────────────
    document.querySelectorAll('select:not(.form-select):not(.btn-check)').forEach(sel => {
        sel.classList.add('form-select');
    });
});

// ── CSRF cookie helper ────────────────────────────────────────────────────────
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
