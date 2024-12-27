#!/bin/bash


dayu::util::install_yq(){

  if ! command -v yq &> /dev/null; then
      echo "yq could not be found, installing..."
      wget -O /usr/local/bin/yq https://github.com/mikefarah/yq/releases/download/v4.6.1/yq_linux_amd64
      sudo chmod +x /usr/local/bin/yq
      echo "yq installed successfully."
  fi

}

