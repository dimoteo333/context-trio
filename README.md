# context-trio
<img width="2048" height="2048" alt="context-trio" src="https://github.com/user-attachments/assets/e695bc7d-7da3-4b54-94cf-fe5179af65ed" />

**Triad Orchestration System** — 3개의 AI 에이전트가 팀으로 협업하는 소프트웨어 개발 오케스트레이션 프레임워크.

| Agent | Model | Role |
|---|---|---|
| **Architect** | Claude Opus 4.6 | 설계, 태스크 분해, 프롬프트 엔지니어링 |
| **Implementer** | GLM-4.7 | 코드 구현, 디버깅, 테스트 |
| **Auditor** | Gemini 3 Pro | 코드 리뷰, 보안 감사, 문서 정리 |

## 사전 요구사항

- Python 3.12+
- git

## 설치

### 방법 1: pip (권장)

```bash
git clone <repo-url> && cd context-trio
pip install -e .
```

### 방법 2: install.sh

기존 프로젝트에 context-trio 구조를 추가:

```bash
cd your-project
bash /path/to/context-trio/install.sh
```

프로젝트명 지정:

```bash
bash install.sh --name my-awesome-project
```

### 방법 3: trio init

pip 설치 후 다른 프로젝트에서:

```bash
cd your-project
trio init --name my-project
```

## 워크플로우

context-trio는 **plan → implement → review** 사이클을 따릅니다:

### 자동화된 워크플로우 (권장)

```bash
trio task "사용자 인증 시스템 구현"
```

이 명령 하나로 전체 파이프라인이 자동으로 실행됩니다:

```
User Request
    │
    ▼
┌──────────────┐     ┌──────────────┐     ┌────────────┐     ┌──────────┐
│ Auto Plan   │────▶│Auto Implement│────▶│Auto Review │────▶│ approved │
│ (Architect) │     │ (Implementer)│     │ (Auditor)   │     │          │
└──────────────┘     └──────────────┘     └────────────┘     └──────────┘
                                            │
                                            │ (rejected)
                                            ▼
                                      ┌──────────────┐
                                      │ Architect    │ (재설계)
                                      │              │
                                      └──────────────┘
```

### 수동 워크플로우

각 단계를 수동으로 제어하려면:

```
User Request
    │
    ▼
┌──────────┐     ┌──────────────┐     ┌────────────┐     ┌──────────┐
│ planning │────▶│implementation│────▶│   review   │────▶│ approved │
└──────────┘     └──────────────┘     └────────────┘     └──────────┘
                                            │
                                            │ (rejected)
                                            ▼
                                      ┌──────────┐
                                      │ planning  │ (재설계)
                                      └──────────┘
```

### Step 1: Plan (Architect)

```bash
trio plan "사용자 인증 시스템 구현"
```

생성된 프롬프트를 Architect 에이전트(Claude Opus)에 입력하면 Task Packet을 출력합니다.

### Step 2: Add Task

Architect가 생성한 Task Packet을 큐에 추가:

```bash
trio add-task '{"task_id":"TASK-001","title":"JWT 인증 모듈","description":"JWT 기반 인증 미들웨어 구현","acceptance_criteria":["POST /auth/login 동작","토큰 발급 및 검증"],"priority":"high"}'
```

### Step 3: Implement (Implementer)

```bash
trio implement --task-id TASK-001
```

생성된 프롬프트를 Implementer 에이전트(GLM)에 입력합니다.

### Step 4: Review (Auditor)

```bash
trio review --task-id TASK-001
```

생성된 프롬프트를 Auditor 에이전트(Gemini)에 입력합니다.

## 자동화된 오케스트레이션

### `trio task` — 원샷 파이프라인

가장 간단한 방법으로 전체 workflow를 실행합니다:

```bash
trio task "JWT 기반 사용자 인증 시스템 구현"
```

**과정:**

1. **Architect 에이전트가 3단계 계획 생성**
   - Task 분해
   - 실행 계획 수립
   - 승인 기준 정의

2. **Implementer 에이전트가 구현**
   - 코드 작성
   - 테스트 작성
   - 검증 실행

3. **Auditor 에이전트가 리뷰**
   - 코드 품질 검사
   - 보안 점검
   - 승인/거부 결정

4. **자동 Git 커밋** (기본 활성화)
   - `--no-commit` 옵션으로 비활성화 가능

### Step 5: Transition

Auditor가 승인하면:

```bash
trio transition approved --agent auditor
```

거부되면:

```bash
trio transition rejected --agent auditor
```

## CLI 레퍼런스

| Command | Description |
|---|---|
| `trio task <description>` | **전체 파이프라인 자동 실행** (Plan → Implement → Review) |
| `trio status` | 현재 phase, task queue, 최근 activity 표시 |
| `trio plan <request>` | Architect용 시스템 프롬프트 생성 |
| `trio implement [--task-id ID]` | Implementer용 시스템 프롬프트 생성 |
| `trio review [--task-id ID]` | Auditor용 시스템 프롬프트 생성 |
| `trio add-task <json>` | TaskPacket JSON을 큐에 추가 |
| `trio transition <phase>` | 수동 phase 전환 (`--agent` 지정) |
| `trio init [--name NAME]` | 프로젝트 구조 초기화 |
| `trio --version` | 버전 표시 |

## 파일 구조

```
context-trio/
├── CLAUDE.md              # 공유 규칙 (immutable)
├── AGENTS.md              # 에이전트 페르소나 정의
├── README.md              # 이 파일
├── pyproject.toml         # 패키지 설정
├── install.sh             # 부트스트랩 스크립트
├── src/trio/
│   ├── __init__.py        # 패키지 초기화
│   ├── __main__.py        # python -m trio 진입점
│   ├── cli.py             # Typer CLI 앱
│   ├── schemas.py         # Pydantic v2 모델
│   ├── context.py         # CONTEXT.json 관리자
│   ├── state_machine.py   # Phase 전이 검증
│   ├── prompts.py         # 에이전트별 프롬프트 빌더
│   ├── exceptions.py      # 커스텀 예외
│   ├── agents.py         # 에이전트 실행기 (AgentExecutor)
│   ├── config.py         # 에이전트 설정 관리
│   └── orchestrator.py   # 자동화된 파이프라인 조정자
├── docs/
│   ├── CONTEXT.json       # 런타임 상태 (Single Source of Truth)
│   ├── PRD.md             # 제품 요구사항
│   ├── ARCHITECTURE.md    # 시스템 아키텍처
│   ├── DECISIONS.md       # 아키텍처 결정 기록
│   ├── CHANGELOG.md       # 변경 이력
│   └── logs/              # 아카이브된 reasoning logs
├── src/                   # 소스 코드
└── tests/                 # 테스트 코드
```

## 핵심 개념: prompts.py

`prompts.py`는 context-trio의 핵심 가치입니다. 각 에이전트에게 제공되는 프롬프트를 5개 레이어로 조립합니다:

1. **Identity** — AGENTS.md의 에이전트 페르소나
2. **Rules** — CLAUDE.md의 관련 규칙 섹션
3. **Context** — 현재 CONTEXT.json 상태 요약
4. **Task** — 구체적 작업 페이로드 (TaskPacket 또는 user request)
5. **Format** — 기대하는 출력 JSON 스키마

이를 통해 각 에이전트는 **자신이 누구인지, 무엇을 해야 하는지, 어떤 제약이 있는지**를 완전히 이해한 상태에서 작업합니다.

## FAQ

**Q: `trio task`와 수동 명령의 차이점은?**
A: `trio task`는 전체 Plan → Implement → Review 사이클을 자동으로 실행합니다. 각 단계를 개별적로 제어하려면 `trio plan`, `trio implement`, `trio review`를 사용하세요.

**Q: 에이전트를 직접 호출하나요?**
A: AGENTS.md에 정의된 모델이 권장되지만, 비슷한 능력의 다른 모델로 대체할 수 있습니다.

**Q: CONTEXT.json이 꼬이면 어떻게 하나요?**
A: `trio init`을 다시 실행하면 CONTEXT.json이 없는 경우에만 새로 생성됩니다. 수동으로 수정하거나, 백업에서 복원하세요.

**Q: 에이전트 설정은 어디서 하나요?**
A: 자동화된 `trio task`를 사용하려면 `~/.config/trio/config.toml` 파일에 각 에이전트의 CLI 명령을 설정해야 합니다. 자세한 내용은 `src/trio/config.py`를 참고하세요.

**Q: 기존 프로젝트에 적용할 수 있나요?**
A: 네. `install.sh` 또는 `trio init`은 기존 파일을 덮어쓰지 않으며, 없는 파일만 생성합니다.
