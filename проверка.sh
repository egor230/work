#!/bin/bash 
gnome-terminal -- bash -c '
echo $(pwd);
read;
exec bash'
