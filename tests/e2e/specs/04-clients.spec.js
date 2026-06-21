// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo } = require('./helpers');

test.describe('Clients — lista y detalle de cliente', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'clients');
  });

  test('La sección clients carga', async ({ page }) => {
    await expect(page.locator('#page-clients')).toHaveClass(/active/);
  });

  test('El panel de lista de clientes está presente', async ({ page }) => {
    await expect(page.locator('#clients-list')).toBeAttached();
  });

  test('El botón + Nuevo cliente está visible', async ({ page }) => {
    await expect(
      page.locator('button[onclick="openModal(\'new-client-modal\')"]').first(),
    ).toBeVisible();
  });

  test('El modal + Nuevo cliente se abre y se cierra', async ({ page }) => {
    await page.click('button[onclick="openModal(\'new-client-modal\')"]');
    await expect(page.locator('#new-client-modal')).toHaveClass(/open/);
    await page.click('#new-client-modal .modal-close');
    await expect(page.locator('#new-client-modal')).not.toHaveClass(/open/);
  });

  test('Hacer click en un cliente carga su detalle', async ({ page }) => {
    const clients = await page.evaluate(async () => {
      const r = await fetch('/api/clients', { credentials: 'include' });
      return r.json();
    });
    if (!clients.length) {
      test.skip('No hay clientes en la base de datos');
      return;
    }
    const clientCard = page.locator('#clients-list .client-list-item').first();
    await expect(clientCard).toBeVisible();
    await clientCard.click();
    // El detalle se pinta en #client-detail
    await page.waitForFunction(() => {
      const el = document.getElementById('client-detail');
      return el && el.children.length > 0;
    });
    await expect(page.locator('#client-detail')).not.toBeEmpty();
  });
});
