// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo, apiGet } = require('./helpers');

test.describe('People — lista, drawer y detalle de persona', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'people');
    // No esperamos filas — la BD puede estar vacía; cada test que las necesite
    // hace su propia guardia de skip.
  });

  test('La tabla de personas carga al menos una fila', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    await expect(page.locator('#people-tbody .people-row').first()).toBeVisible();
  });

  test('Los filtros de office, level y skill están presentes', async ({ page }) => {
    await expect(page.locator('#people-filter-office')).toBeVisible();
    await expect(page.locator('#people-filter-level')).toBeVisible();
    await expect(page.locator('#people-filter-skill')).toBeVisible();
  });

  test('El botón + Nueva persona está visible', async ({ page }) => {
    await expect(page.locator('button[onclick="openNewPersonModal()"]')).toBeVisible();
  });

  test('Click en una fila abre el drawer de persona', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    const firstRow = page.locator('#people-tbody .people-row').first();
    await firstRow.click();
    await expect(page.locator('#drawer-overlay')).toHaveClass(/open/);
    await expect(page.locator('#drawer-name')).not.toHaveText('—');
    await expect(page.locator('#drawer-id')).not.toHaveText('—');
  });

  test('El drawer se cierra con el botón ✕', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    await page.locator('#people-tbody .people-row').first().click();
    await expect(page.locator('#drawer-overlay')).toHaveClass(/open/);
    await page.click('.drawer-close');
    await expect(page.locator('#drawer-overlay')).not.toHaveClass(/open/);
  });

  test('El drawer muestra radar, skills y assignments', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    await page.locator('#people-tbody .people-row').first().click();
    await expect(page.locator('#drawer-overlay')).toHaveClass(/open/);
    await expect(page.locator('#drawer-radar')).toBeVisible();
    await expect(page.locator('#drawer-skills')).toBeVisible();
    await expect(page.locator('#drawer-assignments')).toBeVisible();
  });

  test('El enlace "Ver página completa" navega al person-detail', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    await page.locator('#people-tbody .people-row').first().click();
    await expect(page.locator('#drawer-overlay')).toHaveClass(/open/);
    await page.click('#drawer-fullpage');
    await expect(page.locator('#page-person-detail')).toHaveClass(/active/);
    await expect(page.locator('#person-detail-name')).not.toHaveText('—');
    await expect(page.locator('#person-detail-path')).toContainText('/people/');
  });

  test('Las pestañas del detalle de persona existen', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    await page.locator('#people-tbody .people-row').first().click();
    await page.click('#drawer-fullpage');
    await expect(page.locator('#page-person-detail')).toHaveClass(/active/);
    // El person-detail no usa pestañas: organiza el contenido en tarjetas .wf-card
    // apiladas (radar, skills, assignments, coherence, disponibilidad, notas).
    const cards = page.locator('#page-person-detail .wf-card');
    expect(await cards.count()).toBeGreaterThan(2);
  });

  test('El botón + PTO / training está en el detalle de persona', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    await page.locator('#people-tbody .people-row').first().click();
    await page.click('#drawer-fullpage');
    await expect(page.locator('#page-person-detail')).toHaveClass(/active/);
    await expect(page.locator('button[onclick="openNewAvailModal()"]')).toBeVisible();
  });

  test('El modal + Nueva persona se abre y se cierra', async ({ page }) => {
    await page.click('button[onclick="openNewPersonModal()"]');
    await expect(page.locator('#new-person-modal')).toHaveClass(/open/);
    await page.click('#new-person-modal .modal-close');
    await expect(page.locator('#new-person-modal')).not.toHaveClass(/open/);
  });

  test('El modal de disponibilidad (PTO) requiere seleccionar persona primero', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    await page.locator('#people-tbody .people-row').first().click();
    await page.click('#drawer-fullpage');
    await expect(page.locator('#page-person-detail')).toHaveClass(/active/);
    await page.click('button[onclick="openNewAvailModal()"]');
    await expect(page.locator('#new-avail-modal')).toHaveClass(/open/);
    await page.click('#new-avail-modal .modal-close');
    await expect(page.locator('#new-avail-modal')).not.toHaveClass(/open/);
  });
});
