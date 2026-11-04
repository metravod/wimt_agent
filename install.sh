#!/bin/sh
# Installs (or updates) the bot on a Linux server or a Mac with Docker Desktop:
#
#   curl -fsSL https://raw.githubusercontent.com/metravod/wimt_agent/main/install.sh | sh
#
# Run the same command again any time to update. Your data is kept.
set -e

IMAGE="${IMAGE:-ghcr.io/metravod/wimt_agent:latest}"
NAME=wimt-agent
SETTINGS="$HOME/.wimt-agent.env"

if ! command -v docker >/dev/null 2>&1; then
    if [ "$(uname)" = "Linux" ]; then
        echo "Installing Docker..."
        curl -fsSL https://get.docker.com | sh
    else
        echo "Please install Docker Desktop first: https://www.docker.com/products/docker-desktop/"
        echo "Then run this command again."
        exit 1
    fi
fi

DOCKER=docker
docker info >/dev/null 2>&1 || DOCKER="sudo docker"

if [ ! -f "$SETTINGS" ]; then
    echo "Two things are needed (see README):"
    printf "  Telegram bot token from @BotFather: "
    read -r BOT_TOKEN </dev/tty
    printf "  OpenAI API key: "
    read -r OPENAI_API_KEY </dev/tty
    printf 'BOT_TOKEN=%s\nOPENAI_API_KEY=%s\n' "$BOT_TOKEN" "$OPENAI_API_KEY" >"$SETTINGS"
    chmod 600 "$SETTINGS"
fi

$DOCKER pull "$IMAGE"
$DOCKER rm -f "$NAME" >/dev/null 2>&1 || true
$DOCKER run -d --name "$NAME" --restart unless-stopped \
    --env-file "$SETTINGS" -v wimt-agent:/data "$IMAGE" >/dev/null

echo
echo "Done! The bot is running."
echo "Open it in Telegram and send /start. The first person to do so becomes the team admin."
echo "Settings are saved in $SETTINGS. See the logs with: $DOCKER logs -f $NAME"
