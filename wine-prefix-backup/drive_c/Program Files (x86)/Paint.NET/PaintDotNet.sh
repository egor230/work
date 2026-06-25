#!/bin/bash
export WINEDLLOVERRIDES="d3d8,d3d9,ddraw,dinput8,dsound=n,b";
export PW_VULKAN_USE=0;
export LAUNCH_PARAMETERS="";
wine "/home/egor/.wine/drive_c/Program Files/Paint.NET/PaintDotNet.exe" #--fullscreen;
exit; 