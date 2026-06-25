#!/bin/bash
export WINEDLLOVERRIDES="d3d8,d3d9,ddraw,dinput8,dsound=n,b";
export PW_VULKAN_USE=0;
export LAUNCH_PARAMETERS="";
export WINE_SIMULATE_WRITE=COPY wine "/home/egor/.wine/drive_c/Program Files (x86)/Microsoft Office/OFFICE11/WINWORD.EXE";
wine "/home/egor/.wine/drive_c/Program Files (x86)/Microsoft Office/OFFICE11/WINWORD.EXE" #--fullscreen;
exit; 