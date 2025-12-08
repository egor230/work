#!/bin/bash
#wmctrl -s 1
sudo modprobe -r kvm_intel
sudo modprobe -r kvm
VBoxManage modifyvm "7" --nested-hw-virt on
VBoxManage modifyvm "windows xp " --nested-hw-virt on
VBoxManage startvm "windows xp "
#wmctrl -s 0
#rdesktop -u egor -p 1 192.168.0.11
exit
#sudo usermod -aG audio
