PYTHON := python3
WAW_CONTRACTS := ../waw-contracts/dist

# 🔍 Root-relative paths
IDENTITY_DIR := ../waw-identity
SYNC_DIR := ../waw-sync
CLOUD_DIR := ../waw-sync/backend_mock
PROTO_DIR := ../waw-contracts/proto
DB_PATH := ../waw-identity/identity.db

CHECK_ROOT := $(shell test -d $(IDENTITY_DIR) && test -d $(SYNC_DIR) && echo OK)

.PHONY: dev identity sync cloud clean check-root build

build:
	@echo "→ Generating gRPC stubs..."
	$(PYTHON) -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(WAW_CONTRACTS) \
		--grpc_python_out=$(WAW_CONTRACTS) \
		$(PROTO_DIR)/identity.proto $(PROTO_DIR)/model.proto
	@echo "→ gRPC stubs generated in $(WAW_CONTRACTS)"

dev: check-root
	@echo "🚀 Starting all services (gRPC + Sync + Cloud Mock)..."
	@$(MAKE) -j3 identity sync cloud


identity: check-root
	@echo "🔐 Starting IdentityService on port 50051..."
	cd $(IDENTITY_DIR) && PYTHONPATH=$(WAW_CONTRACTS) $(PYTHON) src/identity_srv.py

sync: check-root
	@echo "🔁 Starting waw-sync loop..."
	cd $(SYNC_DIR) && PYTHONPATH=$(WAW_CONTRACTS) $(PYTHON) src/sync_loop.py

cloud: check-root
	@echo "☁️ Starting Cloud API server at localhost:8000..."
	cd $(CLOUD_DIR) && $(PYTHON) -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

check-root:
	@if [ "$(CHECK_ROOT)" != "OK" ]; then \
		echo "❌ Error: Please run from within waw-contracts/ (with sibling folders waw-identity and waw-sync)."; \
		exit 1; \
	fi

