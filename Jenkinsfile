pipeline {
    agent any

    options {
        timestamps()
    }

    stages {
        stage('Check Docker') {
            steps {
                echo 'Vérification Docker dans Jenkins...'
                sh 'docker --version'
                sh 'docker compose version'
            }
        }

        stage('Clean Old CI Containers') {
            steps {
                echo 'Nettoyage des anciens conteneurs CI sans supprimer les volumes CI...'
                sh '''
                    docker rm -f maf_ci_mysql maf_ci_adminer maf_ci_ollama pfe-ops-ci-backend pfe-ops-ci-frontend || true
                    docker compose -f docker-compose.ci.yml down --remove-orphans || true
                '''
            }
        }

        stage('Build Images') {
            steps {
                echo 'Build des images backend/frontend avec docker-compose.ci.yml...'
                sh 'docker compose -f docker-compose.ci.yml build backend frontend'
            }
        }

        stage('Start CI Services') {
            steps {
                echo 'Démarrage des services CI...'
                sh 'docker compose -f docker-compose.ci.yml up -d mysql ollama backend frontend adminer'
            }
        }

        stage('Show CI Containers') {
            steps {
                echo 'État des conteneurs CI...'
                sh 'docker compose -f docker-compose.ci.yml ps'
            }
        }

        stage('Prepare Ollama Models') {
            steps {
                echo 'Préparation des modèles Ollama CI...'
                sh '''
                    echo "Attente Ollama..."
                    sleep 20

                    docker exec maf_ci_ollama ollama list || true

                    docker exec maf_ci_ollama ollama pull llama3.2:3b
                    docker exec maf_ci_ollama ollama pull llama3.1:8b

                    docker exec maf_ci_ollama ollama list
                '''
            }
        }

        stage('Backend Health Check') {
            steps {
                echo 'Vérification API backend CI...'
                sh '''
                    sleep 10

                    docker exec pfe-ops-ci-backend python -c "
import urllib.request
import sys

url = 'http://127.0.0.1:8000/api/health'

try:
    response = urllib.request.urlopen(url, timeout=10)
    print(response.read().decode())
except Exception as e:
    print(e)
    sys.exit(1)
"
                '''
            }
        }

        stage('Frontend Health Check') {
            steps {
                echo 'Vérification frontend CI...'
                sh '''
                    docker exec pfe-ops-ci-frontend node -e "
fetch('http://127.0.0.1:15175')
  .then(r => {
    if (!r.ok) process.exit(1);
    console.log('Frontend CI OK');
  })
  .catch(e => {
    console.error(e);
    process.exit(1);
  });
"
                '''
            }
        }

        stage('API Jobs Check') {
            steps {
                echo 'Vérification route /api/jobs CI...'
                sh '''
                    docker exec pfe-ops-ci-backend python -c "
import urllib.request
import sys

url = 'http://127.0.0.1:8000/api/jobs'

try:
    response = urllib.request.urlopen(url, timeout=10)
    print(response.read().decode())
except Exception as e:
    print(e)
    sys.exit(1)
"
                '''
            }
        }

        stage('Precheck BASICAT API Check') {
            steps {
                echo 'Vérification route /api/precheck-basicat/GRC CI...'
                sh '''
                    docker exec pfe-ops-ci-backend python -c "
import json
import urllib.request
import sys

url = 'http://127.0.0.1:8000/api/precheck-basicat/GRC'

try:
    response = urllib.request.urlopen(url, timeout=20)
    data = json.loads(response.read().decode())
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if 'ready' not in data:
        print('Champ ready manquant dans le precheck')
        sys.exit(1)

    if 'checks' not in data:
        print('Champ checks manquant dans le precheck')
        sys.exit(1)

except Exception as e:
    print(e)
    sys.exit(1)
"
                '''
            }
        }

        stage('MAF Functional Workflow Test') {
            steps {
                echo 'Test fonctionnel métier MAF + ML sur environnement CI...'
                sh '''
                    docker exec pfe-ops-ci-backend python /app/ci_test_maf_workflow.py
                '''
            }
        }

        stage('LLM / RAG Functional Tests') {
            steps {
                echo 'Test fonctionnel LLM/RAG: MySQL + Excel + Ollama router...'
                sh '''
                    docker exec pfe-ops-ci-backend python /app/ci_test_rag_workflow.py
                '''
            }
        }
    }

    post {
        success {
            echo 'Pipeline terminée avec succès.'
        }

        failure {
            echo 'Pipeline échouée. Affichage des logs utiles...'
            sh 'docker compose -f docker-compose.ci.yml ps || true'
            sh 'docker compose -f docker-compose.ci.yml logs --tail=150 backend || true'
            sh 'docker compose -f docker-compose.ci.yml logs --tail=150 frontend || true'
            sh 'docker compose -f docker-compose.ci.yml logs --tail=150 mysql || true'
            sh 'docker compose -f docker-compose.ci.yml logs --tail=150 ollama || true'
        }

        always {
            echo 'Arrêt des conteneurs CI sans suppression des volumes CI...'
            sh 'docker compose -f docker-compose.ci.yml down --remove-orphans || true'
        }
    }
}