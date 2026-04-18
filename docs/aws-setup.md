# AWS Setup (Beyond Tokens — Builder Lab)

## Purpose
Prepare local AWS credentials and CDK tooling for Pack 4 deployment work. Credentials remain **local-only** and must never be committed to this repository.

## Supported authentication methods
- **AWS SSO** (preferred)
- **Access keys** (named profile)

## Example commands (placeholders only)
```bash
# SSO
aws configure sso --profile <your-profile>
aws sso login --profile <your-profile>

# Access keys
aws configure --profile <your-profile>

# Verify auth
AWS_PROFILE=<your-profile> aws sts get-caller-identity

# CDK
cd infra/cdk
npx cdk doctor
AWS_PROFILE=<your-profile> npx cdk bootstrap
```

## Region guidance
Choose a single region for Pack 4 and keep it consistent across AWS CLI and CDK. Use your team’s standard region for development.

## Reminder
- Credentials live only in your local AWS CLI configuration.
- **Never** commit AWS credentials, account IDs, ARNs, or SSO URLs.

## Pre-Pack-4 checklist
- `aws sts get-caller-identity` succeeds
- `npx cdk doctor` succeeds
- `cdk bootstrap` completed
