# Copyright 2021 The KubeEdge Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Add cross buildx improvement
# _speed_buildx_for_go_
ARG REG=docker.io
FROM ${REG}/alpine:3.11

ARG SEDNA_PATH=./sedna

COPY  $SEDNA_PATH/_output/bin/sedna-gm /usr/local/bin/sedna-gm

COPY $SEDNA_PATH/build/gm/gm-config.yaml /gm.yaml

CMD ["sedna-gm", "--config", "/gm.yaml"]
