# Security Test Matrix

| Area | Test |
|---|---|
| Authentication | anonymous rejected |
| Authentication | invalid/expired token rejected dove testabile |
| Authorization | authenticated without permission rejected |
| Authorization | allowed role succeeds |
| Object permission | guessed object ID rejected |
| Workspace | workspace A cannot access workspace B |
| Workspace | cross-workspace related FK rejected |
| Mutation | protected owner/workspace fields cannot be escalated |
| Mass assignment | protected fields ignored/rejected |
| Files | invalid type/size/path rejected |
| SSRF | internal/private target rejected quando applicabile |
| AI tool | unauthorized tool rejected |
| AI tool | foreign/hallucinated resource rejected |
| RAG | workspace A retrieval never returns B |
| RAG | malicious retrieved prompt cannot widen permission |
| Output | no secret/token/sensitive field exposed |
| Audit | sensitive action emits audit event |
| Error | no internal traceback/secret exposed |

## Endpoint template

    Endpoint:
    Actor:
    Required role:
    Workspace scoped:
    Object scoped:
    Side effects:
    Sensitive data:

    [ ] anonymous
    [ ] no role
    [ ] correct role
    [ ] wrong workspace
    [ ] foreign related object
    [ ] malformed input
    [ ] privilege escalation
    [ ] expected audit event

## RAG template

    Retriever:
    Resource:
    Workspace filter:
    Additional ACL:
    Vector metadata:

    [ ] correct workspace retrieved
    [ ] other workspace excluded
    [ ] revoked/deleted content excluded
    [ ] prompt injection test
    [ ] model cannot change retrieval scope
