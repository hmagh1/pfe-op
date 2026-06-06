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

        stage('Build Images') {
            steps {
                echo 'Build des images backend/frontend...'
                sh 'docker compose build backend frontend'
            }
        }

        stage('Start Services') {
            steps {
                echo 'Démarrage des services...'
                sh 'docker compose up -d mysql backend frontend adminer'
            }
        }

        stage('Backend Health Check') {
            steps {
                echo 'Vérification API backend...'
                sh '''
                    sleep 15
                    curl -f http://backend:8000/api/health
                '''
            }
        }

        stage('Frontend Health Check') {
            steps {
                echo 'Vérification frontend...'
                sh '''
                    curl -f http://frontend:15175
                '''
            }
        }

        stage('API Jobs Check') {
            steps {
                echo 'Vérification route /api/jobs...'
                sh '''
                    curl -f http://backend:8000/api/jobs
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
            sh 'docker compose ps || true'
            sh 'docker compose logs --tail=100 backend || true'
            sh 'docker compose logs --tail=100 frontend || true'
            sh 'docker compose logs --tail=100 mysql || true'
        }
    }
}