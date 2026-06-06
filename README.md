# MAF WebApp Skeleton

Squelette React + FastAPI pour transformer ton script MAF en application web.

## Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 18000
```

ou double-cliquer `run_backend.bat`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Docker

```bash
docker compose up --build
```

- Backend: http://127.0.0.1:18000/docs
- Frontend: http://127.0.0.1:15173

ou double-cliquer `run_frontend.bat`.

## Étapes prévues

1. Upload `vmliste_remplie.xlsx`
2. Upload `bdd_flux_maf.xlsx`
3. Upload SNIF prod/horsprod
4. Créer job avec BASICAT
5. Lancer analyse
6. Valider/corriger les décisions
7. Télécharger FR / SNIF / MAF

## Important

Le fichier `backend/app/services/maf_engine.py` contient un placeholder.
Au prochain passage, on va y intégrer ton vrai moteur MAF.
