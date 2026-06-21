// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo, apiGet, apiPost } = require('./helpers');

test.describe('Notes — añadir y leer notas en entidades', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
  });

  test('GET /api/notes para "fer" responde con array', async ({ page }) => {
    const notes = await apiGet(page, '/notes?entity_type=person&entity_id=fer');
    expect(Array.isArray(notes)).toBeTruthy();
  });

  test('Añadir nota a "fer" via API persiste y es recuperable @write', async ({ page }) => {
    const body = `Nota e2e ${Date.now()}`;
    const created = await apiPost(page, '/notes', {
      entity_type: 'persons',
      entity_id: 'fer',
      body,
      tags: ['e2e'],
    });
    expect(created).toHaveProperty('id');
    expect(created.body).toBe(body);

    // Verificar que aparece al listar notas
    const notes = await apiGet(page, '/notes?entity_type=persons&entity_id=fer');
    const found = notes.find(n => n.body === body);
    expect(found).toBeTruthy();
  });

  test('La sección de notas de person-detail carga', async ({ page }) => {
    const people = await apiGet(page, '/people');
    if (!people.length) { test.skip(); return; }
    await goTo(page, 'people');
    // Usar .people-row para evitar que el placeholder <tr> engañe al selector
    const firstRow = page.locator('#people-tbody .people-row').first();
    await expect(firstRow).toBeVisible();
    await firstRow.click();
    await expect(page.locator('#drawer-overlay')).toHaveClass(/open/);
    await page.click('#drawer-fullpage');
    await expect(page.locator('#page-person-detail')).toHaveClass(/active/);

    // Las notas de persona están siempre visibles en una tarjeta del person-detail,
    // no detrás de una pestaña.
    await expect(page.locator('#person-detail-notes')).toBeVisible();
  });

  test('El textarea de notas del proyecto es funcional', async ({ page }) => {
    const projects = await apiGet(page, '/projects');
    if (!projects.length) {
      test.skip('No hay proyectos en la base de datos');
      return;
    }
    await goTo(page, 'projects');
    // Vista por defecto kanban; esperamos al re-render y clicamos la tarjeta.
    const kanbanCard = page.locator('#projects-kanban-view .kanban-card').first();
    await expect(kanbanCard).toBeVisible();
    await kanbanCard.click();
    await page.waitForFunction(
      () => document.getElementById('project-detail-title')?.textContent?.trim() !== '—',
    );
    await expect(page.locator('#project-detail-notes')).toBeVisible();
  });
});
