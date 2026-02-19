pushd $(dirname $0)

port=5000

# Copy steamguard-cli manifest files to current directory
cp -r $HOME/.config/steamguard-cli/maFiles ./maFiles

# Build latest image and run container
podman build . -t intfar:latest --env PORT=$port
podman run --name intfar -p $port:$port --replace intfar:latest

# Clean up old images
podman image prune -f > /dev/null

rm -r ./maFiles

popd