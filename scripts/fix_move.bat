@echo off
robocopy "C:\172.20.255.13\tasyausta\anexo_opme" "\\172.20.255.13\tasyausta\anexo_opme" *.pdf /MOV /R:2 /W:3 /NP
echo Concluido.
pause
