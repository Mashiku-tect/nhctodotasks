# CI/CD for a Local Server (`10.11.5.59`)

This project can use GitHub Actions for CI and a self-hosted GitHub runner for CD.

## Why this approach

Your server address `10.11.5.59` is a private LAN IP. A normal GitHub-hosted runner usually cannot SSH or deploy to that machine unless you expose the network, use a VPN, or set up port forwarding. A self-hosted runner avoids that problem.

## Suggested flow

1. Push code to GitHub.
2. GitHub Actions runs CI in the cloud:
   - install dependencies
   - run `python manage.py check`
3. If CI passes and the branch is `main`, a self-hosted runner installed on `10.11.5.59` performs deployment.
4. The server updates the repo and runs:
   - `docker compose up -d --build`

## What to install on `10.11.5.59`

- Git
- Docker Desktop or Docker Engine with Compose support
- A GitHub self-hosted runner

## Self-hosted runner setup

In GitHub:

1. Open the repository.
2. Go to `Settings -> Actions -> Runners`.
3. Click `New self-hosted runner`.
4. Choose Windows if your server is Windows.
5. Install it on `10.11.5.59`.
6. Add a custom label named `nhctodo`.

The workflow in `.github/workflows/ci-cd.yml` expects these labels:

- `self-hosted`
- `windows`
- `nhctodo`

## Deployment directory

The workflow currently deploys from:

`D:\apps\nhctodotasks-main`

Clone your repository there on the server, or change `DEPLOY_PATH` in the workflow to your real path.

## Required server files

Make sure the server deployment folder has:

- `.env.docker`
- Docker running
- access to pull the repository

Do not commit `.env.docker` with real secrets.

## First-time server commands

After cloning the repo on the server:

```powershell
cd D:\apps\nhctodotasks-main
docker compose up -d --build
```

## Notes

- CI uses SQLite, so validation can run without the production MySQL server.
- CD assumes the deployment branch is `main`.
- If your server is Linux instead of Windows, the workflow and `scripts/deploy.ps1` should be replaced with a shell-based deploy script.
- The current workflow runs `python manage.py check` only. Expanding CI to run `python manage.py test` is a recommended next step after dependencies are available in the validation environment.

## Reproducibility checklist

Before relying on CI/CD for deployment, confirm:

- `.env.example` is kept in sync with local setup requirements
- `.env.docker.example` is kept in sync with deployment requirements
- `requirements.txt` is updated whenever dependencies change
- `docker compose config` succeeds on the deployment host
- `python manage.py check` succeeds in both local and CI environments
