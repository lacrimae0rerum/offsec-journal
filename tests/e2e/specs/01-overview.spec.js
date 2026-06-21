// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp } = require('./helpers');

test.describe('Overview — página de inicio', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
  });

  test('La página de overview está activa al cargar', async ({ page }) => {
    await expect(page.locator('#page-overview')).toHaveClass(/active/);
  });

  test('El badge de equipo y el nombre de usuario se pintan', async ({ page }) => {
    await expect(page.locator('#team-badge')).not.toBeEmpty();
    await expect(page.locator('#sidebar-user-name')).not.toBeEmpty();
    await expect(page.locator('#sidebar-user-role')).toContainText(/admin|miembro/);
  });

  test('El heatmap de overview está presente', async ({ page }) => {
    await expect(page.locator('#overview-heatmap')).toBeVisible();
  });

  test('La sección de coherence warnings está presente', async ({ page }) => {
    // El contador siempre existe, aunque no haya warnings con datos vacíos
    await expect(page.locator('#overview-warnings-count')).toBeVisible();
  });

  test('La sección de journal reciente está presente', async ({ page }) => {
    // El contenedor existe en DOM; con datos vacíos puede tener alto cero
    await expect(page.locator('#overview-journal')).toBeAttached();
  });

  test('Los botones de rango se generan (9 opciones)', async ({ page }) => {
    // buildOverviewRangeButtons() genera 9 rangos: 1S 2S 3S 1M 2M 3M 4M 5M 6M
    const buttons = page.locator('#overview-range-btns button');
    await expect(buttons).toHaveCount(9);
  });

  test('El overlay no-access NO está visible para fer', async ({ page }) => {
    await expect(page.locator('#no-access-overlay')).toHaveClass(/hidden/);
  });
});
