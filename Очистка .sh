#!/bin/bash
sudo aptitude search '?broken' purge '~b'
sudo apt-get clean -y
sudo apt-get autoclean -y
sudo apt-get autoremove -y
sudo apt install -f
sudo dpkg --configure -a
sudo apt-get --fix-broken install
sudo apt update
exit
