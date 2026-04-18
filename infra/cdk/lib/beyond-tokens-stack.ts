import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwv2Integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as logs from "aws-cdk-lib/aws-logs";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as path from "path";

export class BeyondTokensStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const artifactsBucket = new s3.Bucket(this, "ArtifactsBucket", {
      versioned: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.KMS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      enforceSSL: true,
    });

    const stateTable = new dynamodb.Table(this, "StateTable", {
      tableName: "beyond_tokens_state",
      partitionKey: { name: "state_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const runsTable = new dynamodb.Table(this, "RunsTable", {
      tableName: "beyond_tokens_runs",
      partitionKey: { name: "run_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const policiesTable = new dynamodb.Table(this, "PoliciesTable", {
      tableName: "beyond_tokens_policies",
      partitionKey: { name: "policy_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const agentcoreMemoryTable = new dynamodb.Table(this, "AgentCoreMemoryTable", {
      tableName: "beyond_tokens_agentcore_memory",
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "sk", type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: "expires_at",
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const lambdaEnv = {
      ARTIFACT_BUCKET: artifactsBucket.bucketName,
      STATE_TABLE: stateTable.tableName,
      RUNS_TABLE: runsTable.tableName,
      POLICIES_TABLE: policiesTable.tableName,
      FIXTURE_NAME: "trading_path.json",
      ENABLE_BEDROCK_PLANNER: this.node.tryGetContext("enableBedrockPlanner") ? "1" : "0",
      ENABLE_LOCAL_PLANNER: this.node.tryGetContext("enableLocalPlanner") ? "1" : "0",
      BEDROCK_MODEL_ID: this.node.tryGetContext("bedrockModelId") ?? "",
    };

    const lambdaPath = path.join(__dirname, "..", "..", "..");
    const lambdaAsset = lambda.Code.fromAsset(lambdaPath, {
      exclude: [
        "infra/cdk/**",
        "**/cdk.out/**",
        "**/node_modules/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/*.pyc",
        "**/.git/**",
        "**/.DS_Store",
        "tmp/**",
      ],
    });

    const pythonDepsLayer = new lambda.LayerVersion(this, "PythonDepsLayer", {
      code: lambda.Code.fromAsset(path.join(lambdaPath, "infra", "cdk", "layers", "python-deps")),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: "Python dependencies for Beyond Tokens lambdas",
    });

    const simulateFn = new lambda.Function(this, "SimulateFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "services.aws.handlers.simulate_handler.handler",
      code: lambdaAsset,
      environment: lambdaEnv,
      timeout: cdk.Duration.seconds(30),
      reservedConcurrentExecutions: 1,
      layers: [pythonDepsLayer],
    });

    const executeFn = new lambda.Function(this, "ExecuteFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "services.aws.handlers.execute_handler.handler",
      code: lambdaAsset,
      environment: lambdaEnv,
      timeout: cdk.Duration.seconds(30),
      reservedConcurrentExecutions: 1,
      layers: [pythonDepsLayer],
    });

    const statusFn = new lambda.Function(this, "StatusFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "services.aws.handlers.status_handler.handler",
      code: lambdaAsset,
      environment: lambdaEnv,
      timeout: cdk.Duration.seconds(30),
      reservedConcurrentExecutions: 1,
      layers: [pythonDepsLayer],
    });

    const healthFn = new lambda.Function(this, "HealthFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "services.aws.handlers.health_handler.handler",
      code: lambdaAsset,
      timeout: cdk.Duration.seconds(10),
      layers: [pythonDepsLayer],
    });

    const agentcoreHelloFn = new lambda.Function(this, "AgentCoreHelloFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "services.aws.handlers.agentcore_hello_handler.handler",
      code: lambdaAsset,
      environment: {
        ARTIFACT_BUCKET: artifactsBucket.bucketName,
      },
      timeout: cdk.Duration.seconds(10),
      reservedConcurrentExecutions: 2,
      layers: [pythonDepsLayer],
    });

    const agentcoreToolsFn = new lambda.Function(this, "AgentCoreToolsFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "services.aws.handlers.agentcore_tools_handler.handler",
      code: lambdaAsset,
      environment: {
        ARTIFACT_BUCKET: artifactsBucket.bucketName,
        FIXTURE_NAME: "trading_path.json",
      },
      timeout: cdk.Duration.seconds(30),
      reservedConcurrentExecutions: 2,
      layers: [pythonDepsLayer],
    });

    const agentcoreMemoryFn = new lambda.Function(this, "AgentCoreMemoryFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "services.aws.handlers.agentcore_memory_handler.handler",
      code: lambdaAsset,
      environment: {
        ARTIFACT_BUCKET: artifactsBucket.bucketName,
        ENABLE_AGENTCORE_MEMORY: "1",
        AGENTCORE_MEMORY_BACKEND: "dynamodb",
        AGENTCORE_MEMORY_TABLE: agentcoreMemoryTable.tableName,
        AGENTCORE_MEMORY_TTL_SECONDS: "86400",
      },
      timeout: cdk.Duration.seconds(15),
      reservedConcurrentExecutions: 1,
      layers: [pythonDepsLayer],
    });

    const agentcoreLoopFn = new lambda.Function(this, "AgentCoreLoopFn", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "services.aws.handlers.agentcore_loop_handler.handler",
      code: lambdaAsset,
      environment: {
        ...lambdaEnv,
        RUNS_TABLE: runsTable.tableName,
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 128,
      reservedConcurrentExecutions: 1,
      logRetention: logs.RetentionDays.TWO_WEEKS,
      layers: [pythonDepsLayer],
    });

    const agentcoreHelloApi = new apigwv2.HttpApi(this, "AgentCoreHelloApi", {
      apiName: "agentcore-hello",
    });

    const agentcoreAccessLogGroup = new logs.LogGroup(this, "AgentCoreHttpApiAccessLogs", {
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const defaultStage = agentcoreHelloApi.defaultStage?.node.defaultChild as apigwv2.CfnStage;
    if (defaultStage) {
      defaultStage.accessLogSettings = {
        destinationArn: agentcoreAccessLogGroup.logGroupArn,
        format: JSON.stringify({
          requestId: "$context.requestId",
          ip: "$context.identity.sourceIp",
          requestTime: "$context.requestTime",
          httpMethod: "$context.httpMethod",
          routeKey: "$context.routeKey",
          status: "$context.status",
          protocol: "$context.protocol",
          responseLength: "$context.responseLength",
          integrationErrorMessage: "$context.integrationErrorMessage",
        }),
      };
    }

    agentcoreHelloApi.addRoutes({
      path: "/health",
      methods: [apigwv2.HttpMethod.GET],
      integration: new apigwv2Integrations.HttpLambdaIntegration(
        "HealthIntegration",
        healthFn,
      ),
    });

    agentcoreHelloApi.addRoutes({
      path: "/agentcore/base",
      methods: [apigwv2.HttpMethod.POST],
      integration: new apigwv2Integrations.HttpLambdaIntegration(
        "AgentCoreHelloIntegration",
        agentcoreHelloFn,
      ),
    });

    agentcoreHelloApi.addRoutes({
      path: "/agentcore/tools",
      methods: [apigwv2.HttpMethod.POST],
      integration: new apigwv2Integrations.HttpLambdaIntegration(
        "AgentCoreToolsIntegration",
        agentcoreToolsFn,
      ),
    });

    agentcoreHelloApi.addRoutes({
      path: "/agentcore/memory",
      methods: [apigwv2.HttpMethod.POST],
      integration: new apigwv2Integrations.HttpLambdaIntegration(
        "AgentCoreMemoryIntegration",
        agentcoreMemoryFn,
      ),
    });

    agentcoreHelloApi.addRoutes({
      path: "/agentcore/loop",
      methods: [apigwv2.HttpMethod.POST],
      integration: new apigwv2Integrations.HttpLambdaIntegration(
        "AgentCoreLoopIntegration",
        agentcoreLoopFn,
      ),
    });

    const loopRequestsMetric = new cloudwatch.Metric({
      namespace: "BeyondTokens/AgentCoreLoop",
      metricName: "Requests",
      dimensionsMap: { service: "beyond-tokens", component: "agentcore-loop", mode: "agentcore-loop" },
      statistic: "Sum",
      period: cdk.Duration.minutes(5),
    });
    const loopClientErrorsMetric = new cloudwatch.Metric({
      namespace: "BeyondTokens/AgentCoreLoop",
      metricName: "ClientErrors",
      dimensionsMap: { service: "beyond-tokens", component: "agentcore-loop", mode: "agentcore-loop" },
      statistic: "Sum",
      period: cdk.Duration.minutes(5),
    });
    const loopServerErrorsMetric = new cloudwatch.Metric({
      namespace: "BeyondTokens/AgentCoreLoop",
      metricName: "ServerErrors",
      dimensionsMap: { service: "beyond-tokens", component: "agentcore-loop", mode: "agentcore-loop" },
      statistic: "Sum",
      period: cdk.Duration.minutes(5),
    });
    const loopLatencyP50Metric = new cloudwatch.Metric({
      namespace: "BeyondTokens/AgentCoreLoop",
      metricName: "LatencyMs",
      dimensionsMap: { service: "beyond-tokens", component: "agentcore-loop", mode: "agentcore-loop" },
      statistic: "p50",
      period: cdk.Duration.minutes(5),
    });
    const loopLatencyP95Metric = new cloudwatch.Metric({
      namespace: "BeyondTokens/AgentCoreLoop",
      metricName: "LatencyMs",
      dimensionsMap: { service: "beyond-tokens", component: "agentcore-loop", mode: "agentcore-loop" },
      statistic: "p95",
      period: cdk.Duration.minutes(5),
    });

    const loopServerErrorsAlarm = new cloudwatch.Alarm(this, "AgentCoreLoopServerErrorsAlarm", {
      metric: loopServerErrorsMetric,
      threshold: 1,
      evaluationPeriods: 1,
      datapointsToAlarm: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: "AgentCore loop server errors detected in the last 5 minutes",
    });

    const loopLatencyP95Alarm = new cloudwatch.Alarm(this, "AgentCoreLoopLatencyP95Alarm", {
      metric: loopLatencyP95Metric,
      threshold: 1000,
      evaluationPeriods: 1,
      datapointsToAlarm: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
      alarmDescription: "AgentCore loop p95 latency above 1000ms over 5 minutes",
    });

    const loopDashboard = new cloudwatch.Dashboard(this, "AgentCoreLoopDashboard", {
      dashboardName: `${cdk.Stack.of(this).stackName}-AgentCoreLoop`,
    });
    loopDashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: "AgentCore Loop Requests",
        left: [loopRequestsMetric],
      }),
      new cloudwatch.GraphWidget({
        title: "AgentCore Loop Client/Server Errors",
        left: [loopClientErrorsMetric, loopServerErrorsMetric],
      }),
      new cloudwatch.GraphWidget({
        title: "AgentCore Loop Latency p50/p95 (ms)",
        left: [loopLatencyP50Metric, loopLatencyP95Metric],
      }),
    );

    artifactsBucket.grantReadWrite(simulateFn);
    artifactsBucket.grantReadWrite(statusFn);
    artifactsBucket.grantReadWrite(executeFn);
    artifactsBucket.grantReadWrite(agentcoreHelloFn);
    artifactsBucket.grantReadWrite(agentcoreToolsFn);
    artifactsBucket.grantReadWrite(agentcoreMemoryFn);
    // AgentCoreLoopFn needs explicit S3 permissions for artifacts
    artifactsBucket.grantReadWrite(agentcoreLoopFn);
    agentcoreMemoryTable.grantReadWriteData(agentcoreMemoryFn);

    stateTable.grantReadWriteData(simulateFn);
    stateTable.grantReadWriteData(executeFn);

    runsTable.grantReadWriteData(simulateFn);
    runsTable.grantReadWriteData(statusFn);
    runsTable.grantReadWriteData(executeFn);
    runsTable.grantReadWriteData(agentcoreLoopFn);

    policiesTable.grantReadWriteData(simulateFn);

    if (this.node.tryGetContext("enableBedrockPlanner")) {
      simulateFn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ["bedrock:InvokeModel"],
          resources: ["*"],
        }),
      );
    }

    new cdk.CfnOutput(this, "ArtifactsBucketName", {
      value: artifactsBucket.bucketName,
    });
    new cdk.CfnOutput(this, "StateTableName", {
      value: stateTable.tableName,
    });
    new cdk.CfnOutput(this, "RunsTableName", {
      value: runsTable.tableName,
    });
    new cdk.CfnOutput(this, "PoliciesTableName", {
      value: policiesTable.tableName,
    });
    new cdk.CfnOutput(this, "SimulateFunctionName", {
      value: simulateFn.functionName,
    });
    new cdk.CfnOutput(this, "ExecuteFunctionName", {
      value: executeFn.functionName,
    });
    new cdk.CfnOutput(this, "StatusFunctionName", {
      value: statusFn.functionName,
    });
    new cdk.CfnOutput(this, "AgentCoreHelloFunctionName", {
      value: agentcoreHelloFn.functionName,
    });
    new cdk.CfnOutput(this, "AgentCoreHelloApiUrl", {
      value: agentcoreHelloApi.apiEndpoint,
    });
    new cdk.CfnOutput(this, "AgentCoreToolsFunctionName", {
      value: agentcoreToolsFn.functionName,
    });
    new cdk.CfnOutput(this, "AgentCoreToolsApiUrl", {
      value: agentcoreHelloApi.apiEndpoint,
    });
    new cdk.CfnOutput(this, "AgentCoreMemoryFunctionName", {
      value: agentcoreMemoryFn.functionName,
    });
    new cdk.CfnOutput(this, "AgentCoreMemoryApiUrl", {
      value: agentcoreHelloApi.apiEndpoint,
    });
    new cdk.CfnOutput(this, "AgentCoreLoopFunctionName", {
      value: agentcoreLoopFn.functionName,
    });
    new cdk.CfnOutput(this, "AgentCoreLoopApiUrl", {
      value: agentcoreHelloApi.apiEndpoint,
    });
    new cdk.CfnOutput(this, "AgentCoreLoopDashboardName", {
      value: loopDashboard.dashboardName,
    });
    new cdk.CfnOutput(this, "AgentCoreLoopErrorsAlarmName", {
      value: loopServerErrorsAlarm.alarmName,
    });
    new cdk.CfnOutput(this, "AgentCoreLoopLatencyP95AlarmName", {
      value: loopLatencyP95Alarm.alarmName,
    });
    new cdk.CfnOutput(this, "AgentCoreMemoryTableName", {
      value: agentcoreMemoryTable.tableName,
    });
  }
}
