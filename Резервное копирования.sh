#!/bin/bash
gnome-terminal  -- bash -c '
sudo rsync -avh --progress --update / //media/egor/reze

exec bash'
