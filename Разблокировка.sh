#!/bin/bash
gnome-terminal -- bash -c '
cd ~/.local/share/keyrings;
chmod +x *;
chmod 600 ~/.local/share/keyrings/default
chmod 600 ~/.local/share/keyrings/Связка_ключей_по_умолчанию.keyring
eval "$(ssh-agent)";
ssh-add ~/.local/share/keyrings/default;
ssh-add ~/.local/share/keyrings/Связка_ключей_по_умолчанию.keyring;
exec bash'
