import { test, expect } from '@playwright/test';

test.describe('Studio Editor E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));

    // 1. Postavljamo token u localStorage pre navigacije
    await page.addInitScript(() => {
      window.localStorage.setItem('sinhronizuj_me_token', 'mock-test-token');
    });

    // 2. Interceptujemo API rute
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'user-uuid', email: 'testuser@sinhronizuj.me' })
      });
    });

    await page.route('**/api/v1/projects', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'test-project-uuid',
            name: 'Moj Test Projekat',
            video_title: 'Test Video',
            status: 'ready',
            created_at: '2026-06-09T05:00:00Z'
          }
        ])
      });
    });

    await page.route('**/api/v1/project/test-project-uuid', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          project_id: 'test-project-uuid',
          name: 'Moj Test Projekat',
          video_url: 'http://localhost:5173/mock_video.mp4',
          video_path: 'mock_video.mp4',
          vocals_path: 'vocals.mp4',
          no_vocals_path: 'no_vocals.mp4',
          no_vocals_url: 'http://localhost:5173/mock_no_vocals.mp3',
          dubbed_audio_path: 'dubbed.mp3',
          dubbed_audio_url: 'http://localhost:5173/mock_dubbed.mp3',
          visual_context_url: '',
          title: 'Test Video Title',
          segments: [
            {
              id: 1,
              start: 1.0,
              end: 4.0,
              original: 'Hello, how are you?',
              translated: 'Zdravo, kako si?',
              voice_type: 'clone',
              volume: 0.0,
              speed: 1.0,
              pitch: 0.0,
              bg_volume: 0.0,
              tts_path: 'http://localhost:5173/tts_1.mp3',
              tts_duration: 5.0,
              status: 'ready'
            },
            {
              id: 2,
              start: 5.0,
              end: 8.0,
              original: 'I am fine, thank you.',
              translated: 'Ja sam dobro, hvala ti.',
              voice_type: 'clone',
              volume: 0.0,
              speed: 1.0,
              pitch: 0.0,
              bg_volume: 0.0,
              tts_path: 'http://localhost:5173/tts_2.mp3',
              tts_duration: 3.0,
              status: 'ready'
            }
          ],
          costs: { phases: {}, total_usd: 0.0 },
          status: 'ready',
          created_at: '2026-06-09T05:00:00Z'
        })
      });
    });

    await page.route('**/api/v1/project/test-project-uuid/save', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success' })
      });
    });

    await page.route('**/api/v1/hw-stats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ cpu: 10, ram: 20 })
      });
    });

    await page.route('**/api/v1/modal-status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'active', active_workers: 1 })
      });
    });

    await page.goto('/');
    
    // Otvori projekat
    await page.locator('.project-card', { hasText: 'Moj Test Projekat' }).first().click();
    
    // Sačekaj da se učita studio
    await expect(page.locator('h4')).toContainText('Vremenski Editor (Timeline)');
  });

  test('Drag and drop segment movement', async ({ page }) => {
    // Uzimamo drag handler za prvi segment
    const dragHandle = page.getByTestId('drag-move-1');
    await expect(dragHandle).toBeVisible();

    // Uzimamo inicijalnu poziciju
    const boxBefore = await dragHandle.boundingBox();
    expect(boxBefore).not.toBeNull();

    // Pomeramo segment povlačenjem za 100px udesno, držeći Y osu na sredini i računajući od sredine elementa
    const startX = boxBefore.x + boxBefore.width / 2;
    const startY = boxBefore.y + boxBefore.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 100, startY, { steps: 5 });
    await page.mouse.up();

    // Proveravamo da li je pozicija promenjena
    const boxAfter = await dragHandle.boundingBox();
    expect(boxAfter.x).toBeGreaterThan(boxBefore.x);
  });

  test('Resize right edge of segment', async ({ page }) => {
    const resizeHandle = page.getByTestId('resize-right-1');
    await expect(resizeHandle).toBeVisible();

    const boxBefore = await resizeHandle.boundingBox();
    expect(boxBefore).not.toBeNull();
    
    // Pomeramo desnu ivicu udesno da rastegnemo segment, držeći Y osu na sredini
    await resizeHandle.hover();
    await page.mouse.down();
    await page.mouse.move(boxBefore.x + 50, boxBefore.y + boxBefore.height / 2, { steps: 5 });
    await page.mouse.up();

    const boxAfter = await resizeHandle.boundingBox();
    expect(boxAfter.x).toBeGreaterThan(boxBefore.x);
  });

  test('Segment selection and editing text updates the status to edited', async ({ page }) => {
    // Klik na drag-move-1 umesto na span koji ima pointer-events: none
    await page.getByTestId('drag-move-1').click();

    // Provera da li se učitala forma za segment #1
    await expect(page.locator('textarea')).toBeVisible();
    
    // Upisivanje teksta
    await page.fill('textarea', 'Novi prevedeni tekst');
    
    // Klik na vanjsku površinu da se trigeruje Blur i spasi nacrt
    await page.locator('h4').click();
    
    // Provera da se pojavljuje upozorenje o potrebi regeneracije glasa (edited status)
    await expect(page.getByText('Izmenjeno, regenerišite glas!')).toBeVisible();
  });

  test('Undo and Redo stack works correctly', async ({ page }) => {
    // Klik na drag-move-1 i unos teksta
    await page.getByTestId('drag-move-1').click();
    await page.fill('textarea', 'Prva izmena');
    await page.locator('h4').click(); // trigger save
    
    // Unos novog teksta
    await page.fill('textarea', 'Druga izmena');
    await page.locator('h4').click(); // trigger save

    // Pritisak na Ctrl+Z (Undo)
    await page.keyboard.press('Control+z');
    
    // Provera da li je vraćena "Prva izmena"
    await expect(page.locator('textarea')).toHaveValue('Prva izmena');

    // Pritisak na Ctrl+Y (Redo)
    await page.keyboard.press('Control+y');

    // Provera da li je vraćena "Druga izmena"
    await expect(page.locator('textarea')).toHaveValue('Druga izmena');
  });

  test('Collision detection shows red border on dubbed segment', async ({ page }) => {
    // 1. Prebacujemo na dubbed audio izvor kako bi videli tts segmente
    await page.getByRole('button', { name: 'Srpski glas (TTS)' }).click();

    // Proveravamo da li dubbed segment ima crvenu granicu (odmah zbog inicijalnog tts_duration = 5.0 u mock-u)
    const dubbedSegment = page.getByTestId('dubbed-segment-1');
    await expect(dubbedSegment).toHaveCSS('border-top-color', 'rgb(244, 63, 94)');
    await expect(dubbedSegment).toHaveCSS('border-bottom-color', 'rgb(244, 63, 94)');
  });

  test('Group operations select multiple segments and update properties', async ({ page }) => {
    // Onemogućavamo pointer-events na svim drag i resize ručicama kako bi klik pogodio roditeljski div koji nosi onClick
    await page.evaluate(() => {
      const handles = document.querySelectorAll('[data-testid^="drag-move-"], [data-testid^="resize-"]');
      handles.forEach(h => {
        h.style.pointerEvents = 'none';
      });
    });

    // Selektujemo roditeljske div-ove segmenata koji drže onClick
    const segment1 = page.locator('div:has(> [data-testid="drag-move-1"])');
    await segment1.click();

    // Simuliramo programski Ctrl+Click na segment #2
    await page.evaluate(() => {
      const parent = document.querySelector('div:has(> [data-testid="drag-move-2"])');
      if (parent) {
        const event = new MouseEvent('click', {
          bubbles: true,
          cancelable: true,
          view: window,
          ctrlKey: true,
          metaKey: true
        });
        parent.dispatchEvent(event);
      }
    });

    // Provera da li se učitao Bulk Operations panel (koristimo fleksibilniji regex zbog emojija)
    await expect(page.getByText(/Grupne Akcije/)).toBeVisible();

    // Menjamo glas za grupnu selekciju
    await page.selectOption('select', 'male');

    // Proveravamo da li je promena primenjena u UI-ju
    await expect(page.locator('select')).toHaveValue('male');
  });
});
