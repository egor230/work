#!/bin/bash
sudo fuser -k /dev/loop0
sudo losetup -d /dev/loop0
sudo fuser -v /dev/loop0

sudo fuser -k /dev/loop1
sudo losetup -d /dev/loop1
sudo fuser -v /dev/loop1

exit;
