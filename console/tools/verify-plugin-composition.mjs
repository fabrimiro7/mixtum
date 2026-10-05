import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const CONSOLE_URL = process.env.MIXTUM_CONSOLE_URL ?? 'http://127.0.0.1:4200';
const KEYCLOAK_ORIGIN = process.env.MIXTUM_KEYCLOAK_ORIGIN ?? 'http://127.0.0.1:8080';
const API_ORIGIN = process.env.MIXTUM_API_ORIGIN ?? 'http://127.0.0.1:8000';
let step = 'avvio';

async function main() {
  const input = JSON.parse(readFileSync(0, 'utf8'));
  assert.equal(typeof input.username, 'string');
  assert.equal(typeof input.password, 'string');
  assert.ok(Number.isSafeInteger(input.workspaceId) && input.workspaceId > 0);
  assert.equal(typeof input.ticketEnabled, 'boolean');
  assert.equal(typeof input.linksEnabled, 'boolean');
  assert.equal(typeof input.extensionEnabled, 'boolean');
  assert.ok(input.workspacePrimary === undefined || /^#[0-9a-fA-F]{6}$/.test(input.workspacePrimary));
  assert.ok(input.expectedTicketTitle === undefined || typeof input.expectedTicketTitle === 'string');

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    step = 'login';
    await page.goto(CONSOLE_URL, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Accedi con Keycloak' }).click();
    await page.waitForURL(url => url.origin === KEYCLOAK_ORIGIN
      && url.pathname.endsWith('/protocol/openid-connect/auth'));
    const sessionResponse = page.waitForResponse(response => response.url()
      === `${API_ORIGIN}/api/workspace/session/` && response.request().method() === 'GET');
    await page.locator('#username').fill(input.username);
    await page.locator('#password').fill(input.password);
    await page.locator('#kc-login').click();
    await page.getByRole('heading', { name: 'Dashboard' }).waitFor();
    const session = await sessionResponse;
    assert.equal(session.status(), 200);
    const authorization = session.request().headers().authorization;
    assert.ok(authorization?.startsWith('Bearer '));
    await page.locator('#workspace-select').selectOption(String(input.workspaceId));

    if (input.workspacePrimary !== undefined) {
      step = 'branding seconda composizione';
      const branding = await page.request.patch(
        `${API_ORIGIN}/api/branding/workspace/${input.workspaceId}/`,
        {
          headers: { Authorization: authorization },
          data: { colors: { '--ed-blue': input.workspacePrimary } },
        },
      );
      assert.equal(branding.status(), 200);
    }

    step = 'navigazione composta';
    const expected = [
      ['Ticket', input.ticketEnabled],
      ['Link', input.linksEnabled],
      ['Riepilogo assistenza', input.extensionEnabled],
    ];
    for (const [label, enabled] of expected) {
      assert.equal(await page.getByRole('link', { name: label, exact: true }).count(), enabled ? 1 : 0);
    }

    if (!input.ticketEnabled) {
      step = 'route Ticket disabilitata';
      await page.goto(`${CONSOLE_URL}/tickets`, { waitUntil: 'domcontentloaded' });
      await page.getByRole('heading', { name: 'Dashboard' }).waitFor();
      assert.equal(new URL(page.url()).pathname, '/dashboard');
    } else {
      step = 'route Ticket abilitata';
      await page.getByRole('link', { name: 'Ticket', exact: true }).click();
      await page.getByRole('heading', { name: 'Ticket' }).waitFor();
      if (input.expectedTicketTitle !== undefined) {
        await page.getByText(input.expectedTicketTitle).waitFor();
      }
    }

    if (input.linksEnabled) {
      step = 'route Links abilitata';
      await page.getByRole('link', { name: 'Link', exact: true }).click();
      await page.getByRole('heading', { name: 'Link' }).waitFor();
      await page.getByText('Nessun link in questo workspace.').waitFor();
    }
    if (input.extensionEnabled) {
      step = 'route extension abilitata';
      await page.getByRole('link', { name: 'Riepilogo assistenza', exact: true }).click();
      await page.getByRole('heading', { name: 'Riepilogo assistenza' }).waitFor();
      await page.getByText(/Ticket aperti: \d+/).waitFor();
    }

    await page.getByRole('button', { name: 'Esci' }).click();
    await page.getByRole('button', { name: 'Accedi con Keycloak' }).waitFor();
    console.log('PASS: composizione plugin coerente tra route e navigazione Console.');
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(`FAIL composizione Console (${step}): ${error.name}`);
  process.exitCode = 1;
});
