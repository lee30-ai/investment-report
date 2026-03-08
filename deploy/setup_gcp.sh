#!/bin/bash
# GCP 초기 설정 스크립트
# 실행 전: gcloud auth login 완료 필요

set -e

PROJECT_ID="my-invest-100"
REGION="asia-northeast3"   # 서울 리전
SERVICE_ACCOUNT="investment-report-sa"

echo "=== GCP 프로젝트 설정 ==="
gcloud config set project $PROJECT_ID

echo "=== 필요한 API 활성화 ==="
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

echo "=== Artifact Registry 저장소 생성 ==="
gcloud artifacts repositories create investment-report \
  --repository-format=docker \
  --location=$REGION \
  --description="Investment report Docker images" \
  2>/dev/null || echo "저장소가 이미 존재합니다"

echo "=== 서비스 계정 생성 ==="
gcloud iam service-accounts create $SERVICE_ACCOUNT \
  --display-name="Investment Report Service Account" \
  2>/dev/null || echo "서비스 계정이 이미 존재합니다"

SA_EMAIL="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== 서비스 계정 권한 부여 ==="
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Build 서비스 계정에 Artifact Registry 쓰기 권한 부여
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

echo "=== Telegram 시크릿 저장 ==="
echo -n "${TELEGRAM_BOT_TOKEN}" | gcloud secrets create TELEGRAM_BOT_TOKEN \
  --data-file=- --replication-policy=automatic 2>/dev/null || \
  echo -n "${TELEGRAM_BOT_TOKEN}" | gcloud secrets versions add TELEGRAM_BOT_TOKEN --data-file=-

echo -n "${TELEGRAM_CHAT_ID}" | gcloud secrets create TELEGRAM_CHAT_ID \
  --data-file=- --replication-policy=automatic 2>/dev/null || \
  echo -n "${TELEGRAM_CHAT_ID}" | gcloud secrets versions add TELEGRAM_CHAT_ID --data-file=-

echo ""
echo "=== 설정 완료 ==="
echo "다음 단계: ./deploy/build_and_deploy.sh 실행"
