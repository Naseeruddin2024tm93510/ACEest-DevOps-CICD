// ─────────────────────────────────────────────────────────────────────────────
// Jenkinsfile — ACEest Fitness & Gym Management
// Declarative Pipeline: triggered by a GitHub webhook on every push.
// ─────────────────────────────────────────────────────────────────────────────

pipeline {

    agent any                          // run on any available Jenkins agent

    // ── Environment variables ──────────────────────────────────────────────
    environment {
        IMAGE_NAME = "aceest-fitness"
        IMAGE_TAG  = "${env.BUILD_NUMBER}"
        PYTHON_CMD = "python3"
    }

    // ── Pipeline options ───────────────────────────────────────────────────
    options {
        timestamps()                   // prepend timestamps to console output
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()      // prevent parallel builds on same branch
    }

    // ── Triggers ───────────────────────────────────────────────────────────
    triggers {
        // Poll SCM every 5 minutes as a fallback in case webhooks are blocked
        pollSCM('H/5 * * * *')
    }

    stages {

        // ── Stage 1: Checkout ──────────────────────────────────────────────
        stage('Checkout') {
            steps {
                echo 'Cloning repository…'
                checkout scm
                echo "Checkout complete — ${env.GIT_COMMIT}"
            }
        }

        // ── Stage 2: Setup Python environment ─────────────────────────────
        stage('Setup Environment') {
            steps {
                echo 'Setting up Python virtual environment…'
                sh """
                    ${PYTHON_CMD} -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip --quiet
                    pip install -r requirements.txt --quiet
                    echo "Installed packages:"
                    pip list
                """
            }
        }

        // ── Stage 3: Lint (syntax verification) ───────────────────────────
        stage('Lint — Syntax Check') {
            steps {
                echo 'Checking Python syntax…'
                sh """
                    . venv/bin/activate
                    python -m py_compile app.py
                    python -m py_compile test_app.py
                    echo "No syntax errors found"
                """
            }
        }

        // ── Stage 4: Unit Tests ────────────────────────────────────────────
        stage('Unit Tests (Pytest)') {
            steps {
                echo 'Running Pytest test suite…'
                sh """
                    . venv/bin/activate
                    pytest test_app.py -v \
                           --tb=short \
                           --junitxml=test-results.xml \
                           --cov=app \
                           --cov-report=xml:coverage.xml \
                           --cov-report=term-missing
                """
            }
            post {
                always {
                    // Publish JUnit results in Jenkins dashboard
                    junit 'test-results.xml'
                    // Publish coverage if Cobertura plugin is installed
                    // cobertura coberturaReportFile: 'coverage.xml'
                }
            }
        }

        // ── Stage 5: Docker Build ──────────────────────────────────────────
        stage('Docker Build') {
            steps {
                echo 'Building Docker image…'
                sh """
                    docker build \
                        --tag  ${IMAGE_NAME}:${IMAGE_TAG} \
                        --tag  ${IMAGE_NAME}:latest \
                        --pull \
                        .
                    docker images ${IMAGE_NAME}
                """
            }
        }

        // ── Stage 6: Docker Test (Smoke) ───────────────────────────────────
        stage('Docker Smoke Test') {
            steps {
                echo 'Running container smoke test…'
                sh """
                    # Start container in background
                    docker run --rm -d \
                        --name aceest-smoke-\${BUILD_NUMBER} \
                        -p 5099:5000 \
                        ${IMAGE_NAME}:${IMAGE_TAG}

                    # Give the service a few seconds to start
                    sleep 5

                    # Hit the health endpoint
                    curl --fail --silent --max-time 10 http://localhost:5099/health \
                        && echo "Smoke test passed" \
                        || (echo "Smoke test FAILED"; exit 1)

                    # Stop the container
                    docker stop aceest-smoke-\${BUILD_NUMBER}
                """
            }
        }
    }

    // ── Post pipeline actions ──────────────────────────────────────────────
    post {
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline FAILED — check logs above for details.'
        }
        always {
            // Clean up dangling Docker images to reclaim disk space
            sh 'docker image prune -f || true'
        }
        cleanup {
            cleanWs()                  // wipe workspace after every run
        }
    }
}
