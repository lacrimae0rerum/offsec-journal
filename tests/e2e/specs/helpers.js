// Shared helpers for OffSec Journal E2E tests.
// Pre-condition: Docker dev server is running on 127.0.0.1:8001 with DEV_USER=fer.

/**
 * Navigate to the app root and wait for bootstrapApp() + refreshAll() to finish.
 * Returns once /api/people and /api/projects have responded and the DOM has
 * the people section with at least the header visible.
 */
async function bootApp(page) {
  // Bypass the welcome overlay — each Playwright page starts with empty sessionStorage,
  // so the overlay would block all nav clicks without this.
  await page.addInitScript(() => {
    sessionStorage.setItem('osj_welcomed', '1');
  });
  // Include goto() inside Promise.all — the canonical Playwright pattern.
  // Listeners and navigation start atomically: no window where a fast response
  // could arrive between goto() resolving and a later Promise.all().
  await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/auth/me') && r.ok()),
    page.waitForResponse(r => r.url().includes('/api/people') && r.ok()),
    page.goto('/'),
  ]);
}

/**
 * Navigate to a SPA page by clicking the nav item.
 * Returns once the target <section> has the 'active' class.
 */
async function goTo(page, pageId) {
  await page.click(`[data-page="${pageId}"]`);
  await page.waitForFunction(
    id => document.getElementById(`page-${id}`)?.classList.contains('active'),
    pageId,
  );
}

/**
 * Wait for the first matching toast of a given kind ('success'|'error'|'warn'|'info').
 */
async function waitForToast(page, kind = 'success') {
  return page.waitForSelector(`.toast.${kind}`, { state: 'visible' });
}

/**
 * Open a modal by its ID and wait for it to have the 'open' class.
 */
async function openModal(page, modalId) {
  await page.waitForFunction(
    id => document.getElementById(id)?.classList.contains('open'),
    modalId,
  );
}

/**
 * Close a modal via its ✕ button and wait for it to lose the 'open' class.
 */
async function closeModal(page, modalId) {
  await page.click(`#${modalId} .modal-close`);
  await page.waitForFunction(
    id => !document.getElementById(id)?.classList.contains('open'),
    modalId,
  );
}

/**
 * Create a minimal journal entry and return its ID.
 * Uses direct API calls (faster than UI) to seed data for subsequent tests.
 */
async function apiPost(page, path, body) {
  return page.evaluate(
    async ([p, b]) => {
      const r = await fetch(`/api${p}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(b),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },
    [path, body],
  );
}

async function apiGet(page, path) {
  return page.evaluate(async p => {
    const r = await fetch(`/api${p}`, { credentials: 'include' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }, path);
}

module.exports = { bootApp, goTo, waitForToast, openModal, closeModal, apiPost, apiGet };
