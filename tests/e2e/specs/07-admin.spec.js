// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo, apiPost } = require('./helpers');

test.describe('Admin — gestión de usuarios y auth-events', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    // El listener debe armarse ANTES de goTo, porque goTo llama a loadAdminPage()
    // que dispara /api/admin/users — si esperamos después, la respuesta ya pasó.
    const adminUsersReady = page.waitForResponse(r => r.url().includes('/api/admin/users') && r.ok());
    await goTo(page, 'admin');
    await adminUsersReady;
  });

  test('La página admin carga', async ({ page }) => {
    await expect(page.locator('#page-admin')).toHaveClass(/active/);
  });

  test('La tabla de usuarios tiene al menos una fila', async ({ page }) => {
    const rows = page.locator('#admin-users-tbody tr');
    await expect(rows.first()).toBeVisible();
  });

  test('El botón Nuevo usuario está visible', async ({ page }) => {
    await expect(page.locator('button[onclick="openModal(\'new-user-modal\')"]')).toBeVisible();
  });

  test('El modal Nuevo usuario se abre y se cierra', async ({ page }) => {
    await page.click('button[onclick="openModal(\'new-user-modal\')"]');
    await expect(page.locator('#new-user-modal')).toHaveClass(/open/);
    await page.click('#new-user-modal .modal-close');
    await expect(page.locator('#new-user-modal')).not.toHaveClass(/open/);
  });

  test('La tabla de auth-events tiene cabecera visible', async ({ page }) => {
    // Esperar auth-events (pueden tardar más)
    await page.waitForResponse(r => r.url().includes('/api/admin/auth-events') && r.ok());
    await expect(page.locator('#admin-events-tbody')).toBeVisible();
  });

  test('Los controles de paginación de auth-events están presentes', async ({ page }) => {
    await expect(page.locator('#admin-events-prev')).toBeVisible();
    await expect(page.locator('#admin-events-next')).toBeVisible();
    await expect(page.locator('#admin-events-info')).toBeVisible();
  });

  test('El filtro de tipo de auth-event está presente', async ({ page }) => {
    await expect(page.locator('#admin-event-filter')).toBeVisible();
  });

  test('El toggle "Mostrar archivados" está presente', async ({ page }) => {
    await expect(page.locator('#admin-show-archived')).toBeVisible();
  });

  test('GET /api/admin/users devuelve lista con al menos fer', async ({ page }) => {
    const users = await page.evaluate(async () => {
      const r = await fetch('/api/admin/users', { credentials: 'include' });
      return r.json();
    });
    const usernames = users.map(u => u.username);
    expect(usernames).toContain('fer');
  });

  test('El rol del usuario se muestra en la tabla', async ({ page }) => {
    await page.waitForFunction(
      () => document.querySelector('#admin-users-tbody tr') !== null,
    );
    const firstRow = page.locator('#admin-users-tbody tr').first();
    await expect(firstRow).toContainText(/admin|member/);
  });

  test('Crear y archivar usuario via API devuelve 201 y PATCH correcto @write', async ({ page }) => {
    // Crear usuario de prueba
    const username = `e2e_${Date.now().toString(36)}`;
    const created = await page.evaluate(async u => {
      const r = await fetch('/api/admin/users', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: u,
          team_id: 'offsec',
          role: 'member',
          display_name: 'E2E Test User',
          email: `${u}@e2e.test`,
        }),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    }, username);
    expect(created).toHaveProperty('id');

    // Archivar el usuario creado (limpieza)
    const archived = await page.evaluate(async id => {
      const r = await fetch(`/api/admin/users/${id}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ archived: true }),
      });
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    }, created.id);
    expect(archived.archived).toBe(true);
  });
});
