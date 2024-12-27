#!/bin/bash


dayu::util::install_yq(){

  if ! command -v yq &> /dev/null; then
      echo "yq could not be found, installing..."
      wget -O /usr/local/bin/yq https://github.com/mikefarah/yq/releases/download/v4.6.1/yq_linux_amd64
      sudo chmod +x /usr/local/bin/yq
      echo "yq installed successfully."
  fi

}

dayu::util::install_tomlq(){
  wget https://github.com/kowainik/tomlq/releases/download/v1.0.0/tomlq-linux-amd64.tar.gz
  if ! command -v yq &> /dev/null; then
      echo "tomlq could not be found, installing..."

      local INSTALL_DIR="/usr/local/bin"
      local TMP_DIR=$(mktemp -d)
      local TOMLQ_BINARY_URL="https://github.com/kowainik/tomlq/releases/download/v1.0.0/tomlq-linux-amd64.tar.gz"
      cd "$TMP_DIR" || { echo "unable move into temporary directory"; return 1; }
      wget -q "$TOMLQ_BINARY_URL" -O tomlq.tar.gz
      tar -xzf tomlq.tar.gz
      sudo mv "$BINARY_NAME" "$INSTALL_DIR/"
      tomlq --version
      cd - || { echo "unable move out temporary directory"; return 1; }
      rm -rf "$TMP_DIR"

      echo "tomlq installed successfully."
  fi
}


