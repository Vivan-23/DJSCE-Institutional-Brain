// CI/CD for production (docs/DEPLOYMENT.md). Jenkins runs on the VM (deploy/jenkins/), triggered by the
// GitHub push webhook. Test → pre-deploy DB dump → sync code into DEPLOY_DIR → rebuild → health check.
// DEPLOY_DIR keeps its own .env and institution.yaml (real members); data volumes are never touched.
pipeline {
    agent any
    options {
        disableConcurrentBuilds()
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }
    environment {
        DEPLOY_DIR = '/home/ubuntu/djsce-brain'
        BACKUP_DIR = '/home/ubuntu/backups'
    }
    stages {
        stage('Backend tests') {
            steps {
                // Build from the workspace (context goes over the Docker socket), then run pytest in it.
                sh 'docker build -t djsce-ci-backend backend'
                sh '''
                    docker run --rm -i --entrypoint sh \
                      -e GROQ_API_KEY=ci-test-key -e NEO4J_PASSWORD=ci-test-password \
                      -e SECRET_KEY=ci-test-secret-key-must-be-long-enough \
                      -e INSTITUTION_CONFIG=/tmp/institution.yaml \
                      djsce-ci-backend -c "cat > /tmp/institution.yaml && python -m pytest -q -p no:cacheprovider" \
                      < institution.yaml
                '''
            }
        }
        stage('Frontend lint + types') {
            steps {
                sh '''
                    tar -C frontend --exclude=node_modules --exclude=.next -cf - . \
                    | docker run --rm -i node:20-alpine sh -c \
                      "mkdir /w && cd /w && tar xf - && npm ci --no-audit --no-fund && npm run lint && npx tsc --noEmit"
                '''
            }
        }
        stage('Pre-deploy backup') {
            steps {
                // Startup runs `alembic upgrade head` on real data: keep a dump to roll back to (last 10 kept).
                sh '''
                    mkdir -p "$BACKUP_DIR"
                    cd "$DEPLOY_DIR"
                    docker compose exec -T postgres pg_dump -U djsce_brain_user -Fc djsce_brain_db \
                      > "$BACKUP_DIR/predeploy-$(date +%Y%m%d-%H%M)-$(echo "$GIT_COMMIT" | cut -c1-7).dump"
                    ls -1t "$BACKUP_DIR"/predeploy-*.dump | tail -n +11 | xargs -r rm -f
                '''
            }
        }
        stage('Deploy') {
            steps {
                sh '''
                    rsync -a --delete \
                      --exclude=.git --exclude=.env --exclude=institution.yaml --exclude=REVISION \
                      --exclude=publication --exclude=brag-output --exclude=mock_institutional_data \
                      --exclude=creds.txt \
                      ./ "$DEPLOY_DIR"/
                    echo "$GIT_COMMIT" > "$DEPLOY_DIR/REVISION"
                    cd "$DEPLOY_DIR"
                    docker compose up -d --build --remove-orphans
                '''
            }
        }
        stage('Health check') {
            steps {
                sh '''
                    for i in $(seq 1 30); do
                      curl -fsS http://djsce_backend:8001/health && curl -fsS -o /dev/null http://djsce_frontend:3000/ \
                        && echo " healthy" && exit 0
                      sleep 10
                    done
                    echo "Stack not healthy after 5 minutes"; exit 1
                '''
            }
        }
    }
    post {
        failure { sh 'cd "$DEPLOY_DIR" && docker compose logs --tail=150 backend frontend || true' }
        always { sh 'docker image prune -f >/dev/null || true' }
    }
}
