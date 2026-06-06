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

        stage('Clean Old Containers') {
            steps {
                echo 'Nettoyage des anciens conteneurs CI...'
                sh '''
                    docker rm -f maf_mysql maf_adminer pfe-ops-backend pfe-ops-frontend || true
                    docker compose -f docker-compose.ci.yml down -v --remove-orphans || true
                '''
            }
        }

        stage('Build Images') {
            steps {
                echo 'Build des images backend/frontend avec docker-compose.ci.yml...'
                sh 'docker compose -f docker-compose.ci.yml build backend frontend'
            }
        }

        stage('Start Services') {
            steps {
                echo 'Démarrage des services CI...'
                sh 'docker compose -f docker-compose.ci.yml up -d mysql backend frontend adminer'
            }
        }

        stage('Show Containers') {
            steps {
                echo 'État des conteneurs...'
                sh 'docker compose -f docker-compose.ci.yml ps'
            }
        }

        stage('Backend Health Check') {
            steps {
                echo 'Vérification API backend...'
                sh '''
                    sleep 25

                    docker exec pfe-ops-backend python -c "
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
                echo 'Vérification frontend...'
                sh '''
                    docker exec pfe-ops-frontend node -e "
fetch('http://127.0.0.1:15175')
  .then(r => {
    if (!r.ok) process.exit(1);
    console.log('Frontend OK');
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
                echo 'Vérification route /api/jobs...'
                sh '''
                    docker exec pfe-ops-backend python -c "
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
    }

    post {
        success {
            echo 'Pipeline terminée avec succès.'
        }

        failure {
            echo 'Pipeline échouée. Affichage des logs utiles...'
            sh 'docker compose -f docker-compose.ci.yml ps || true'
            sh 'docker compose -f docker-compose.ci.yml logs --tail=120 backend || true'
            sh 'docker compose -f docker-compose.ci.yml logs --tail=120 frontend || true'
            sh 'docker compose -f docker-compose.ci.yml logs --tail=120 mysql || true'
        }
    }
}
