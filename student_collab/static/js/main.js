/* ═══════════════════════════════════════════════
   CollabHub — main.js
   ═══════════════════════════════════════════════ */

// ── Modal ──────────────────────────────────────
const overlay = document.getElementById('modal-overlay');

function openModal() {
    if (!overlay) return;
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
    const firstInput = overlay.querySelector('input, textarea, select');
    if (firstInput) setTimeout(() => firstInput.focus(), 80);
}

function closeModal(e) {
    if (!overlay) return;
    // Only close if clicking the backdrop itself, not the modal box
    if (e && e.target !== overlay) return;
    overlay.classList.remove('open');
    document.body.style.overflow = '';
}

// Close modal with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay && overlay.classList.contains('open')) {
        overlay.classList.remove('open');
        document.body.style.overflow = '';
    }
});


// ── Password Toggle ─────────────────────────────
function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    btn.textContent = isHidden ? '🙈' : '👁';
}


// ── Password Match Hint (register page) ─────────
const confirmInput = document.getElementById('confirm_password');
const passwordInput = document.getElementById('password');
const matchHint = document.getElementById('pw-match-hint');

if (confirmInput && passwordInput && matchHint) {
    const checkMatch = () => {
        if (!confirmInput.value) { matchHint.textContent = ''; return; }
        if (confirmInput.value === passwordInput.value) {
            matchHint.textContent = '✓ Passwords match';
            matchHint.className = 'field-hint hint-success';
        } else {
            matchHint.textContent = '✗ Passwords do not match';
            matchHint.className = 'field-hint hint-error';
        }
    };
    confirmInput.addEventListener('input', checkMatch);
    passwordInput.addEventListener('input', checkMatch);
}


// ── Flash Auto-Dismiss ──────────────────────────
setTimeout(() => {
    document.querySelectorAll('.flash').forEach(el => {
        el.style.transition = 'opacity 0.5s ease';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 500);
    });
}, 5000);


// ── Search debounce (auto-submit) ──────────────
const searchInput = document.getElementById('search-input');
const searchForm  = document.getElementById('search-form');

if (searchInput && searchForm) {
    let debounceTimer;
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchForm.submit();
        }, 500);
    });
}


// ── Post card staggered animation ──────────────
document.querySelectorAll('.post-card').forEach((card, i) => {
    card.style.animationDelay = `${i * 60}ms`;
});
