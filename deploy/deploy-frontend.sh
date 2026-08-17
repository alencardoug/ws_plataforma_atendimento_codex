#!/usr/bin/env bash
# Builds the SPA and deploys it to Firebase Hosting. Run from the repo root
# or from anywhere (this script cds correctly either way). Requires
# `firebase login` and `.firebaserc` to already exist (see DEPLOYMENT.md).
set -euo pipefail

cd "$(dirname "$0")/../frontend"
npm ci
npm run build
cd ..
firebase deploy --only hosting
