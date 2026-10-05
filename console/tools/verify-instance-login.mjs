import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const CONSOLE_URL = process.env.MIXTUM_CONSOLE_URL ?? 'http://127.0.0.1:4200';
const KEYCLOAK_ORIGIN = process.env.MIXTUM_KEYCLOAK_ORIGIN ?? 'http://127.0.0.1:8080';
const API_ORIGIN = process.env.MIXTUM_API_ORIGIN ?? 'http://127.0.0.1:8000';
let currentStep = 'avvio';
let activePage;
let safeDiagnostic = '';

async function main() {
  const input = JSON.parse(readFileSync(0, 'utf8'));
  assert.equal(typeof input.username, 'string');
  assert.equal(typeof input.password, 'string');
  assert.ok(input.workspaceId === undefined || (Number.isSafeInteger(input.workspaceId) && input.workspaceId > 0));
  assert.ok(input.newPassword === undefined || typeof input.newPassword === 'string');
  assert.ok(input.firstName === undefined || typeof input.firstName === 'string');
  assert.ok(input.lastName === undefined || typeof input.lastName === 'string');
  assert.ok(input.expectedWorkspacePrimary === undefined || typeof input.expectedWorkspacePrimary === 'string');
  assert.ok(input.expectedGlobalPrimary === undefined || typeof input.expectedGlobalPrimary === 'string');
  assert.ok(input.expectedTicketTitle === undefined || typeof input.expectedTicketTitle === 'string');
  assert.ok(input.forbiddenWorkspaceId === undefined
    || (Number.isSafeInteger(input.forbiddenWorkspaceId) && input.forbiddenWorkspaceId > 0));

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    activePage = page;
    currentStep = 'apertura Console';
    await page.goto(CONSOLE_URL, { waitUntil: 'domcontentloaded' });
    if (input.workspaceId !== undefined) {
      await page.waitForFunction(expected => document.querySelector('app-root > div')?.style
        .getPropertyValue('--mixtum-primary').trim() === expected, input.expectedGlobalPrimary ?? '#14532d');
    }
    currentStep = 'avvio login';
    await page.getByRole('button', { name: 'Accedi con Keycloak' }).click();
    currentStep = 'redirect Keycloak';
    await page.waitForURL(url => url.origin === KEYCLOAK_ORIGIN && url.pathname.endsWith('/protocol/openid-connect/auth'));

    const authorization = new URL(page.url());
    assert.equal(authorization.searchParams.get('client_id'), 'mixtum-console');
    assert.equal(authorization.searchParams.get('response_type'), 'code');
    assert.equal(authorization.searchParams.get('code_challenge_method'), 'S256');
    assert.ok(authorization.searchParams.get('code_challenge'));
    assert.equal(authorization.searchParams.get('redirect_uri'), `${CONSOLE_URL}/`);

    const sessionResponse = page.waitForResponse(response =>
      response.url() === `${API_ORIGIN}/api/workspace/session/` && response.request().method() === 'GET',
    );
    currentStep = 'credenziali Keycloak';
    await page.locator('#username').fill(input.username);
    await page.locator('#password').fill(input.password);
    await page.locator('#kc-login').click();
    if (input.newPassword !== undefined) {
      currentStep = 'cambio password temporanea';
      await page.locator('#password-new').fill(input.newPassword);
      await page.locator('#password-confirm').fill(input.newPassword);
      await page.getByRole('button', { name: 'Submit' }).click();
    }
    currentStep = 'required action successiva';
    const dashboard = page.getByRole('heading', { name: 'Dashboard' });
    const firstName = page.locator('#firstName');
    await Promise.race([dashboard.waitFor(), firstName.waitFor()]);
    if (await firstName.isVisible()) {
      currentStep = 'completamento profilo Keycloak';
      await firstName.fill(input.firstName ?? 'Mixtum');
      await page.locator('#lastName').fill(input.lastName ?? 'User');
      await page.getByRole('button', { name: 'Submit' }).click();
    }
    currentStep = 'ritorno alla Dashboard';
    await dashboard.waitFor();
    currentStep = 'sessione backend';
    const session = await sessionResponse;
    const authorizationHeader = session.request().headers().authorization;
    let tokenDiagnostic = '';
    if (authorizationHeader?.startsWith('Bearer ')) {
      try {
        const header = JSON.parse(Buffer.from(authorizationHeader.slice(7).split('.')[0], 'base64url').toString());
        const payload = JSON.parse(Buffer.from(authorizationHeader.slice(7).split('.')[1], 'base64url').toString());
        const audience = Array.isArray(payload.aud) ? payload.aud.join(',') : String(payload.aud);
        tokenDiagnostic = `, kid=${header.kid}, issuer=${payload.iss === `${KEYCLOAK_ORIGIN}/realms/mixtum` ? 'atteso' : 'diverso'}, audience=${audience}, type=${payload.typ}`;
      } catch {
        tokenDiagnostic = ', token non decodificabile';
      }
    }
    let responseDiagnostic = '';
    if (session.status() !== 200) {
      const body = await session.json().catch(() => ({}));
      const detail = typeof body.detail === 'string' ? body.detail : '';
      const knownDetails = new Set([
        'Invalid bearer token',
        'Invalid token type',
        'Invalid token subject',
        'Invalid identity profile',
        'Identity requires an explicit account link',
        'Identity could not be provisioned',
      ]);
      responseDiagnostic = knownDetails.has(detail) ? `, backend=${detail}` : '';
    }
    safeDiagnostic = `HTTP ${session.status()}${tokenDiagnostic}${responseDiagnostic}`;
    assert.equal(session.status(), 200);
    assert.ok(authorizationHeader?.startsWith('Bearer '));
    if (input.workspaceId === undefined) {
      currentStep = 'logout';
      await page.getByRole('button', { name: 'Esci' }).click();
      await page.getByRole('button', { name: 'Accedi con Keycloak' }).waitFor();
      assert.equal(await page.evaluate(() => sessionStorage.getItem('mixtum.workspaceId')), null);
      console.log('PASS: primo login Console, cambio password temporanea e logout.');
      return;
    }
    const workspace = page.locator('#workspace-select');
    await workspace.selectOption(String(input.workspaceId));
    assert.equal(await workspace.inputValue(), String(input.workspaceId));
    const expectedWorkspacePrimary = input.expectedWorkspacePrimary ?? '#1e3a8a';
    await page.waitForFunction(expected => document.querySelector('app-root > div')?.style
      .getPropertyValue('--mixtum-primary').trim() === expected, expectedWorkspacePrimary);

    const ticketResponse = page.waitForResponse(response =>
      response.url().startsWith(`${API_ORIGIN}/api/plugin-ticket/tickets/`) && response.request().method() === 'GET',
    );
    await page.getByRole('link', { name: 'Ticket', exact: true }).click();
    const response = await ticketResponse;
    assert.equal(response.status(), 200);
    assert.equal(response.request().headers()['x-workspace-id'], String(input.workspaceId));
    assert.ok(response.request().headers().authorization?.startsWith('Bearer '));
    await page.getByText(input.expectedTicketTitle ?? 'Staging A').waitFor();
    if (input.forbiddenWorkspaceId !== undefined) {
      currentStep = 'diniego workspace estraneo';
      const denied = await page.request.get(`${API_ORIGIN}/api/plugin-ticket/tickets/`, {
        headers: {
          Authorization: response.request().headers().authorization,
          'X-Workspace-Id': String(input.forbiddenWorkspaceId),
        },
      });
      safeDiagnostic = `HTTP ${denied.status()}`;
      assert.equal(denied.status(), 403);
    }
    safeDiagnostic = '';
    await page.getByRole('button', { name: 'Esci' }).click();
    await page.getByRole('button', { name: 'Accedi con Keycloak' }).waitFor();
    assert.equal(await page.evaluate(() => sessionStorage.getItem('mixtum.workspaceId')), null);
    console.log('PASS: login Console con Authorization Code + PKCE, selezione workspace, API Ticket e logout.');
  } catch (error) {
    if (process.env.MIXTUM_FAILURE_SCREENSHOT && activePage) {
      await activePage.screenshot({ path: process.env.MIXTUM_FAILURE_SCREENSHOT, fullPage: true });
    }
    throw error;
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  // Browser errors can contain redirect URLs with transient OIDC state; do not log them.
  const diagnostic = safeDiagnostic ? `, ${safeDiagnostic}` : '';
  console.error(`FAIL login Console (${currentStep}${diagnostic}): ${error.name}`);
  process.exitCode = 1;
});
