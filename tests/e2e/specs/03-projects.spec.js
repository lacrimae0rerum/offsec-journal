// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo } = require('./helpers');

test.describe('Projects — lista y detalle de proyecto', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'projects');
  });

  test('La sección de proyectos carga con pestañas de status', async ({ page }) => {
    const tabs = page.locator('#projects-tabs .tab');
    expect(await tabs.count()).toBeGreaterThan(1);
  });

  test('El KPI de proyectos activos es visible en overview', async ({ page }) => {
    await goTo(page, 'overview');
    const kpi = page.locator('#kpi-projects-active');
    await expect(kpi).toBeVisible();
    // El valor puede ser 0 o un número; no debe ser "—" una vez que los datos cargaron
    await page.waitForFunction(
      () => document.getElementById('kpi-projects-active')?.textContent?.trim() !== '—',
    );
  });

  test('La vista kanban o tabla está presente en proyectos', async ({ page }) => {
    const kanban = page.locator('#projects-kanban-view');
    const table = page.locator('#projects-table-view');
    const kanbanVisible = await kanban.isVisible();
    const tableVisible = await table.isVisible();
    expect(kanbanVisible || tableVisible).toBeTruthy();
  });

  test('El botón + Nuevo proyecto está visible', async ({ page }) => {
    await expect(
      page.locator('button[onclick="openNewProjectModal()"]').first(),
    ).toBeVisible();
  });

  test('El modal + Nuevo proyecto se abre y se cierra', async ({ page }) => {
    await page.click('button[onclick="openNewProjectModal()"]');
    await expect(page.locator('#new-project-modal')).toHaveClass(/open/);
    await page.click('#new-project-modal .modal-close');
    await expect(page.locator('#new-project-modal')).not.toHaveClass(/open/);
  });

  test('El detalle de proyecto muestra título y breadcrumb', async ({ page }) => {
    // Navegar al primer proyecto disponible via API y luego hacer click
    const projects = await page.evaluate(async () => {
      const r = await fetch('/api/projects', { credentials: 'include' });
      return r.json();
    });
    if (!projects.length) {
      test.skip('No hay proyectos en la base de datos');
      return;
    }
    // Click en la primera fila de la vista tabla (si está visible) o card kanban
    // La vista por defecto es kanban (la tabla arranca con display:none). Esperamos
    // al re-render que dispara refreshAll() y clicamos la tarjeta; ambas vistas
    // comparten el handler que abre el project-detail.
    const kanbanCard = page.locator('#projects-kanban-view .kanban-card').first();
    await expect(kanbanCard).toBeVisible();
    await kanbanCard.click();
    await page.waitForFunction(
      () => document.getElementById('project-detail-title')?.textContent?.trim() !== '—',
    );
    await expect(page.locator('#project-detail-breadcrumb')).toContainText('/projects/');
  });

  test('El modal de edición se puede abrir desde el detalle de proyecto', async ({ page }) => {
    const projects = await page.evaluate(async () => {
      const r = await fetch('/api/projects', { credentials: 'include' });
      return r.json();
    });
    if (!projects.length) {
      test.skip('No hay proyectos en la base de datos');
      return;
    }
    // La vista por defecto es kanban (la tabla arranca con display:none). Esperamos
    // al re-render que dispara refreshAll() y clicamos la tarjeta; ambas vistas
    // comparten el handler que abre el project-detail.
    const kanbanCard = page.locator('#projects-kanban-view .kanban-card').first();
    await expect(kanbanCard).toBeVisible();
    await kanbanCard.click();
    await page.waitForFunction(
      () => document.getElementById('project-detail-title')?.textContent?.trim() !== '—',
    );
    const editBtn = page.locator('#project-detail-edit-btn');
    await expect(editBtn).toBeVisible();
  });
});
