#!/bin/bash
# GLOA Identity deployment: the shared user pool, its groups, post-login hook and
# login.galaxref.com. Every deploy goes through a change set you review first,
# because this stack holds every GLOA staff login.
#
#   ./scripts/deploy.sh            create a change set, show it, ask before applying
#   ./scripts/deploy.sh --preview  create and show the change set only
set -euo pipefail
cd "$(dirname "$0")/.."

STACK=gloa-identity
PROFILE=${AWS_PROFILE:-gloa}
CERT=arn:aws:acm:us-east-1:043848616038:certificate/1499d08a-7bf3-4313-ac51-29b453b991c8
NAME=deploy-$(date +%Y%m%d-%H%M%S)

aws cloudformation validate-template --template-body file://template.yaml --profile "$PROFILE" >/dev/null
aws cloudformation create-change-set --stack-name "$STACK" --change-set-name "$NAME" \
  --template-body file://template.yaml --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=AcmCertificateArn,ParameterValue="$CERT" \
  --tags Key=Application,Value=GLOA-Identity \
  --profile "$PROFILE" >/dev/null
if ! aws cloudformation wait change-set-create-complete --stack-name "$STACK" --change-set-name "$NAME" --profile "$PROFILE" 2>/dev/null; then
  aws cloudformation describe-change-set --stack-name "$STACK" --change-set-name "$NAME" --profile "$PROFILE" --query StatusReason --output text
  exit 1
fi

echo "==> Change set $NAME:"
aws cloudformation describe-change-set --stack-name "$STACK" --change-set-name "$NAME" --profile "$PROFILE" \
  --query 'Changes[].ResourceChange.[Action,LogicalResourceId,ResourceType,Replacement]' --output table

[ "${1:-}" = "--preview" ] && { echo "Preview only; change set left for review: $NAME"; exit 0; }
read -r -p "Apply this change set? [y/N] " answer
[ "$answer" = "y" ] || { echo "Not applied."; exit 0; }
aws cloudformation execute-change-set --stack-name "$STACK" --change-set-name "$NAME" --profile "$PROFILE"
aws cloudformation wait stack-update-complete --stack-name "$STACK" --profile "$PROFILE"
echo "==> $(aws cloudformation describe-stacks --stack-name "$STACK" --profile "$PROFILE" --query 'Stacks[0].StackStatus' --output text)"
