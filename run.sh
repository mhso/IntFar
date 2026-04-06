pushd $(dirname $0)

port=5000

# Clean up old image
podman stop -i intfar
podman rm -i intfar

# Build latest image and run container
podman build . -t intfar:latest --env PORT=$port
podman image prune -f

podman run \
    --name intfar \
    -i \
    -t \
    -p $port:$port \
    -m 6500m \
    --memory-reservation 4g \
    -v ./log:/intfar/log \
    -v ./resources/databases:/intfar/resources/databases \
    -v ./resources/game_data:/intfar/resources/game_data \
    -v ./src/intfar/app/static/champ_data:/intfar/src/intfar/app/static/champ_data \
    -v ./src/intfar/app/static/img/avatars:/intfar/src/intfar/app/static/img/avatars \
    -v ./src/intfar/app/static/img/champions:/intfar/src/intfar/app/static/img/champions \
    -v ./src/intfar/app/static/img/items:/intfar/src/intfar/app/static/img/items \
    -v ./src/intfar/app/static/sounds:/intfar/src/intfar/app/static/sounds \
    -v $HOME/.config/steamguard-cli/maFiles:/root/.config/steamguard-cli/maFiles \
    intfar:latest

popd