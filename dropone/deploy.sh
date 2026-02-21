#!/data/data/com.termux/files/usr/bin/bash
# ============================================================================
# DropOne — Termux Deploy Script
# 
# Usage:
#   1. Télécharge le zip depuis Claude
#   2. Extrait dans ~/dropone/
#   3. Lance ce script : bash deploy.sh
# ============================================================================

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${CYAN}${BOLD}🚀 DropOne — Déploiement depuis Termux${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ──────────────────────────────────────────
# 1. Vérifier / installer les dépendances
# ──────────────────────────────────────────
echo -e "${YELLOW}[1/6] Vérification des dépendances...${NC}"

if ! command -v git &> /dev/null; then
    echo "  → Installation de git..."
    pkg install -y git
fi

if ! command -v node &> /dev/null; then
    echo "  → Installation de nodejs..."
    pkg install -y nodejs-lts
fi

if ! command -v npm &> /dev/null; then
    echo "  → npm non trouvé, installation..."
    pkg install -y nodejs-lts
fi

echo -e "${GREEN}  ✓ git $(git --version | cut -d' ' -f3)${NC}"
echo -e "${GREEN}  ✓ node $(node --version)${NC}"
echo -e "${GREEN}  ✓ npm $(npm --version)${NC}"

# ──────────────────────────────────────────
# 2. Installer Vercel CLI
# ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}[2/6] Installation de Vercel CLI...${NC}"

if ! command -v vercel &> /dev/null; then
    npm install -g vercel
fi
echo -e "${GREEN}  ✓ vercel installé${NC}"

# ──────────────────────────────────────────
# 3. Config git
# ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}[3/6] Configuration Git...${NC}"

if [ -z "$(git config --global user.name)" ]; then
    read -p "  Ton nom GitHub : " GIT_NAME
    git config --global user.name "$GIT_NAME"
fi

if [ -z "$(git config --global user.email)" ]; then
    read -p "  Ton email GitHub : " GIT_EMAIL
    git config --global user.email "$GIT_EMAIL"
fi

echo -e "${GREEN}  ✓ git config: $(git config --global user.name) <$(git config --global user.email)>${NC}"

# ──────────────────────────────────────────
# 4. Init repo + commit
# ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}[4/6] Initialisation du repo...${NC}"

cd "$(dirname "$0")"

# Remove deploy script from git tracking
if [ ! -f .gitignore ] || ! grep -q "deploy.sh" .gitignore; then
    echo "deploy.sh" >> .gitignore
fi

if [ -d .git ]; then
    echo "  → Repo git déjà initialisé"
else
    git init
    echo -e "${GREEN}  ✓ git init${NC}"
fi

git add -A
git commit -m "DropOne v2.1 — production ready

- 8 modules Python (FastAPI + Supabase + Stripe + PayPal)
- PWA frontend (2000+ lignes)
- Schema PostgreSQL (8 tables, RLS, triggers)
- 18 bugs critiques corrigés
- SEO meta tags (OG + Twitter)
- AI content generation (OpenAI GPT-4o-mini)
- Push notifications (Web Push + Supabase)
- Seller network + gamification" 2>/dev/null || echo "  → Rien de nouveau à commiter"

echo -e "${GREEN}  ✓ Commit créé${NC}"

FILE_COUNT=$(git ls-files | wc -l)
echo -e "${GREEN}  ✓ ${FILE_COUNT} fichiers trackés${NC}"

# ──────────────────────────────────────────
# 5. Push vers GitHub
# ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/6] Push vers GitHub...${NC}"
echo ""

CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")

if [ -z "$CURRENT_REMOTE" ]; then
    echo -e "  ${BOLD}Tu dois d'abord créer le repo sur github.com :${NC}"
    echo -e "  → github.com/new → Nom: ${CYAN}dropone${NC} → ${RED}Ne coche PAS 'Add README'${NC}"
    echo ""
    read -p "  URL du repo (https://github.com/USER/dropone.git) : " REPO_URL
    
    if [ -z "$REPO_URL" ]; then
        echo -e "${RED}  ✗ URL vide, abandon${NC}"
        exit 1
    fi
    
    git remote add origin "$REPO_URL"
    echo -e "${GREEN}  ✓ Remote ajouté: $REPO_URL${NC}"
else
    echo -e "${GREEN}  ✓ Remote existant: $CURRENT_REMOTE${NC}"
fi

git branch -M main

echo ""
echo -e "  ${BOLD}Push en cours...${NC}"
echo -e "  (GitHub va demander ton username + Personal Access Token)"
echo ""

git push -u origin main

echo ""
echo -e "${GREEN}  ✓ Code pushé sur GitHub !${NC}"

# ──────────────────────────────────────────
# 6. Deploy Vercel
# ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}[6/6] Déploiement Vercel...${NC}"
echo ""
echo -e "  ${BOLD}Option A — Auto-deploy via GitHub (recommandé) :${NC}"
echo -e "  → Va sur ${CYAN}https://vercel.com/new${NC}"
echo -e "  → Import Git Repository → sélectionne ${CYAN}dropone${NC}"
echo -e "  → Framework: Other → Deploy"
echo ""
echo -e "  ${BOLD}Option B — Deploy CLI maintenant :${NC}"
read -p "  Veux-tu déployer via CLI ? (o/n) : " DEPLOY_CLI

if [ "$DEPLOY_CLI" = "o" ] || [ "$DEPLOY_CLI" = "O" ] || [ "$DEPLOY_CLI" = "oui" ]; then
    echo ""
    echo -e "  ${BOLD}Login Vercel...${NC}"
    vercel login
    
    echo ""
    echo -e "  ${BOLD}Déploiement preview...${NC}"
    vercel
    
    echo ""
    read -p "  Tout marche ? Déployer en production ? (o/n) : " DEPLOY_PROD
    if [ "$DEPLOY_PROD" = "o" ] || [ "$DEPLOY_PROD" = "O" ]; then
        vercel --prod
        echo ""
        echo -e "${GREEN}${BOLD}  ✓ DÉPLOYÉ EN PRODUCTION !${NC}"
    fi
fi

# ──────────────────────────────────────────
# Résumé
# ──────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}✅ TERMINÉ !${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Prochaines étapes :${NC}"
echo -e "  1. Configure les ${YELLOW}env vars${NC} dans Vercel Dashboard"
echo -e "     → Settings → Environment Variables"
echo -e "     → Ajoute : SUPABASE_URL, SUPABASE_SERVICE_KEY,"
echo -e "       STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,"
echo -e "       PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_MODE,"
echo -e "       OPENAI_API_KEY, APP_URL"
echo ""
echo -e "  2. Exécute le ${YELLOW}schema SQL${NC} dans Supabase"
echo -e "     → SQL Editor → colle supabase_schema.sql → Run"
echo ""
echo -e "  3. Redéploie : ${CYAN}vercel --prod${NC}"
echo ""
echo -e "  4. Configure le ${YELLOW}webhook Stripe${NC}"
echo -e "     → Developers → Webhooks → URL: /api/webhook/stripe"
echo ""
echo -e "  5. Teste : crée une boutique → checkout → vérifie Supabase"
echo ""
