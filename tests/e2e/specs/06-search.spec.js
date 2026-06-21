// @ts-check
const { test, expect } = require('@playwright/test');
const { bootApp, goTo } = require('./helpers');

test.describe('Search — búsqueda y filtros', () => {
  test.beforeEach(async ({ page }) => {
    await bootApp(page);
    await goTo(page, 'search');
    // runSearch() hace skip si q === '' (fix N0.6), así que solo esperamos
    // que la sección esté activa — no la respuesta de API inicial.
  });

  test('La página search carga', async ({ page }) => {
    await expect(page.locator('#page-search')).toHaveClass(/active/);
  });

  test('El input de búsqueda está presente', async ({ page }) => {
    await expect(page.locator('#search-input')).toBeVisible();
  });

  test('El panel de filtros está presente', async ({ page }) => {
    await expect(page.locator('#search-filters')).toBeVisible();
  });

  test('Existen checkboxes de tipo (más de uno)', async ({ page }) => {
    const checkboxes = page.locator('#search-filters input[type="checkbox"]');
    expect(await checkboxes.count()).toBeGreaterThan(1);
  });

  test('Los filtros de fecha from/to están presentes', async ({ page }) => {
    await expect(page.locator('#search-date-from')).toBeVisible();
    await expect(page.locator('#search-date-to')).toBeVisible();
  });

  test('El botón Limpiar filtros está presente', async ({ page }) => {
    await expect(page.locator('#search-clear')).toBeVisible();
  });

  test('Buscar "fer" llama a /api/search y muestra resultados', async ({ page }) => {
    await page.fill('#search-input', 'fer');
    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/search') && r.url().includes('q=fer') && r.ok()),
      page.keyboard.press('Enter'),
    ]);
    expect(response.ok()).toBeTruthy();
    await page.waitForFunction(
      () => {
        const el = document.getElementById('search-results');
        return el && el.textContent && el.textContent.trim().length > 0;
      },
      { timeout: 10_000 },
    );
    await expect(page.locator('#search-results')).not.toBeEmpty();
  });

  test('Limpiar filtros resetea los filtros de fecha', async ({ page }) => {
    // #search-clear limpia fechas y checkboxes, pero NO el texto de búsqueda (diseño intencional)
    await page.evaluate(() => {
      document.getElementById('search-date-from').value = '2026-01-01';
      document.getElementById('search-date-to').value = '2026-12-31';
    });
    await page.click('#search-clear');
    await expect(page.locator('#search-date-from')).toHaveValue('');
    await expect(page.locator('#search-date-to')).toHaveValue('');
  });

  test('Filtrar por tipo incluye el parámetro types en la URL', async ({ page }) => {
    // Configurar los checkboxes ANTES de escribir la query: con el input vacío,
    // runSearch() hace skip, así que el uncheck/check no dispara búsquedas intermedias.
    // (Si se rellena 'fer' primero, cada onchange lanza una búsqueda y el
    // waitForResponse puede capturar la del último uncheck — 0 tipos, sin types=.)
    const checkboxes = page.locator('#search-filters input[type="checkbox"]');
    const count = await checkboxes.count();
    for (let i = 0; i < count; i++) {
      if (await checkboxes.nth(i).isChecked()) {
        await checkboxes.nth(i).uncheck();
      }
    }
    await checkboxes.first().check();

    // Ahora sí: query + Enter sobre el input → una única búsqueda con el tipo marcado.
    await page.fill('#search-input', 'fer');
    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/search') && r.url().includes('types=')),
      page.press('#search-input', 'Enter'),
    ]);
    expect(response.url()).toContain('types=');
  });

  test('Filtrar por rango de fechas incluye date_from y date_to', async ({ page }) => {
    await page.fill('#search-input', 'fer');
    // Setear los valores directamente sin disparar change — _readSearchFilters() lee el
    // DOM en el momento del search, así que basta con tener los valores presentes al pulsar Enter.
    // Disparar change primero causaría una búsqueda parcial (solo date_from) que la
    // waitForResponse captura antes de que date_to esté en el DOM.
    await page.evaluate(() => {
      document.getElementById('search-date-from').value = '2026-01-01';
      document.getElementById('search-date-to').value = '2026-12-31';
    });
    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/search') && r.ok()),
      page.press('#search-input', 'Enter'),
    ]);
    expect(response.url()).toContain('date_from=');
    expect(response.url()).toContain('date_to=');
  });

  test('GET /api/search?q=fer directo devuelve resultados con personas', async ({ page }) => {
    const result = await page.evaluate(async () => {
      const r = await fetch('/api/search?q=fer', { credentials: 'include' });
      return r.json();
    });
    expect(result).toHaveProperty('people');
    expect(Array.isArray(result.people)).toBeTruthy();
  });
});
