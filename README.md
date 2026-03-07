# ACEest Fitness & Gym Management

> **A Flask-based REST API for gym and fitness management, built as part of a DevOps CI/CD pipeline demonstration.**

![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue?logo=githubactions)
![Python](https://img.shields.io/badge/Python-3.12-yellow?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-black?logo=flask)
![Docker](https://img.shields.io/badge/Docker-Containerized-blue?logo=docker)
![Jenkins](https://img.shields.io/badge/Jenkins-Pipeline-red?logo=jenkins)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Application Features](#application-features)
3. [Project Structure](#project-structure)
4. [Local Setup & Execution](#local-setup--execution)
5. [Running Tests Manually](#running-tests-manually)
6. [Docker — Build & Run](#docker--build--run)
7. [GitHub Actions — CI/CD Pipeline](#github-actions--cicd-pipeline)
8. [Jenkins Integration](#jenkins-integration)
9. [API Reference](#api-reference)

---

## Project Overview

ACEest is a Flask REST API that allows gym staff to manage members, log workouts, track weekly progress, and compute fitness metrics (BMI, calorie targets). The project is fully containerised with Docker and ships with an automated CI/CD pipeline that enforces code quality on every commit.

---

## Application Features

| Feature | Endpoint |
|---|---|
| Health check | `GET /health` |
| Create / read / update / delete members | `POST/GET/PUT/DELETE /members` |
| Log workout sessions | `POST /members/{id}/workouts` |
| Track weekly adherence | `POST /members/{id}/progress` |
| BMI calculator | `POST /bmi` |
| Calorie target estimator | `POST /calculate-calories` |
| Membership status check | `GET /members/{id}/membership` |

---

## Project Structure

```
Assignment-2/
├── app.py                        # Flask application (application factory pattern)
├── test_app.py                   # Pytest test suite (40+ test cases)
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Multi-stage, non-root Docker image
├── Jenkinsfile                   # Declarative Jenkins pipeline
├── .github/
│   └── workflows/
│       └── main.yml              # GitHub Actions CI/CD workflow
└── README.md                     # This file
```

---

## Local Setup & Execution

### Prerequisites

- Python 3.10 or later
- `pip`
- (Optional) Docker Desktop

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/aceest-fitness.git
cd aceest-fitness

# 2. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the development server
flask --app app run --debug
```

The service will be available at **http://127.0.0.1:5000**.

#### Quick API smoke test (curl)

```bash
curl http://127.0.0.1:5000/health
# → {"status":"healthy"}

curl -X POST http://127.0.0.1:5000/members \
     -H "Content-Type: application/json" \
     -d '{"name":"Alice","weight_kg":62,"program":"Fat Loss"}'
# → {"id":1,"name":"Alice","calories":1364}
```

---

## Running Tests Manually

### Using Pytest directly

```bash
# Activate virtual environment first (see above), then:
pytest test_app.py -v
```

### With coverage report

```bash
pytest test_app.py -v --cov=app --cov-report=term-missing
```

### Expected output

```
collected 40 items

test_app.py::TestHealthEndpoints::test_root_returns_200          PASSED
test_app.py::TestHealthEndpoints::test_health_returns_200        PASSED
test_app.py::TestMemberCreation::test_create_member_success      PASSED
...
test_app.py::TestMembership::test_expired_membership             PASSED

============ 40 passed in 0.42s ============
```

> **All tests use an isolated in-memory SQLite database** — no files are created on disk.

---

## Docker — Build & Run

### Build the image

```bash
docker build -t aceest-fitness:latest .
```

### Run the container

```bash
docker run -d --name aceest -p 5000:5000 aceest-fitness:latest
```

The API is now accessible at **http://localhost:5000**.

### Run tests inside the container

```bash
docker run --rm \
  -v "$(pwd)/test_app.py:/app/test_app.py:ro" \
  --entrypoint "" \
  aceest-fitness:latest \
  sh -c "pip install pytest pytest-cov -q && pytest test_app.py -v"
```

### Docker image highlights

| Design choice | Reason |
|---|---|
| `python:3.12-slim` base | Smaller attack surface than `python:3.12` full image |
| **Multi-stage build** | Build-time tools never reach the runtime image |
| **Non-root user** (`appuser`) | Prevents privilege escalation inside the container |
| `HEALTHCHECK` instruction | Enables Docker / Kubernetes readiness probing |
| `--no-cache-dir` in `pip install` | Reduces final image size |

---

## GitHub Actions — CI/CD Pipeline

File: `.github/workflows/main.yml`

### Trigger

Every `push` or `pull_request` to **any branch**.

### Jobs

```
push / pull_request
        │
        ▼
┌───────────────────┐
│  build-and-lint   │  (Job 1)
│  ─────────────    │
│  • pip install    │
│  • py_compile     │
│  • import check   │
└────────┬──────────┘
         │ needs: build-and-lint
         ▼
┌───────────────────┐
│   docker-build    │  (Job 2)
│  ─────────────    │
│  • buildx setup   │
│  • docker build   │
│  • verify image   │
└────────┬──────────┘
         │ needs: docker-build
         ▼
┌───────────────────┐
│ automated-tests   │  (Job 3)
│  ─────────────    │
│  • rebuild image  │
│  • docker run     │
│    pytest -v      │
│  • upload cov     │
└───────────────────┘
```

#### Key features

- **Dependency chaining** (`needs:` keyword) — downstream jobs only run if upstream jobs pass.
- **Docker layer caching** (`cache-from/cache-to: type=gha`) — dramatically speeds up repeated builds.
- **Coverage artefact upload** — the `.coverage` file is preserved for 7 days.

---

## Jenkins Integration

File: `Jenkinsfile`

### Prerequisites on the Jenkins server

1. Jenkins with the **Pipeline** plugin installed.
2. Docker available on the Jenkins agent host.
3. Python 3 available on the agent (`python3` in `PATH`).

### Creating the Jenkins project

1. Open Jenkins → **New Item** → name it `aceest-fitness` → select **Pipeline**.
2. Under **Pipeline** section, choose **Pipeline script from SCM**.
3. Set SCM to **Git**, paste your repository URL.
4. Set **Script Path** to `Jenkinsfile`.
5. Save and click **Build Now** to verify.

### Pipeline stages

| # | Stage | What it does |
|---|---|---|
| 1 | **Checkout** | Clones the latest code from GitHub |
| 2 | **Setup Environment** | Creates a Python virtualenv, installs `requirements.txt` |
| 3 | **Lint — Syntax Check** | Runs `py_compile` on `app.py` and `test_app.py` |
| 4 | **Unit Tests (Pytest)** | Executes the full test suite; publishes JUnit XML report |
| 5 | **Docker Build** | Builds the Docker image tagged with the build number |
| 6 | **Docker Smoke Test** | Starts the container and hits `/health`; stops it afterwards |

### Automatic triggers

The Jenkins pipeline polls SCM every five minutes (`H/5 * * * *`) as a fallback. For instant triggers, configure a **GitHub webhook** pointing at `http://<jenkins-host>/github-webhook/`.

---

## API Reference

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service metadata |
| `GET` | `/health` | Liveness probe |

### Members

| Method | Path | Description |
|---|---|---|
| `GET` | `/members` | List all members |
| `POST` | `/members` | Create a new member |
| `GET` | `/members/{id}` | Get member by ID |
| `PUT` | `/members/{id}` | Update member |
| `DELETE` | `/members/{id}` | Delete member |

### Workouts

| Method | Path | Description |
|---|---|---|
| `GET` | `/members/{id}/workouts` | List all workouts for a member |
| `POST` | `/members/{id}/workouts` | Add a workout session |

### Progress

| Method | Path | Description |
|---|---|---|
| `GET` | `/members/{id}/progress` | List weekly progress |
| `POST` | `/members/{id}/progress` | Record weekly adherence |

### Fitness Calculators

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/calculate-calories` | `{ weight_kg, program }` | Estimate daily calories |
| `POST` | `/bmi` | `{ weight_kg, height_cm }` | Compute BMI + category |
| `GET` | `/members/{id}/membership` | — | Check membership status |

---

## Author

**[Your Name]** — M.Tech Student, Introduction to DevOps (CSIZG514/SEZG514)

---

*"Automate everything, test everything, ship with confidence."*
