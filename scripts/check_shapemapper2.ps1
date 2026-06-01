$ErrorActionPreference = "Stop"

wsl --exec bash -lc 'shapeMapper="$HOME/tools/shapemapper2-2.3/shapemapper"; test -x "$shapeMapper"; "$shapeMapper" --version'
