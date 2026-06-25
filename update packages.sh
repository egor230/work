#!/bin/bash
gnome-terminal -- bash -c '
echo "1" | sudo -S apt update;
sudo apt upgrade && apt list --upgradable && sudo apt dist-upgrade
exec bash
'
