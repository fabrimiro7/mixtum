import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const PUBLIC_URL = process.env.MIXTUM_PUBLIC_URL ?? 'http://127.0.0.1:4300';
const KEYCLOAK_ORIGIN = process.env.MIXTUM_KEYCLOAK_ORIGIN ?? 'http://127.0.0.1:8080';
const API_ORIGIN = process.env.MIXTUM_API_ORIGIN ?? 'http://127.0.0.1:8000';
let step = 'avvio';
let diagnostic = '';

async function main() {
  const input = JSON.parse(readFileSync(0, 'utf8'));
  assert.equal(typeof input.username, 'string');
  assert.equal(typeof input.password, 'string');
  assert.ok(Number.isSafeInteger(input.workspaceId) && input.workspaceId > 0);

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    step = 'apertura Public Frontend';
    await page.goto(PUBLIC_URL, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Continua con Keycloak' }).waitFor();

    step = 'avvio login';
    await page.getByRole('button', { name: 'Continua con Keycloak' }).click();
    await page.waitForURL(url => url.origin === KEYCLOAK_ORIGIN
      && url.pathname.endsWith('/protocol/openid-connect/auth'));
    const authorization = new URL(page.url());
    assert.equal(authorization.searchParams.get('client_id'), 'mixtum-public');
    assert.equal(authorization.searchParams.get('response_type'), 'code');
    assert.equal(authorization.searchParams.get('code_challenge_method'), 'S256');
    assert.ok(authorization.searchParams.get('code_challenge'));
    assert.equal(authorization.searchParams.get('redirect_uri'), `${PUBLIC_URL}/`);

    step = 'credenziali Keycloak';
    const sessionResponse = page.waitForResponse(response =>
      response.url() === `${API_ORIGIN}/api/workspace/session/`
      && response.request().method() === 'GET',
    );
    await page.locator('#username').fill(input.username);
    await page.locator('#password').fill(input.password);
    await page.locator('#kc-login').click();
    await page.getByRole('heading', { name: 'Portale' }).waitFor();
    const session = await sessionResponse;
    const authorizationHeader = session.request().headers().authorization;
    let tokenDiagnostic = '';
    if (authorizationHeader?.startsWith('Bearer ')) {
      try {
        const payload = JSON.parse(Buffer.from(authorizationHeader.slice(7).split('.')[1], 'base64url').toString());
        tokenDiagnostic = `, audience=${Array.isArray(payload.aud) ? payload.aud.join(',') : String(payload.aud)}`
          + `, issuer=${payload.iss === `${KEYCLOAK_ORIGIN}/realms/mixtum` ? 'atteso' : 'diverso'}`
          + `, subject=${typeof payload.sub === 'string' && payload.sub.length > 0 ? 'presente' : 'assente'}`
          + `, client=${String(payload.azp)}`;
      } catch {
        tokenDiagnostic = ', token non decodificabile';
      }
    }
    diagnostic = `HTTP ${session.status()}, bearer=${authorizationHeader?.startsWith('Bearer ') === true}${tokenDiagnostic}`;
    assert.equal(session.status(), 200);
    assert.ok(authorizationHeader?.startsWith('Bearer '));
    diagnostic = '';

    step = 'selezione workspace';
    await page.locator('#workspace-select').selectOption(String(input.workspaceId));
    await page.getByText(`Benvenuto, ${input.username}.`).waitFor();
    assert.equal(
      await page.evaluate(() => sessionStorage.getItem('mixtum.public.workspaceId')),
      String(input.workspaceId),
    );

    step = 'logout';
    await page.getByRole('button', { name: 'Esci' }).click();
    await page.getByRole('button', { name: 'Continua con Keycloak' }).waitFor();
    assert.equal(
      await page.evaluate(() => sessionStorage.getItem('mixtum.public.workspaceId')),
      null,
    );
    console.log('PASS: Public Frontend usa client OIDC separato, PKCE, sessione, workspace e logout.');
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  const detail = diagnostic ? `, ${diagnostic}` : '';
  console.error(`FAIL login Public Frontend (${step}${detail}): ${error.name}`);
  process.exitCode = 1;
});
