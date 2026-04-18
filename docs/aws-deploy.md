# AWS Deployment (Beyond Tokens — Builder Lab)

## Purpose
Deploy the minimal MVWM system to AWS using CDK. This doc uses placeholders only.

## Workflow (placeholders)
```bash
npm --prefix infra/cdk install
AWS_PROFILE=<your-profile> make cdk-synth
AWS_PROFILE=<your-profile> make cdk-deploy
AWS_PROFILE=<your-profile> make demo-aws
```

## Notes
- CDK outputs are written to `infra/cdk/cdk-outputs.json`.
- Do not commit credentials, account IDs, or ARNs.
