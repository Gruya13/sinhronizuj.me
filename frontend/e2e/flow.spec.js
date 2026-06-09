import { test, expect } from '@playwright/test';

test.describe('E2E Flow Sinhronizuj.me', () => {
  test('landing page and invalid login attempt', async ({ page }) => {
    // 1. Otvaranje Landing stranice
    await page.goto('/');
    
    // Provera da li je naslov ispravan
    await expect(page.locator('h1')).toContainText('Neka vaši video snimci progovore srpski');
    
    // 2. Klik na dugme "Prijava za članove"
    const loginBtn = page.getByRole('button', { name: 'Prijava za članove' });
    await expect(loginBtn).toBeVisible();
    await loginBtn.click();
    
    // 3. Provera da smo na Login formi
    await expect(page.getByRole('heading', { name: 'sinhronizuj.me' })).toBeVisible();
    await expect(page.locator('label[for="email"]')).toContainText('E-mail Adresa');
    await expect(page.locator('label[for="password"]')).toContainText('Lozinka');
    
    // 4. Popunjavanje pogrešnih kredencijala za testiranje neuspele prijave
    await page.fill('#email', 'neispravan@sinhronizuj.me');
    await page.fill('#password', 'PogresnaLozinka123');
    
    // Klik na dugme "Prijavi se"
    await page.click('button[type="submit"]');
    
    // 5. Provera dugmeta (zaustavićemo se na proveri da se forma poslala/ostala vidljiva)
    const submitBtn = page.getByRole('button', { name: 'Prijavi se' });
    await expect(submitBtn).toBeVisible();
  });
});
