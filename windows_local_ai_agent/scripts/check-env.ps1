$ErrorActionPreference = "Continue"
Write-Host "Python:"; py -3 --version
Write-Host "`nWSL distros:"; wsl --list --verbose
Write-Host "`nSSH:"; ssh -V
Write-Host "`nVMware vmrun (optional):"; Get-Command vmrun.exe -ErrorAction SilentlyContinue | Select-Object Source
