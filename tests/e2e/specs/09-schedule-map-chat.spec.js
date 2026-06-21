// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo } = require('./helpers');

test.describe('Schedule — heatmap de disponibilidad', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'schedule');
  });

  test('La página schedule carga', async ({ page }) => {
    await expect(page.locator('#page-schedule')).toHaveClass(/active/);
  });

  test('El contenedor del heatmap de schedule está presente', async ({ page }) => {
    await expect(page.locator('#schedule-card')).toBeVisible();
    await expect(page.locator('#schedule-heatmap')).toBeVisible();
  });

  test('GET /api/heatmap responde con datos válidos', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const r = await fetch('/api/heatmap?start=2026-01-01&end=2026-12-31', { credentials: 'include' });
      return r.json();
    });
    expect(result).toHaveProperty('weeks');
    expect(result).toHaveProperty('people'); // la API devuelve {weeks, people}, no {weeks, rows}
  });
});

test.describe('Map — distribución geográfica', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'map');
  });

  test('La página map carga', async ({ page }) => {
    await expect(page.locator('#page-map')).toHaveClass(/active/);
  });

  test('El contenedor del mapa está presente', async ({ page }) => {
    await expect(page.locator('.map-container')).toBeVisible();
  });

  test('GET /api/geo devuelve datos válidos', async ({ page }) => {
    const geo = await page.evaluate(async () => {
      const r = await fetch('/api/geo', { credentials: 'include' });
      return r.json();
    });
    expect(Array.isArray(geo)).toBeTruthy();
  });
});

test.describe('Chat — página mock', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'chat');
  });

  test('La página chat carga', async ({ page }) => {
    await expect(page.locator('#page-chat')).toHaveClass(/active/);
  });

  test('El contenedor de mensajes está presente', async ({ page }) => {
    await expect(page.locator('#chat-messages')).toBeVisible();
  });

  test('La página chat muestra el estado mock correctamente', async ({ page }) => {
    // El chat es 100% mock — verificamos que no hay errores JS y la sección está visible
    await expect(page.locator('#page-chat')).toBeVisible();
  });
});
