// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo, apiPost, apiGet } = require('./helpers');

// Tests sin tag: solo lectura — seguros para el loop automático.
// Tests con @write: crean/mutan datos reales en journal.yaml / people.yaml.
//   Loop: npm run test:loop  (excluye @write)
//   Manual completo: npm test

test.describe('Journal — navegación y lectura', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'journal');
  });

  test('La página journal carga con las pestañas', async ({ page }) => {
    await expect(page.locator('#page-journal')).toHaveClass(/active/);
    const tabs = page.locator('#journal-tabs .tab');
    expect(await tabs.count()).toBeGreaterThan(1);
  });

  test('El contenedor de entries está presente', async ({ page }) => {
    await expect(page.locator('#journal-entries')).toBeVisible();
  });

  test('La pestaña Pending está activa por defecto', async ({ page }) => {
    await expect(
      page.locator('#journal-tabs .tab[data-filter="pending"]'),
    ).toHaveClass(/active/);
  });

  test('Cambio de pestaña a Applied actualiza la vista', async ({ page }) => {
    const appliedTab = page.locator('#journal-tabs .tab[data-filter="applied"]');
    await appliedTab.click();
    await expect(appliedTab).toHaveClass(/active/);
    await expect(page.locator('#journal-entries')).toBeVisible();
  });

  test('Cambio de pestaña a Rejected actualiza la vista', async ({ page }) => {
    const rejectedTab = page.locator('#journal-tabs .tab[data-filter="rejected"]');
    await rejectedTab.click();
    await expect(rejectedTab).toHaveClass(/active/);
    await expect(page.locator('#journal-entries')).toBeVisible();
  });
});

test.describe('Journal — escritura @write', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'journal');
  });

  test('Crear entry skill_update queda pending y se limpia @write', async ({ page }) => {
    const skills = await apiGet(page, '/skills');
    if (!skills.length) { test.skip(); return; }

    const entry = await apiPost(page, '/journal', {
      kind: 'skill_update',
      payload: { person_id: 'fer', skill_id: skills[0].id, level: 1, note: 'e2e @write' },
    });
    expect(entry).toHaveProperty('id');
    expect(entry.status).toBe('pending');

    await apiPost(page, `/journal/${entry.id}/reject`, { reason: 'e2e cleanup' });
  });

  test('Rechazar entry la mueve a Rejected @write', async ({ page }) => {
    const skills = await apiGet(page, '/skills');
    if (!skills.length) { test.skip(); return; }

    const entry = await apiPost(page, '/journal', {
      kind: 'skill_update',
      payload: { person_id: 'fer', skill_id: skills[0].id, level: 2, note: 'e2e reject @write' },
    });
    const rejected = await apiPost(page, `/journal/${entry.id}/reject`, { reason: 'e2e' });
    expect(rejected.status).toBe('rejected');
  });

  test('Aplicar skill_update (nivel idéntico) la mueve a Applied @write', async ({ page }) => {
    const skills = await apiGet(page, '/skills');
    if (!skills.length) { test.skip(); return; }

    const personSkills = await apiGet(page, '/people/fer/skills');
    const originalLevel = (personSkills.find(s => s.skill_id === skills[0].id) || {}).level || 0;

    const entry = await apiPost(page, '/journal', {
      kind: 'skill_update',
      payload: { person_id: 'fer', skill_id: skills[0].id, level: originalLevel, note: 'e2e apply @write' },
    });
    const applied = await apiPost(page, `/journal/${entry.id}/apply`, {});
    expect(applied.status).toBe('applied');
  });

  test('Modal reject-modal se abre desde una entry pending @write', async ({ page }) => {
    const skills = await apiGet(page, '/skills');
    if (!skills.length) { test.skip(); return; }

    const entry = await apiPost(page, '/journal', {
      kind: 'skill_update',
      payload: { person_id: 'fer', skill_id: skills[0].id, level: 1, note: 'e2e modal @write' },
    });

    await page.reload();
    await page.waitForResponse(r => r.url().includes('/api/journal') && r.ok());

    const rejectBtn = page.locator(
      '#journal-entries .journal-entry button[onclick*="openRejectModal"]',
    ).first();
    if (await rejectBtn.isVisible()) {
      await rejectBtn.click();
      await expect(page.locator('#reject-modal')).toHaveClass(/open/);
      await page.click('#reject-modal .modal-close');
    }
    await apiPost(page, `/journal/${entry.id}/reject`, { reason: 'e2e cleanup' });
  });
});
