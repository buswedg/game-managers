#Requires -RunAsAdministrator
param(
    [switch]$y
)

$registryPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\",
    "HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\"
)

$keysFound = 0
$keysDeleted = 0

foreach ($path in $registryPaths) {
    $subkeys = Get-ChildItem -Path $path
    foreach ($subkey in $subkeys) {
        $uninstallString = (Get-ItemProperty -Path $subkey.PSPath).UninstallString
        if ($uninstallString -like "*steam://uninstall/*") {
            $keysFound++
            
            if ($y) {
                Write-Host "Auto-deleting key $($subkey.PSPath)" -ForegroundColor Yellow
                Remove-Item -Path $subkey.PSPath -Force
                $keysDeleted++
            } else {
                $choice = Read-Host "Do you want to delete key $($subkey.PSPath)? (Y/N)"
                if ($choice -eq "Y") {
                    Write-Host "Deleting key $($subkey.PSPath)" -ForegroundColor Green
                    Remove-Item -Path $subkey.PSPath -Force
                    $keysDeleted++
                } else {
                    Write-Host "Skipped key $($subkey.PSPath)" -ForegroundColor Gray
                }
            }
        }
    }
}

Write-Host "`nSummary:" -ForegroundColor Cyan
Write-Host "  Steam registry keys found: $keysFound" -ForegroundColor White
Write-Host "  Steam registry keys deleted: $keysDeleted" -ForegroundColor White

if ($keysFound -eq 0) {
    Write-Host "No Steam uninstall registry keys found." -ForegroundColor Green
}

Write-Host "Exiting script in 5 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
exit