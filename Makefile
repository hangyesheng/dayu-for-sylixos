REGISTRY := $(or $(REG),docker.io)
REPOSITORY := $(or $(REPO),dayuhub)
IMAGE_REPO ?= $(REGISTRY)/$(REPOSITORY)
IMAGE_TAG ?= $(or $(TAG),v1.0)

define BUILD_HELP_INFO
# Build Docker images using the build.sh script in the 'hack' folder.
#
# Usage:
#   make build WHAT=component
#   make images
#
# Components:
#   generator, distributor, controller, monitor, scheduler, car-detection, etc.
#
# Example:
#   make build WHAT=monitor,generator
#   make images
endef

.PHONY: build images help

ifeq ($(HELP),y)
help:
	@echo "$$BUILD_HELP_INFO"
else
help:
	bash ./hack/build.sh --help
endif

# Build images
build:
	bash ./hack/build.sh --files $(WHAT) --tag $(TAG) --repo $(REPO) --registry $(REGISTRY) --no-cache

# Build all images
images:
	bash ./hack/build.sh --tag $(TAG) --repo $(REPO) --registry $(REGISTRY) --no-cache


