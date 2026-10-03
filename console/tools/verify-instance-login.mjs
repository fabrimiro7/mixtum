import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const CONSOLE_URL = 'http://127.0.0.1:4200';
const KEYCLOAK_ORIGIN = 'http://127.0.0.1:8080';
const API_ORIGIN = 'http://127.0.0.1:8000';

async function main() {
  const input = JSON.parse(readFileSync(0, 'utf8'));
  assert.equal(typeof input.username, 'string');
  assert.equal(typeof input.password, 'string');
  assert.ok(Number.isSafeInteger(input.workspaceId) && input.workspaceId > 0);

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(CONSOLE_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelector('app-root > div')?.style
      .getPropertyValue('--mixtum-primary').trim() === '#14532d');
    await page.getByRole('button', { name: 'Accedi con Keycloak' }).click();
    await page.waitForURL(url => url.origin === KEYCLOAK_ORIGIN && url.pathname.endsWith('/protocol/openid-connect/auth'));

    const authorization = new URL(page.url());
    assert.equal(authorization.searchParams.get('client_id'), 'mixtum-console');
    assert.equal(authorization.searchParams.get('response_type'), 'code');
    assert.equal(authorization.searchParams.get('code_challenge_method'), 'S256');
    assert.ok(authorization.searchParams.get('code_challenge'));
    assert.equal(authorization.searchParams.get('redirect_uri'), `${CONSOLE_URL}/`);

    await page.locator('#username').fill(input.username);
    await page.locator('#password').fill(input.password);
    await page.locator('#kc-login').click();
    await page.getByRole('heading', { name: 'Dashboard' }).waitFor();
    const workspace = page.locator('#workspace-select');
    await workspace.selectOption(String(input.workspaceId));
    assert.equal(await workspace.inputValue(), String(input.workspaceId));
    await page.waitForFunction(() => document.querySelector('app-root > div')?.style
      .getPropertyValue('--mixtum-primary').trim() === '#1e3a8a');

    const ticketResponse = page.waitForResponse(response =>
      response.url().startsWith(`${API_ORIGIN}/api/plugin-ticket/tickets/`) && response.request().method() === 'GET',
    );
    await page.getByRole('link', { name: 'Ticket', exact: true }).click();
    const response = await ticketResponse;
    assert.equal(response.status(), 200);
    assert.equal(response.request().headers()['x-workspace-id'], String(input.workspaceId));
    assert.ok(response.request().headers().authorization?.startsWith('Bearer '));
    await page.getByText('Staging A').waitFor();
    console.log('PASS: login Console con Authorization Code + PKCE, selezione workspace e API Ticket.');
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  // Browser errors can contain redirect URLs with transient OIDC state; do not log them.
  console.error(`FAIL login Console: ${error.name}`);
  process.exitCode = 1;
});
