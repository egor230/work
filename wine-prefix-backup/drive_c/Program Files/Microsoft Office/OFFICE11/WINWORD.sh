#!/bin/bash
export WINEDLLOVERRIDES="d3d8,d3d9,ddraw,dinput8,dsound=n,b";
export PW_VULKAN_USE=1;
export LAUNCH_PARAMETERS="";
WINE_FULLSCREEN_FSR=1
export WINE_SIMULATE_WRITE=COPY wine "/home/egor/.wine/drive_c/Program Files/Microsoft Office/OFFICE11/WINWORD.EXE";
export WINE_FULLSCREEN_FSR_STRENGTH=5
export LC_CTYPE LC_COLLATE LC_ALL LANG
wine "/home/egor/.wine/drive_c/Program Files/Microsoft Office/OFFICE11/WINWORD.EXE" --fullscreen;
exit; 