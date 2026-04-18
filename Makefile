.PHONY: deploy-agentcore-loop smoke-agentcore-loop demo-agentcore-loop setup lint test-unit test-integration test cdk-synth verify verify-aws demo-aws-planner smoke-aws-planner demo-agentcore-base smoke-agentcore-base deploy-agentcore-base deploy-agentcore-tools smoke-agentcore-tools demo-agentcore-tools deploy-agentcore-memory smoke-agentcore-memory demo-agentcore-memory verify-agentcore-memory

setup:
	@if command -v uv >/dev/null 2>&1; then \
		echo "Using uv to install Python dependencies"; \
		uv pip install pydantic boto3 requests certifi pytest ruff; \
	else \
		echo "uv not found; using pip to install Python dependencies"; \
		python3 -m pip install --upgrade pip; \
		python3 -m pip install pydantic boto3 requests certifi pytest ruff; \
	fi
	cd infra/cdk && npm install

lint:
	ruff check services tests

test-unit:
	pytest tests/unit

test-integration:
	pytest tests/integration

test: test-unit test-integration

demo-local:
	python3 scripts/demo_local.py

demo-local-planner:
	python3 scripts/demo_local_planner.py

demo-local-strategy:
	python3 scripts/demo_local_strategy.py

demo-local-tape:
	python3 scripts/demo_local_trade_tape.py

demo-local-loop:
	python3 scripts/demo_local_loop.py

demo-local-bedrock:
	python3 scripts/demo_local_bedrock_planner.py

replay-executions:
	python3 scripts/replay_executions.py --executions tmp/demo_local_loop/executions.json

cdk-install:
	npm --prefix infra/cdk install

cdk-synth:
	@cd infra/cdk && \
	if [ -x node_modules/.bin/cdk ]; then \
		./node_modules/.bin/cdk synth; \
	else \
		echo "CDK not initialized yet. Run 'npm install' in infra/cdk once ready."; \
		exit 1; \
	fi

cdk-deploy:
	cd infra/cdk && npx cdk deploy --require-approval never

deploy-agentcore-base:
	cd infra/cdk && npx cdk deploy --require-approval never

deploy-agentcore-tools:
	cd infra/cdk && npx cdk deploy --require-approval never

smoke-aws:
	python3 scripts/smoke_aws.py

demo-aws:
	python3 scripts/demo_aws.py

demo-aws-planner:
	python3 scripts/demo_aws_planner.py

smoke-aws-planner:
	python3 scripts/smoke_aws_planner.py

smoke-agentcore-base:
	python3 scripts/smoke_agentcore_hello.py

demo-agentcore-base:
	python3 scripts/smoke_agentcore_hello.py
	python3 scripts/smoke_agentcore_hello.py

smoke-agentcore-tools:
	python3 scripts/smoke_agentcore_tools.py

demo-agentcore-tools:
	python3 scripts/demo_agentcore_tools.py

deploy-agentcore-memory:
	cd infra/cdk && npx cdk deploy --require-approval never

smoke-agentcore-memory:
	python3 scripts/smoke_agentcore_memory.py

demo-agentcore-memory:
	python3 scripts/demo_agentcore_memory.py

verify-agentcore-memory: lint test
	@if [ "$$RUN_AWS_TESTS" = "1" ]; then \
		$(MAKE) smoke-agentcore-memory; \
	fi

verify: lint test demo-local

verify-aws:
	@if [ -z "$$AWS_PROFILE" ]; then \
		echo "AWS_PROFILE is not set. Run: AWS_PROFILE=<profile> make verify-aws"; \
		exit 1; \
	fi
	$(MAKE) cdk-synth
	$(MAKE) cdk-deploy
	$(MAKE) smoke-aws
	$(MAKE) demo-aws
	$(MAKE) smoke-aws-planner
	$(MAKE) demo-aws-planner
	$(MAKE) deploy-agentcore-base
	$(MAKE) smoke-agentcore-base
	$(MAKE) demo-agentcore-base
	$(MAKE) deploy-agentcore-tools
	$(MAKE) smoke-agentcore-tools
	$(MAKE) demo-agentcore-tools
	$(MAKE) deploy-agentcore-memory
	$(MAKE) smoke-agentcore-memory
	$(MAKE) demo-agentcore-memory


deploy-agentcore-loop:
	cd infra/cdk && npm install
	cd infra/cdk && npx cdk deploy --require-approval never

smoke-agentcore-loop:
	python3 scripts/smoke_agentcore_loop.py

demo-agentcore-loop:
	python3 scripts/demo_agentcore_loop.py

deploy-agentcore-loop-planner:
	cd infra/cdk && npx cdk deploy --require-approval never -c enableLocalPlanner=1
