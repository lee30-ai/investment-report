#!/bin/bash
# Docker 이미지 빌드 & Cloud Run Job 배포 스크립트

set -e

PROJECT_ID="my-invest-100"
REGION="asia-northeast3"
IMAGE="asia-northeast3-docker.pkg.dev/${PROJECT_ID}/investment-report/app"
JOB_NAME="investment-report"
SA_EMAIL="investment-report-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== Docker 이미지 빌드 및 푸시 ==="
gcloud auth configure-docker asia-northeast3-docker.pkg.dev --quiet
docker build -t "${IMAGE}:latest" .
docker push "${IMAGE}:latest"

echo "=== Cloud Run Job 배포 ==="
gcloud run jobs deploy $JOB_NAME \
  --image="${IMAGE}:latest" \
  --region=$REGION \
  --service-account=$SA_EMAIL \
  --set-secrets="TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_CHAT_ID=TELEGRAM_CHAT_ID:latest" \
  --task-timeout=600 \
  --max-retries=1 \
  --memory=512Mi \
  --cpu=1

echo "=== Cloud Scheduler 설정 (매일 오전 7시 KST) ==="
gcloud scheduler jobs create http ${JOB_NAME}-scheduler \
  --location=$REGION \
  --schedule="0 7 * * *" \
  --time-zone="Asia/Seoul" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
  --message-body="" \
  --oauth-service-account-email=$SA_EMAIL \
  2>/dev/null && echo "스케줄러 생성 완료" || \
  gcloud scheduler jobs update http ${JOB_NAME}-scheduler \
    --location=$REGION \
    --schedule="0 7 * * *" \
    --time-zone="Asia/Seoul" && echo "스케줄러 업데이트 완료"

echo ""
echo "=== 배포 완료 ==="
echo "매일 오전 7시(KST) 자동 실행됩니다"
echo ""
echo "수동 실행:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
