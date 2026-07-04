/* ===========================
   APCS Practice Platform
   Exam Timer & Auto-save
   =========================== */

(function () {
    'use strict';

    // ── Timer ─────────────────────────────────────────────────────────────────
    let secondsLeft = typeof timeRemaining !== 'undefined' ? timeRemaining : 1800;
    const timerEl = document.getElementById('timer');

    function updateTimer() {
        if (!timerEl) return;
        const m = Math.floor(secondsLeft / 60);
        const s = secondsLeft % 60;
        timerEl.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');

        if (secondsLeft <= 300) {
            timerEl.classList.add('text-danger');
            timerEl.classList.remove('text-dark');
        }
        if (secondsLeft <= 60) {
            timerEl.parentElement.classList.add('bg-danger', 'text-white');
        }
        if (secondsLeft <= 0) {
            clearInterval(timerInterval);
            autoSubmit();
        } else {
            secondsLeft--;
        }
    }

    const timerInterval = setInterval(updateTimer, 1000);
    updateTimer();

    // ── Auto Submit ───────────────────────────────────────────────────────────
    function autoSubmit() {
        alert('時間到！系統將自動交卷。');
        const form = document.getElementById('submitForm');
        if (form) form.submit();
    }

    function confirmSubmit() {
        const total = document.querySelectorAll('.options-group').length;
        const answered = document.querySelectorAll('.exam-answer:checked').length;
        const unanswered = total - answered;
        let msg = '確定要交卷嗎？';
        if (unanswered > 0) {
            msg = `還有 ${unanswered} 題未作答，確定要交卷嗎？`;
        }
        if (confirm(msg)) {
            document.getElementById('submitForm').submit();
        }
    }
    window.confirmSubmit = confirmSubmit;

    // ── AJAX Answer Save ──────────────────────────────────────────────────────
    function getCookie(name) {
        let val = null;
        if (document.cookie) {
            document.cookie.split(';').forEach(c => {
                c = c.trim();
                if (c.startsWith(name + '=')) val = decodeURIComponent(c.slice(name.length + 1));
            });
        }
        return val;
    }

    function saveAnswer(questionId, answer, saveUrl, navId) {
        const formData = new FormData();
        formData.append('question_id', questionId);
        formData.append('answer', answer);

        fetch(saveUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
            body: formData,
        })
        .then(r => r.json())
        .then(data => {
            // Mark nav button as answered
            if (data.status === 'saved' && navId) {
                const navBtn = document.getElementById(navId);
                if (navBtn) navBtn.classList.add('answered');
            }
        })
        .catch(err => console.warn('Save answer error:', err));
    }

    // Restore from localStorage
    function restoreAnswers() {
        const key = 'exam_answers_' + (typeof sessionPk !== 'undefined' ? sessionPk : '');
        const stored = JSON.parse(localStorage.getItem(key) || '{}');
        Object.entries(stored).forEach(([qid, ans]) => {
            const radio = document.querySelector(`input[name="answer_${qid}"][value="${ans}"]`);
            if (radio) {
                radio.checked = true;
                const navId = radio.dataset.navId;
                if (navId) document.getElementById(navId)?.classList.add('answered');
            }
        });
    }

    // Attach listeners to answer radios
    document.querySelectorAll('.exam-answer').forEach(radio => {
        radio.addEventListener('change', function () {
            const qid = this.dataset.questionId;
            const ans = this.value;
            const saveUrl = this.dataset.saveUrl;
            const navId = this.dataset.navId;

            // LocalStorage backup
            const key = 'exam_answers_' + (typeof sessionPk !== 'undefined' ? sessionPk : '');
            const stored = JSON.parse(localStorage.getItem(key) || '{}');
            stored[qid] = ans;
            localStorage.setItem(key, JSON.stringify(stored));

            saveAnswer(qid, ans, saveUrl, navId);
        });
    });

    restoreAnswers();

    // Clear storage after submit
    document.getElementById('submitForm')?.addEventListener('submit', function () {
        const key = 'exam_answers_' + (typeof sessionPk !== 'undefined' ? sessionPk : '');
        localStorage.removeItem(key);
    });

    // ── Anti-cheat ────────────────────────────────────────────────────────────
    if (typeof antiCheat !== 'undefined' && antiCheat) {
        let cheatCount = 0;
        const MAX_WARNINGS = typeof maxWarnings !== 'undefined' ? maxWarnings : 3;
        let cooldown = false;   // prevent double-firing from blur + visibilitychange

        function triggerAntiCheat() {
            if (cooldown) return;
            cooldown = true;
            setTimeout(() => { cooldown = false; }, 800);

            cheatCount++;

            // Update modal counters
            const countEl = document.getElementById('cheatCountDisplay');
            const maxEl   = document.getElementById('cheatMaxDisplay');
            if (countEl) countEl.textContent = cheatCount;
            if (maxEl)   maxEl.textContent   = MAX_WARNINGS;

            // Show modal
            const modalEl = document.getElementById('antiCheatModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl)
                           || new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: false });
                modal.show();
            }

            // Record on server (fire-and-forget)
            if (typeof recordCheatUrl !== 'undefined') {
                fetch(recordCheatUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                }).catch(() => {});
            }

            // Auto-submit when max reached
            if (cheatCount >= MAX_WARNINGS) {
                document.getElementById('cheatFinalWarning')?.classList.remove('d-none');
                document.getElementById('cheatModalFooter')?.classList.add('d-none');
                setTimeout(() => {
                    const storageKey = 'exam_answers_' + (typeof sessionPk !== 'undefined' ? sessionPk : '');
                    localStorage.removeItem(storageKey);
                    document.getElementById('submitForm')?.submit();
                }, 3000);
            }
        }

        // Tab switch (visibility API)
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) triggerAntiCheat();
        });

        // Window blur: catches switching to another app without hiding the tab
        window.addEventListener('blur', function () {
            if (!document.hidden) triggerAntiCheat();
        });
    }

})();
