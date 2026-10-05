import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const CONSOLE_URL = process.env.MIXTUM_CONSOLE_URL ?? 'http://127.0.0.1:4200';
const KEYCLOAK_ORIGIN = process.env.MIXTUM_KEYCLOAK_ORIGIN ?? 'http://127.0.0.1:8080';
const API_ORIGIN = process.env.MIXTUM_API_ORIGIN ?? 'http://127.0.0.1:8000';
let step = 'avvio';
let diagnostic = '';

async function login(page, username, password) {
  step = `login ${username}`;
  await page.goto(CONSOLE_URL, { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Accedi con Keycloak' }).click();
  await page.waitForURL(url => url.origin === KEYCLOAK_ORIGIN && url.pathname.endsWith('/protocol/openid-connect/auth'));
  const sessionResponse = page.waitForResponse(response =>
    response.url() === `${API_ORIGIN}/api/workspace/session/` && response.request().method() === 'GET',
  );
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.locator('#kc-login').click();
  await page.getByRole('heading', { name: 'Dashboard' }).waitFor();
  assert.equal((await sessionResponse).status(), 200);
}

async function logout(page) {
  step = 'logout';
  await page.getByRole('button', { name: 'Esci' }).click();
  await page.getByRole('button', { name: 'Accedi con Keycloak' }).waitFor();
}

async function waitForEnabledButton(page, name) {
  await page.waitForFunction(label => [...document.querySelectorAll('button')].some(button =>
    button.textContent?.trim() === label && !button.disabled
  ), name);
}

async function main() {
  const input = JSON.parse(readFileSync(0, 'utf8'));
  for (const field of ['adminUsername', 'adminPassword', 'ownerUsername', 'ownerPassword', 'newWorkspaceName', 'companyName']) {
    assert.equal(typeof input[field], 'string');
    assert.ok(input[field]);
  }
  assert.ok(Number.isSafeInteger(input.adminWorkspaceId) && input.adminWorkspaceId > 0);

  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await login(page, input.adminUsername, input.adminPassword);

    step = 'selezione workspace amministratore';
    await page.locator('#workspace-select').selectOption(String(input.adminWorkspaceId));
    await page.getByRole('link', { name: 'Amministrazione' }).click();
    await page.getByRole('heading', { name: 'Amministrazione' }).waitFor();
    await page.locator('#workspace-name').waitFor();

    step = 'configurazione workspace';
    await page.locator('#workspace-description').fill('Configurato dalla Console E2E');
    let mutation = page.waitForResponse(response =>
      response.url().startsWith(`${API_ORIGIN}/api/workspace/workspaces/`) && response.request().method() === 'PATCH',
    );
    await page.getByRole('button', { name: 'Salva workspace' }).click();
    assert.equal((await mutation).status(), 200);
    await waitForEnabledButton(page, 'Salva workspace');

    step = 'nomina gestore';
    mutation = page.waitForResponse(response =>
      response.url().startsWith(`${API_ORIGIN}/api/workspace/workspace-users/`) && response.request().method() === 'PATCH',
    );
    await page.getByLabel(`Ruolo di ${input.adminUsername}@example.test`).selectOption('owner');
    assert.equal((await mutation).status(), 200);

    step = 'branding globale';
    await page.locator('#global-primary').fill('#2255aa');
    await page.locator('#global-logo-compact').setInputFiles({
      name: 'console-e2e-logo.png',
      mimeType: 'image/png',
      buffer: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        'base64',
      ),
    });
    mutation = page.waitForResponse(response =>
      response.url() === `${API_ORIGIN}/api/branding/global/` && response.request().method() === 'PATCH',
    );
    await page.getByRole('button', { name: 'Salva branding globale' }).click();
    const brandingResponse = await mutation;
    assert.equal(brandingResponse.status(), 200);
    const branding = await brandingResponse.json();
    assert.equal(typeof branding.logo_compact, 'string');
    assert.ok(branding.logo_compact);
    const mediaResponse = await page.request.get(branding.logo_compact);
    assert.equal(mediaResponse.status(), 200);
    assert.match(mediaResponse.headers()['content-type'] ?? '', /^image\/png(?:;|$)/);

    step = 'creazione workspace con owner';
    await page.locator('#new-workspace-name').fill(input.newWorkspaceName);
    await page.locator('#new-workspace-owner').selectOption({ label: `${input.ownerUsername}@example.test` });
    mutation = page.waitForResponse(response =>
      response.url() === `${API_ORIGIN}/api/workspace/workspaces/` && response.request().method() === 'POST',
    );
    const refreshedSession = page.waitForResponse(response =>
      response.url() === `${API_ORIGIN}/api/workspace/session/` && response.request().method() === 'GET',
    );
    await page.getByRole('button', { name: 'Crea', exact: true }).click();
    const workspaceResponse = await mutation;
    assert.equal(workspaceResponse.status(), 201);
    const createdWorkspace = await workspaceResponse.json();
    assert.ok(Number.isSafeInteger(createdWorkspace.id));
    assert.equal((await refreshedSession).status(), 200);
    await page.waitForTimeout(100);
    step = 'configurazione Ticket amministratore';
    await page.locator('#workspace-select').selectOption(String(input.adminWorkspaceId));
    await page.waitForFunction(workspaceId => (
      document.querySelector('#workspace-select')?.value === String(workspaceId)
    ), input.adminWorkspaceId);
    await page.getByRole('link', { name: 'Configura Ticket' }).click();
    await page.getByRole('heading', { name: 'Configurazione Ticket' }).waitFor();
    await page.locator('#ticket-company-name').waitFor();
    await page.locator('#ticket-company-name').fill(input.companyName);
    mutation = page.waitForResponse(response =>
      response.url() === `${API_ORIGIN}/api/plugin-ticket/configuration/companies/`
      && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Aggiungi', exact: true }).click();
    assert.equal((await mutation).status(), 201);
    step = 'attesa azienda Ticket';
    const company = page.locator('article').filter({ hasText: input.companyName });
    await company.waitFor();
    step = 'selezione richiedente Ticket';
    const membershipUser = company.locator('select').nth(0);
    const optionLabels = await membershipUser.locator('option').allTextContents();
    diagnostic = `numero-opzioni=${optionLabels.length}`;
    await membershipUser.selectOption({ label: `${input.adminUsername}@example.test` });
    diagnostic = '';
    await waitForEnabledButton(page, 'Assegna');
    step = 'assegnazione richiedente Ticket';
    mutation = page.waitForResponse(response =>
      response.url().includes('/memberships/') && response.request().method() === 'POST',
    );
    await company.getByRole('button', { name: 'Assegna' }).click();
    assert.equal((await mutation).status(), 201);

    await logout(page);
    await login(page, input.ownerUsername, input.ownerPassword);

    step = 'gestione workspace da owner';
    await page.locator('#workspace-select').selectOption(String(createdWorkspace.id));
    await page.getByRole('link', { name: 'Amministrazione' }).click();
    await page.locator('#workspace-description').waitFor();
    await page.locator('#workspace-description').fill('Configurato dal gestore workspace');
    mutation = page.waitForResponse(response =>
      response.url() === `${API_ORIGIN}/api/workspace/workspaces/${createdWorkspace.id}/`
      && response.request().method() === 'PATCH',
    );
    await page.getByRole('button', { name: 'Salva workspace' }).click();
    assert.equal((await mutation).status(), 200);
    await waitForEnabledButton(page, 'Salva workspace');

    step = 'protezione ultimo owner';
    mutation = page.waitForResponse(response =>
      response.url().startsWith(`${API_ORIGIN}/api/workspace/workspace-users/`)
      && response.request().method() === 'DELETE',
    );
    await page.getByRole('button', { name: 'Revoca' }).click();
    assert.equal((await mutation).status(), 400);
    await page.getByText('Operazione non riuscita.').waitFor();
    assert.equal(await page.getByLabel(`Ruolo di ${input.ownerUsername}@example.test`).inputValue(), 'owner');

    step = 'configurazione Ticket da owner';
    await page.getByRole('link', { name: 'Configura Ticket' }).click();
    await page.locator('#ticket-company-name').waitFor();
    await page.locator('#ticket-company-name').fill(`${input.companyName} Owner`);
    mutation = page.waitForResponse(response =>
      response.url() === `${API_ORIGIN}/api/plugin-ticket/configuration/companies/`
      && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Aggiungi', exact: true }).click();
    assert.equal((await mutation).status(), 201);
    await page.getByRole('heading', { name: `${input.companyName} Owner` }).waitFor();
    await logout(page);

    console.log(`PASS: amministrazione Console centrale/owner, Ticket config e ultimo owner (workspace ${createdWorkspace.id}).`);
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  const detail = diagnostic ? `, ${diagnostic}` : '';
  console.error(`FAIL amministrazione Console (${step}${detail}): ${error.name}`);
  process.exitCode = 1;
});
