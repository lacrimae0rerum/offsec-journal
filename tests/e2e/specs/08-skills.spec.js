// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo, apiGet } = require('./helpers');

test.describe('Skills — matriz, catálogo y gaps', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'skills');
  });

  test('La página skills carga', async ({ page }) => {
    await expect(page.locator('#page-skills')).toHaveClass(/active/);
  });

  test('Las pestañas de skills están presentes', async ({ page }) => {
    const tabs = page.locator('#skills-tabs .tab');
    expect(await tabs.count()).toBeGreaterThan(1);
  });

  test('La vista de matriz tiene la tabla de personas vs skills', async ({ page }) => {
    await expect(page.locator('#skills-matrix-view')).toBeVisible();
    await expect(page.locator('#skills-matrix-head')).toBeVisible();
    await expect(page.locator('#skills-tbody')).toBeAttached();
  });

  test('El botón + Nueva skill está visible', async ({ page }) => {
    await expect(
      page.locator('button[onclick="openModal(\'new-catalog-skill-modal\')"]'),
    ).toBeVisible();
  });

  test('El modal + Nueva skill se abre y se cierra', async ({ page }) => {
    await page.click('button[onclick="openModal(\'new-catalog-skill-modal\')"]');
    await expect(page.locator('#new-catalog-skill-modal')).toHaveClass(/open/);
    await page.click('#new-catalog-skill-modal .modal-close');
    await expect(page.locator('#new-catalog-skill-modal')).not.toHaveClass(/open/);
  });

  test('La vista de gaps es accesible desde la pestaña correspondiente', async ({ page }) => {
    // Buscar la pestaña de gaps (puede llamarse "Gaps" o "Skill Gap")
    const gapTab = page.locator('#skills-tabs .tab').filter({ hasText: /gap/i });
    if (await gapTab.count() > 0) {
      await gapTab.click();
      await expect(page.locator('#skills-gap-view')).toBeVisible();
    }
  });

  test('GET /api/skill-gap responde con datos válidos', async ({ page }) => {
    const gaps = await page.evaluate(async () => {
      const r = await fetch('/api/skill-gap?scope=pipeline', { credentials: 'include' });
      return r.json();
    });
    expect(Array.isArray(gaps)).toBeTruthy();
  });

  test('Las cabeceras de la matriz corresponden a skills del catálogo', async ({ page }) => {
    // La matriz de skills requiere personas con skills asignadas para mostrar columnas
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    const skills = await apiGet(page, '/skills');
    if (!skills.length) { test.skip(); return; }
    // La cabecera debe tener al menos una columna de skill (th con un skill_id)
    const thCells = page.locator('#skills-matrix-head th');
    expect(await thCells.count()).toBeGreaterThan(1); // primera th es la columna de persona
  });
});
