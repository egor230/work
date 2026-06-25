#!/bin/bash 
gnome-terminal -- bash -c '
#git clone https://github.com/libratbag/libratbag.git
cd libratbag
meson builddir
ninja -C builddir
sudo ninja -C builddir install
read;
exec bash'
