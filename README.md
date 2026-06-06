# Documentation MLOps et CI/CD Jenkins du Projet MAF Automation Studio

## 1. Introduction

Dans le cadre du projet MAF Automation Studio, une architecture MLOps a été mise en place afin d’industrialiser le traitement des flux applicatifs, d’améliorer la qualité des décisions, de capitaliser sur les corrections humaines, et de garantir la stabilité de l’application à travers une pipeline CI/CD automatisée avec Jenkins.

L’objectif principal n’est pas seulement d’intégrer un modèle de Machine Learning, mais de construire un cycle complet permettant de gérer le modèle dans un environnement applicatif réel. Ce cycle couvre la préparation des données, l’entraînement du modèle, la sauvegarde des versions, la promotion d’un modèle actif, le suivi des décisions humaines, ainsi que la validation automatique du projet via Jenkins.

Cette approche permet d’avoir un système évolutif, contrôlé et auditable, où le modèle ML assiste l’utilisateur sans remplacer la validation humaine.

---

## 2. Architecture générale du système

L’architecture du projet repose sur plusieurs composants complémentaires :

* Une application frontend développée en React.
* Un backend développé avec FastAPI.
* Une base de données MySQL pour sauvegarder les jobs, les décisions et les versions de modèles.
* Un modèle Machine Learning basé sur RandomForest.
* Un environnement Docker Compose pour le développement local.
* Un environnement Docker Compose dédié à Jenkins CI.
* Une pipeline Jenkins permettant de builder, lancer et tester automatiquement l’application.
* Un dashboard MLOps permettant de suivre les modèles, les métriques et les décisions.

L’architecture peut être représentée comme suit :

```text
Utilisateur
   ↓
Interface React
   ↓
Backend FastAPI
   ↓
Pre-check BASICAT
   ↓
Génération FR / SNIF / MAF
   ↓
Prédictions ML
   ↓
Validation ou correction humaine
   ↓
Sauvegarde MySQL
   ↓
Réentraînement ML
   ↓
Model Registry / Model Promotion
   ↓
Monitoring MLOps
```

En parallèle, Jenkins intervient sur le cycle de développement :

```text
GitHub
   ↓
Jenkins CI/CD
   ↓
Build Docker
   ↓
Lancement environnement CI
   ↓
Tests techniques
   ↓
Tests fonctionnels métier
   ↓
Validation de la version
```

---

## 3. Rôle de Jenkins dans le projet

Jenkins est utilisé comme outil de CI/CD afin de vérifier automatiquement que chaque nouvelle version du code reste fonctionnelle.

Dans ce projet, Jenkins ne se limite pas à vérifier que le backend et le frontend démarrent. Il exécute également des tests liés au workflow métier MAF.

La pipeline Jenkins réalise les actions suivantes :

```text
1. Récupération du code depuis GitHub.
2. Vérification de Docker et Docker Compose.
3. Nettoyage des anciens conteneurs CI.
4. Build des images Docker backend et frontend.
5. Démarrage d’un environnement CI isolé.
6. Vérification du backend via /api/health.
7. Vérification du frontend.
8. Vérification de la route /api/jobs.
9. Vérification de la route /api/precheck-basicat.
10. Exécution d’un test fonctionnel MAF + ML.
11. Arrêt des conteneurs CI après le test.
12. Conservation de la base CI via un volume Docker persistant.
```

Cette pipeline permet de s’assurer que l’application est toujours capable de fonctionner après chaque modification du code.

---

## 4. Séparation entre environnement local et environnement CI

Afin d’éviter tout conflit entre le développement local et Jenkins, deux environnements distincts ont été mis en place.

L’environnement local utilise :

```text
Backend local :  http://localhost:18000
Frontend local : http://localhost:15175
MySQL local :    maf_mysql
Adminer local :  http://localhost:8081
Volume local :   mysql_data
```

L’environnement Jenkins CI utilise :

```text
Backend CI :     http://localhost:18001
Frontend CI :    http://localhost:15176
MySQL CI :       maf_ci_mysql
Adminer CI :     http://localhost:8082
Volume CI :      mysql_data_ci
```

Cette séparation permet de garantir que Jenkins peut exécuter ses tests sans impacter les données locales utilisées pendant le développement.

Les conteneurs CI sont arrêtés automatiquement à la fin de chaque pipeline Jenkins, mais le volume MySQL CI reste conservé. Cela permet de garder un historique des jobs et modèles générés dans l’environnement de test.

---

## 5. Pre-check BASICAT

Avant de lancer la génération FR, un contrôle préalable du BASICAT est effectué.

Ce pre-check permet de vérifier que les conditions nécessaires au traitement sont réunies. Il améliore la qualité du workflow et évite de lancer des traitements incomplets ou incorrects.

Le pre-check vérifie notamment :

```text
- L’existence du fichier vmliste_remplie.xlsx.
- La présence des colonnes obligatoires dans la VLISTE.
- L’existence du BASICAT saisi.
- Le nombre de lignes trouvées pour ce BASICAT.
- La détection des environnements PROD et/ou HORSPROD.
- L’existence du fichier bdd_flux_maf.xlsx.
- La présence des colonnes obligatoires dans la BDD.
- Le nombre de lignes disponibles dans la BDD.
- La disponibilité d’un modèle ML entraîné.
- Le nombre de versions ML existantes.
- L’existence de décisions historiques pour ce BASICAT.
```

Exemple de résultat de pre-check :

```json
{
  "basicat": "GRC",
  "ready": true,
  "status": "ready",
  "detected_envs": ["prod"],
  "summary": {
    "basicat_rows": 15,
    "model_available": true,
    "model_versions_count": 4,
    "historical_decisions_count": 13
  }
}
```

Si le pre-check est positif, l’utilisateur peut lancer la génération FR. Si le pre-check échoue, l’application affiche les erreurs et bloque la génération.

Cette étape permet d’appliquer une logique de contrôle qualité avant traitement.

---

## 6. Workflow métier MAF

Le workflow principal de l’application suit une logique séquencée.

### Étape 1 : Saisie et contrôle du BASICAT

L’utilisateur saisit un BASICAT dans l’interface. Le backend vérifie que ce BASICAT est présent dans la VLISTE et que les données nécessaires sont disponibles.

### Étape 2 : Génération FR

Après validation du pre-check, l’utilisateur peut lancer la génération FR. Le backend génère les lignes nécessaires et identifie les lignes connues, historiques ou nouvelles.

### Étape 3 : Validation humaine

L’utilisateur peut valider ou corriger les décisions proposées. Les décisions validées ou corrigées sont sauvegardées en base MySQL.

### Étape 4 : Traitement SNIF

Après validation du FR, l’utilisateur traite les fichiers SNIF par environnement. Le système peut traiter PROD et HORSPROD séparément.

### Étape 5 : Génération MAF final

Lorsque les environnements SNIF sont finalisés, l’utilisateur peut générer le fichier MAF final.

Ce workflow garantit que les traitements sont réalisés dans un ordre contrôlé, avec une validation humaine avant les étapes critiques.

---

## 7. Human-in-the-loop

Le projet applique une approche Human-in-the-loop.

Le modèle ML ne prend pas de décision finale de manière autonome. Il propose des valeurs, mais l’utilisateur reste responsable de la validation finale.

Pour chaque ligne, le système peut proposer :

```text
- Un flux.
- Un nom applicatif.
- Un score de confiance.
- Une source de proposition.
```

L’utilisateur peut ensuite :

```text
- Valider la proposition.
- Corriger la proposition.
```

Chaque validation ou correction est sauvegardée dans la base de données. Ces décisions deviennent ensuite des données d’apprentissage pour les futurs entraînements du modèle.

Cette approche permet d’améliorer progressivement le modèle tout en gardant un contrôle humain sur les décisions finales.

---

## 8. Sauvegarde des décisions

Les décisions utilisateur sont sauvegardées dans la table `job_decisions`.

Chaque décision contient notamment :

```text
- decision_id
- job_id
- basicat
- environnement
- phase
- action réalisée
- IP source
- IP destination
- port
- SG source
- SG cible
- flux proposé
- nom proposé
- flux final
- nom final
- score
- modèle ML utilisé
- confiance ML
- statut de validation
- date de création
- date de mise à jour
```

Cette sauvegarde permet :

```text
- La traçabilité des décisions.
- L’audit des validations humaines.
- L’analyse des corrections.
- L’amélioration du modèle ML.
- La réutilisation des décisions historiques sur de futurs jobs.
```

---

## 9. Réutilisation de l’historique

Le système est capable de reconnaître les lignes déjà traitées dans des jobs précédents.

Pour cela, une signature technique est construite à partir des informations de la ligne :

```text
BASICAT
Environnement
Protocole
Port
IP source
IP destination
SG source
SG cible
Direction
```

Cette signature permet de retrouver une décision validée précédemment et de la proposer automatiquement lorsque la même ligne est rencontrée à nouveau.

Cela permet de réduire le nombre de validations manuelles nécessaires et d’accélérer les traitements récurrents.

---

## 10. Modèle Machine Learning

Le projet utilise un modèle RandomForest afin de proposer automatiquement un flux et un nom applicatif à partir des caractéristiques techniques des lignes.

Les features utilisées peuvent inclure :

```text
- protocol
- port
- src_ip
- dst_ip
- flowMainSG
- flowGrefSG
```

Le modèle est entraîné à partir de deux sources :

```text
1. La BDD Excel bdd_flux_maf.xlsx.
2. Les décisions humaines sauvegardées dans MySQL.
```

Cette combinaison permet au modèle d’apprendre à partir des données existantes et des corrections réelles effectuées par les utilisateurs.

Le modèle est sauvegardé au format `.joblib`, et ses métriques sont sauvegardées au format JSON.

---

## 11. Model Registry

Un registre des modèles a été mis en place via la table `model_versions`.

Chaque entraînement crée une nouvelle version de modèle. Les informations sauvegardées incluent :

```text
- model_id
- model_name
- source
- model_path
- metrics_path
- training_rows
- excel_rows
- mysql_rows
- n_classes
- accuracy
- precision
- recall
- f1_score
- is_active
- created_at
```

Le Model Registry permet de conserver l’historique des modèles entraînés, de comparer leurs performances, et de savoir quel modèle est actuellement actif.

---

## 12. Modèle actif

Le projet intègre la notion de modèle actif.

Chaque modèle possède un champ :

```text
is_active = true / false
```

Une seule version du modèle peut être marquée comme active à un instant donné.

Le modèle actif représente la version de référence utilisée ou validée pour la prédiction.

Cela permet de séparer :

```text
- Les modèles entraînés et sauvegardés.
- Le modèle réellement promu comme modèle de production.
```

---

## 13. Promotion du modèle

Une fonctionnalité de promotion du modèle a été ajoutée.

Depuis l’interface MLOps, l’équipe peut promouvoir un modèle comme modèle actif.

Le processus de promotion applique la règle suivante :

```text
1. Tous les modèles sont mis en statut inactif.
2. Le modèle sélectionné est marqué comme actif.
3. L’interface affiche le modèle actif en production.
```

Cette logique permet de contrôler le passage d’un modèle vers le statut actif.

Le cycle MLOps devient donc :

```text
Train → Register → Evaluate → Promote → Active Model → Monitor
```

---

## 14. Dashboard MLOps

L’application contient une section dédiée au monitoring MLOps.

Cette section permet de suivre :

```text
- Le modèle actif.
- Les versions de modèles sauvegardées.
- Le nombre de lignes utilisées pour l’entraînement.
- Les métriques du modèle.
- Les décisions totales.
- Les décisions validées.
- Les décisions corrigées.
- Les décisions liées au ML.
- Le taux d’acceptation ML.
- Le taux de correction ML.
- La confiance moyenne ML.
- La répartition des flux finaux.
```

Le dashboard donne une vue claire sur la performance du modèle et sur l’usage réel des prédictions ML par les utilisateurs.

---

## 15. Monitoring des décisions

Le monitoring des décisions permet d’évaluer la qualité du modèle dans le temps.

Les indicateurs suivis incluent :

```text
- Nombre total de décisions.
- Nombre de décisions validées.
- Nombre de décisions corrigées.
- Nombre de décisions issues du ML.
- Taux d’acceptation des suggestions ML.
- Taux de correction des suggestions ML.
- Confiance moyenne du modèle.
- Répartition des flux finaux.
```

Ces indicateurs permettent d’identifier si le modèle est utile, si les utilisateurs acceptent ses suggestions, ou si trop de corrections sont nécessaires.

---

## 16. Feedback loop

Le système intègre une boucle de feedback.

Chaque fois qu’un utilisateur valide ou corrige une décision, cette information est sauvegardée en base. Lors du prochain entraînement, ces décisions sont réutilisées comme données d’apprentissage.

Le modèle s’améliore donc progressivement grâce aux interactions humaines.

La boucle peut être résumée ainsi :

```text
Prédiction ML
   ↓
Validation ou correction humaine
   ↓
Sauvegarde en base
   ↓
Réentraînement du modèle
   ↓
Nouvelle version du modèle
   ↓
Promotion éventuelle
   ↓
Nouvelle prédiction améliorée
```

---

## 17. Tests fonctionnels Jenkins

Jenkins exécute également un script de test fonctionnel métier.

Ce script teste automatiquement :

```text
- La disponibilité de l’API.
- La lecture automatique des BASICAT depuis la VLISTE.
- La création d’un job.
- La génération FR.
- La sauvegarde du job.
- L’entraînement du modèle ML.
- La création d’une version de modèle.
- La disponibilité des statistiques MLOps.
```

Cela permet de vérifier que le workflow principal reste fonctionnel après chaque modification du code.

---

## 18. Persistance des données CI

L’environnement Jenkins CI utilise un volume Docker persistant :

```text
mysql_data_ci
```

Cela permet de conserver les données générées par Jenkins entre deux exécutions.

Cependant, les conteneurs CI sont arrêtés après chaque pipeline afin de garder un environnement propre.

La persistance est donc assurée au niveau de la base de données, sans laisser les conteneurs CI tourner inutilement.

---

## 19. Sécurité et contrôle

Le système ne permet pas au modèle ML de modifier directement les décisions finales sans intervention humaine.

Les décisions sensibles restent contrôlées par l’utilisateur.

Cette approche apporte plusieurs avantages :

```text
- Réduction du risque d’erreur automatique.
- Traçabilité des décisions.
- Auditabilité.
- Possibilité de correction.
- Amélioration continue du modèle.
```

---

## 20. Avantages de l’architecture MLOps

L’architecture mise en place apporte plusieurs bénéfices :

```text
- Automatisation du workflow MAF.
- Contrôle qualité avant traitement.
- Réduction des validations répétitives grâce à l’historique.
- Amélioration continue du modèle ML.
- Conservation des versions de modèles.
- Promotion contrôlée d’un modèle actif.
- Monitoring des performances ML.
- Pipeline Jenkins automatisée.
- Séparation propre entre développement local et environnement CI.
- Traçabilité complète des décisions.
```

---

## 21. Limites actuelles

Certaines limites peuvent encore être améliorées :

```text
- Le drift monitoring avancé n’est pas encore implémenté.
- La promotion automatique selon un seuil de performance peut être ajoutée.
- Le rollback automatique vers un ancien modèle peut être ajouté.
- Des tests unitaires backend plus détaillés peuvent être ajoutés.
- Des tests frontend automatisés peuvent être ajoutés.
- Le déploiement vers un serveur distant n’est pas encore automatisé.
```

Ces limites ne bloquent pas le fonctionnement du système, mais représentent des pistes d’amélioration pour une future version.

---

## 22. Améliorations futures

Les améliorations possibles incluent :

```text
- Ajout d’un système de détection de drift.
- Ajout d’un seuil automatique de promotion des modèles.
- Ajout d’un bouton de rollback vers un ancien modèle.
- Ajout de tests unitaires avec pytest.
- Ajout de tests frontend.
- Ajout de notifications Jenkins.
- Ajout d’un rapport automatique de performance ML.
- Intégration future d’un module LLM/RAG pour interroger les décisions et documents.
```

---

## 23. Conclusion

Le projet MAF Automation Studio intègre une architecture MLOps complète et cohérente.

Le système ne se limite pas à entraîner un modèle ML. Il met en place un cycle complet comprenant la validation des données, l’assistance par Machine Learning, la validation humaine, la sauvegarde des décisions, le réentraînement, le versioning des modèles, la promotion d’un modèle actif, le monitoring MLOps et la validation automatique via Jenkins.

Cette architecture permet d’obtenir un système plus fiable, plus traçable et plus professionnel.

Le cycle final peut être résumé comme suit :

```text
Pre-check BASICAT
   ↓
Génération FR / SNIF
   ↓
Prédiction ML
   ↓
Validation humaine
   ↓
Sauvegarde des décisions
   ↓
Réentraînement ML
   ↓
Model Registry
   ↓
Model Promotion
   ↓
Monitoring MLOps
   ↓
Validation Jenkins CI/CD
```

Cette approche démontre une vision industrielle du Machine Learning, orientée qualité, auditabilité et amélioration continue.
