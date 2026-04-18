#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { BeyondTokensStack } from "../lib/beyond-tokens-stack";

const app = new cdk.App();

new BeyondTokensStack(app, "BeyondTokensStack", {});
