# Posizionamento dei file

```text
mixtum/
├── AGENTS.md
├── ARCHITECTURE.md
├── SECURITY.md
├── TESTING.md
├── DEFINITION_OF_DONE.md
├── README_CODEX.md
├── REPOSITORY_LAYOUT.md
│
├── .agent/
│   └── PLANS.md
│
├── .agents/
│   └── skills/
│       ├── implement-feature/SKILL.md
│       ├── security-review/SKILL.md
│       ├── architecture-review/SKILL.md
│       ├── django-development/SKILL.md
│       ├── angular-development/SKILL.md
│       ├── plugin-development/SKILL.md
│       ├── database-migration/SKILL.md
│       ├── ai-rag-security/SKILL.md
│       ├── keycloak-integration/SKILL.md
│       ├── kubernetes-deployment/SKILL.md
│       └── release-review/SKILL.md
│
├── backend/
│   └── AGENTS.md
├── console/
│   └── AGENTS.md
├── plugins/
│   └── AGENTS.md
├── infrastructure/
│   └── AGENTS.md
│
└── docs/
    ├── engineering/
    │   └── SECURITY_TEST_MATRIX.md
    └── adr/
        └── ADR_TEMPLATE.md
```

## Nota

Se il repository reale usa nomi diversi (`server/`, `frontend/`, `apps/`, ecc.),
spostare gli `AGENTS.md` locali nella directory effettiva a cui devono applicarsi.

Le skill restano invece sotto `.agents/skills/`.
