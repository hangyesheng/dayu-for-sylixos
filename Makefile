REGISTRY := $(or $(REG),docker.io)
REPOSITORY := $(or $(REPO),dayuhub)
IMAGE_REPO ?= $(REGISTRY)/$(REPOSITORY)
IMAGE_TAG ?= $(or $(TAG),v1.0)

define BUILD_HELP_INFO
# Build Docker images using the build.sh script in the 'hack' folder.
#
# Usage:
#   make build WHAT=component
#   make all
#
# Components:
#   backend, frontend, datasource, generator, distributor, controller, monitor, scheduler, car-detection, etc.
#
# Example:
#   make build WHAT=monitor,generator
#   make all
endef

.PHONY: build all help


help:
	@echo "$$BUILD_HELP_INFO"


# Build images
build:
	bash ./hack/build.sh --files $(WHAT) --tag $(IMAGE_TAG) --repo $(REPOSITORY) --registry $(REGISTRY)

# Build all images
all:
	bash ./hack/build.sh --tag $(IMAGE_TAG) --repo $(REPOSITORY) --registry $(REGISTRY)


