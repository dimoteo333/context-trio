# CLAUDE.md — Triad Orchestration Ruleset

> Triad Orchestration System의 공유 규칙 및 프로토콜 정의.
> 모든 에이전트(Architect, Implementer, Auditor)가 이 규칙을 따릅니다.

---

## 1. Mission & Identity

이 시스템은 **이종 멀티 에이전트 팀(Heterogeneous Multi-Agent Team)**으로서 고품질 소프트웨어를 구축합니다.

| Agent | Model | Primary Role |
|---|---|---|
| **Architect** | Claude Opus 4.6 | 프롬프트 엔지니어링, 설계, 태스크 분해 |
| **Implementer** | GLM-4.7 | 코드 구현, 디버깅, 테스트 |
| **Auditor** | Gemini 3 Pro | 코드 리뷰, 보안 감사, 문서 정리 |

**Core Directive:** Context 유지, 제약 준수, 토큰 낭비 최소화.

---

## 2. Workflow State Machine

프로젝트는 아래 상태(phase)를 순차적으로 진행합니다.

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    ▼                                      │
┌──────────┐   ┌──────────────┐   ┌────────────┐   ┌──────────┐
│ planning │──▶│implementation│──▶│   review   │──▶│ approved │
└──────────┘   └──────────────┘   └────────────┘   └──────────┘
     ▲                                  │
     │                                  │ (rejected)
     │              ┌──────────┐        │
     └──────────────│ rejected │◀───────┘
                    └──────────┘
```

### Phase Definitions

| Phase | Active Agent | Entry Condition | Exit Condition |
|---|---|---|---|
| `planning` | Architect | 새로운 사용자 요청 수신 | Task Packet 생성 완료 |
| `implementation` | Implementer | Task Packet이 `task_queue`에 존재 | Implementation Report 제출 |
| `review` | Auditor | Implementation Report 수신 | Review Report 제출 |
| `approved` | — | Auditor가 `verdict: "approved"` | 다음 task 또는 종료 |
| `rejected` | Architect | Auditor가 `verdict: "rejected"` | 수정된 Task Packet 생성 |

---

## 3. Context Maintenance Protocol (CA-MCP)

### 3.1 Single Source of Truth: `docs/CONTEXT.json`

모든 에이전트는 턴의 시작과 끝에 이 파일을 읽고 업데이트합니다.

```json
{
  "project_name": "context-trio",
  "global_phase": "planning",
  "current_task": null,
  "task_queue": [],
  "completed_tasks": [],
  "active_constraints": {
    "language": ["Python 3.12+", "TypeScript 5.5+"],
    "style": {"python": "black", "typescript": "prettier"},
    "testing": {"framework": ["pytest", "jest"], "min_coverage": 80},
    "typing": "strict"
  },
  "reasoning_logs": [],
  "known_issues": [],
  "last_updated_by": "architect",
  "last_updated_at": "2025-01-01T00:00:00Z"
}
```

### 3.2 Per-Agent Context Protocol

| Agent | Start of Turn | End of Turn |
|---|---|---|
| **Architect** | `global_phase`, `known_issues`, `completed_tasks` 확인 | `global_phase` 전환, `task_queue`에 Task Packet 추가 |
| **Implementer** | `task_queue`에서 현재 task 수령, `active_constraints` 확인 | `reasoning_logs`에 Implementation Report 기록, task 상태 업데이트 |
| **Auditor** | 전체 `CONTEXT.json` + `reasoning_logs` 히스토리 확인 | 완료 task 제거, `known_issues` 업데이트, `CHANGELOG.md` 수정 |

### 3.3 Context Compression Strategy

에이전트 간 컨텍스트 전달 시 토큰을 절약하기 위한 규칙:

1. **File References:** 전체 파일 내용 대신 경로 + 라인 범위 참조 사용
2. **Summary Fields:** 전체 reasoning chain 대신 핵심 결정 사항만 기록
3. **Incremental Updates:** `CONTEXT.json`은 전체 교체가 아닌 필드 단위 업데이트
4. **Log Rotation:** `reasoning_logs`가 50개 초과 시 오래된 항목은 `docs/logs/` 아카이브로 이동

---

## 4. Handoff Protocol

에이전트 간 작업 전달은 구조화된 JSON 메시지를 통해 이루어집니다.

### 4.1 Architect → Implementer

`docs/CONTEXT.json`의 `task_queue`에 Task Packet을 추가합니다.

```json
{
  "handoff": "architect_to_implementer",
  "task_packet": { "...Task Packet Schema (see agents.md)..." },
  "context_summary": "인증 시스템 신규 구축. JWT 기반, FastAPI 사용.",
  "reference_files": ["docs/PRD.md#REQ-001", "docs/ARCHITECTURE.md#auth-module"]
}
```

### 4.2 Implementer → Auditor

구현 완료 후 Implementation Report를 `reasoning_logs`에 기록합니다.

```json
{
  "handoff": "implementer_to_auditor",
  "implementation_report": { "...Implementation Report Schema (see agents.md)..." },
  "review_scope": ["src/auth/router.py", "src/auth/service.py", "tests/test_auth.py"],
  "test_command": "pytest tests/test_auth.py -v --cov=src/auth"
}
```

### 4.3 Auditor → Architect (Rejection Only)

거부 시 Review Report와 함께 구체적 피드백을 Architect에게 전달합니다.

```json
{
  "handoff": "auditor_to_architect",
  "review_report": { "...Review Report Schema (see agents.md)..." },
  "action_required": "acceptance_criteria #3 미충족. 만료 토큰 처리 로직 누락.",
  "suggested_approach": "TokenExpiredError 예외 핸들링 추가 필요"
}
```

---

## 5. File Ownership & Permissions

| File / Directory | Owner | Read | Write |
|---|---|---|---|
| `docs/PRD.md` | Architect | All | Architect only |
| `docs/ARCHITECTURE.md` | Architect | All | Architect only |
| `docs/DECISIONS.md` | Architect | All | Architect only |
| `docs/CONTEXT.json` | Shared | All | All (per protocol) |
| `docs/CHANGELOG.md` | Auditor | All | Auditor only |
| `src/**` | Implementer | All | Implementer only |
| `tests/**` | Implementer | All | Implementer only |
| `CLAUDE.md` | System | All | **None (immutable)** |
| `agends.md` | System | All | Architect only |

---

## 6. Coding Standards

### 6.1 Language & Tooling

| Category | Standard |
|---|---|
| **Python** | 3.12+ (match statements, type unions `X \| Y`) |
| **TypeScript** | 5.5+ (strict mode) |
| **Python Style** | Black formatter |
| **TS Style** | Prettier |
| **Docstrings** | Google Style |
| **Type Checking** | mypy (strict mode) |

### 6.2 Testing Requirements

| Requirement | Threshold |
|---|---|
| **Framework** | pytest (Python), Jest (TypeScript) |
| **Coverage** | > 80% (mandatory) |
| **Test Naming** | `test_<feature>_<scenario>_<expected>` |
| **Test Location** | `tests/` 디렉토리, 소스 구조 미러링 |

### 6.3 Error Handling

- **Bare `except:` 금지** — 반드시 구체적 예외 타입 사용
- **Custom Exceptions:** `src/exceptions.py`에 프로젝트 전용 예외 정의
- **Error Logging:** 모든 예외는 structured logging으로 기록

---

## 7. Prohibited Actions

모든 에이전트에게 적용되는 금지 사항:

| Action | Reason |
|---|---|
| `docs/` 파일 삭제 (Architect 허가 없이) | Context 유실 방지 |
| `CLAUDE.md` 수정 | 시스템 규칙 무결성 보장 |
| `active_constraints` 위반 코드 머지 | 아키텍처 일관성 보장 |
| Bare `except:` 블록 사용 | 디버깅 난이도 증가 방지 |
| 테스트 없는 코드 제출 | 품질 기준 미달 방지 |
| `global_phase`를 역방향 전환 (Architect 외) | 워크플로우 무결성 보장 |

---

## 8. Error Handling & Escalation

워크플로우 진행 중 문제 발생 시 에스컬레이션 경로:

### 8.1 Implementer 에러 처리

```
구현 중 에러 발생
    │
    ├─ 자체 해결 가능? → self-correction loop (최대 3회)
    │       │
    │       └─ 3회 초과 실패 → Architect에게 에스컬레이션
    │
    └─ 아키텍처 제약 충돌? → 즉시 Architect에게 에스컬레이션
```

### 8.2 Auditor 거부 처리

```
Review 거부
    │
    ├─ severity: "minor" → Implementer가 직접 수정 후 재제출
    │
    ├─ severity: "major" → Architect가 Task Packet 수정 후 재할당
    │
    └─ severity: "critical" (보안) → 즉시 작업 중단, Architect 재설계
```

---

## 9. Document Map

프로젝트 내 주요 문서의 역할과 위치:

```
context-trio/
├── CLAUDE.md              ← 공유 규칙 (이 파일, immutable)
├── agends.md              ← 에이전트 페르소나 정의
├── docs/
│   ├── CONTEXT.json       ← 런타임 상태 (Single Source of Truth)
│   ├── PRD.md             ← 제품 요구사항 정의서
│   ├── ARCHITECTURE.md    ← 시스템 아키텍처 문서
│   ├── DECISIONS.md       ← 아키텍처 결정 기록 (ADR)
│   ├── CHANGELOG.md       ← 변경 이력
│   └── logs/              ← 아카이브된 reasoning logs
├── src/                   ← 소스 코드
└── tests/                 ← 테스트 코드
```
